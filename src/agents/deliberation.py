"""
Deliberation Orchestrator - Leader-supervised multi-agent deliberation.
"""

from __future__ import annotations
import asyncio
import itertools
import logging
import time
from datetime import datetime, timezone

from .analyst_agent import AnalystAgent
from .compliance_agent import ComplianceAgent
from .execution_agent import ExecutionAgent
from .leader_agent import LeaderAgent
from .risk_agent import RiskAgent

logger = logging.getLogger(__name__)
_id_counter = itertools.count(1)


class DeliberationOrchestrator:
    VETO_CONFIDENCE_THRESHOLD = 80

    def __init__(self):
        self._analyst = AnalystAgent()
        self._risk = RiskAgent()
        self._compliance = ComplianceAgent()
        self._execution = ExecutionAgent()
        self._leader = LeaderAgent()

    @property
    def leader(self) -> LeaderAgent:
        return self._leader

    def run(self, sid: dict, grc_prompt: str, firewall_result: dict | None = None) -> dict:
        return asyncio.run(self.run_async(sid, grc_prompt, firewall_result or {"status": "PASS"}))

    async def run_async(self, sid: dict, grc_prompt: str, firewall_result: dict) -> dict:
        start_ms = int(time.time() * 1000)
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        delib_id = f"delib-{date_str}-{next(_id_counter):03d}"

        rounds_log: list[dict] = []
        leader_monitors: list[dict] = []

        pre = self._leader.pre_validate(sid, grc_prompt, firewall_result)
        if not pre.get("proceed", False):
            duration = int(time.time() * 1000) - start_ms
            base = self._base_result(delib_id, sid.get("sid_id", "n/a"), rounds_log, "BLOCK", None, False, duration)
            base["block_reason"] = f"Leader pre-validation failed: {', '.join(pre.get('issues', []))}"
            base["leader_monitors"] = []
            base["leader_decision"] = {
                "decision": "OVERRIDE_BLOCK",
                "reasons": ["Pre-validation failed", *pre.get("issues", [])],
                "phase": "meta_decision",
                "anomaly_count": 0,
                "risk_score": 100,
            }
            base["pre_validation"] = pre
            return base

        r1_results = await self._run_round(sid, grc_prompt, round_num=1, others=None)
        rounds_log.append({"round": 1, **r1_results})
        leader_monitors.append(self._leader.monitor_round(1, r1_results))

        if self._check_veto(r1_results.get("risk", {})):
            duration = int(time.time() * 1000) - start_ms
            base = self._base_result(delib_id, sid.get("sid_id", "n/a"), rounds_log, "BLOCK", None, True, duration)
            base["block_reason"] = "RiskAgent veto (round 1, confidence > 80 on BLOCK)"
            base["leader_monitors"] = leader_monitors
            base["leader_decision"] = self._leader.meta_decide(base, leader_monitors, {})
            base["pre_validation"] = pre
            return base

        r2_results = await self._run_round(sid, grc_prompt, round_num=2, others=r1_results)
        rounds_log.append({"round": 2, **r2_results})
        leader_monitors.append(self._leader.monitor_round(2, r2_results))

        veto_triggered = self._check_veto(r2_results.get("risk", {}))
        consensus, modifications = self._compute_consensus(r2_results)
        duration = int(time.time() * 1000) - start_ms

        execution_plan = None
        block_reason = None
        if veto_triggered:
            consensus = "BLOCK"
            block_reason = "RiskAgent veto (round 2, confidence > 80 on BLOCK)"
        elif consensus == "BLOCK":
            block_reason = "Any BLOCK in consensus round"

        base = self._base_result(
            delib_id,
            sid.get("sid_id", "n/a"),
            rounds_log,
            consensus,
            execution_plan,
            veto_triggered,
            duration,
        )
        base["block_reason"] = block_reason
        base["leader_monitors"] = leader_monitors
        base["pre_validation"] = pre

        leader_decision = self._leader.meta_decide(base, leader_monitors, {})
        base["leader_decision"] = leader_decision

        if leader_decision.get("decision") in ("OVERRIDE_BLOCK", "ESCALATE"):
            base["final_consensus"] = "BLOCK" if leader_decision["decision"] == "OVERRIDE_BLOCK" else consensus
            if leader_decision["decision"] == "OVERRIDE_BLOCK":
                base["block_reason"] = "Leader override due to degraded agents"

        if base["final_consensus"] in ("PROCEED", "MODIFY") and leader_decision.get("decision") == "APPROVE":
            summary = self._summarize_deliberation(r2_results)
            execution_plan = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._execution.generate_plan(sid, grc_prompt, base["final_consensus"], summary, modifications),
            )
            base["execution_plan"] = execution_plan

        return base

    async def _run_round(self, sid: dict, grc_prompt: str, round_num: int, others: dict | None) -> dict:
        loop = asyncio.get_event_loop()
        analyst_fut = loop.run_in_executor(None, lambda: self._safe_call(self._analyst, sid, grc_prompt, others, round_num))
        risk_fut = loop.run_in_executor(None, lambda: self._safe_call(self._risk, sid, grc_prompt, others, round_num))
        compliance_fut = loop.run_in_executor(None, lambda: self._safe_call(self._compliance, sid, grc_prompt, others, round_num))
        analyst_r, risk_r, compliance_r = await asyncio.gather(analyst_fut, risk_fut, compliance_fut)
        return {"analyst": analyst_r, "risk": risk_r, "compliance": compliance_r}

    def _safe_call(self, agent, sid, grc_prompt, others, round_num) -> dict:
        try:
            return agent.deliberate(sid, grc_prompt, others, round_num)
        except ConnectionError as exc:
            logger.error("%s round %d: OpenClaw unreachable: %s", agent.NAME, round_num, exc)
            return {
                "verdict": "ERROR",
                "confidence": 0,
                "reason": f"{agent.NAME}: OpenClaw unreachable — {exc}",
                "source": "error",
                "suggested_modification": None,
            }
        except ValueError as exc:
            logger.error("%s round %d: bad LLM response: %s", agent.NAME, round_num, exc)
            return {
                "verdict": "ERROR",
                "confidence": 0,
                "reason": f"{agent.NAME}: invalid LLM response — {exc}",
                "source": "error",
                "suggested_modification": None,
            }
        except Exception as exc:
            logger.error("%s round %d failed: %s", agent.NAME, round_num, exc)
            return {
                "verdict": "ERROR",
                "confidence": 0,
                "reason": f"{agent.NAME}: unexpected error — {exc}",
                "source": "error",
                "suggested_modification": None,
            }

    def _check_veto(self, risk_result: dict) -> bool:
        return (
            risk_result.get("verdict", "").upper() == "BLOCK"
            and int(risk_result.get("confidence", 0)) > self.VETO_CONFIDENCE_THRESHOLD
        )

    def _compute_consensus(self, round_results: dict) -> tuple[str, list[str]]:
        verdicts = {
            "analyst": round_results.get("analyst", {}).get("verdict", "ERROR").upper(),
            "risk": round_results.get("risk", {}).get("verdict", "ERROR").upper(),
            "compliance": round_results.get("compliance", {}).get("verdict", "ERROR").upper(),
        }
        modifications: list[str] = []
        for agent_name, verdict in verdicts.items():
            if verdict == "MODIFY":
                mod = round_results.get(agent_name, {}).get("suggested_modification")
                if mod:
                    modifications.append(mod)

        error_count = sum(1 for v in verdicts.values() if v == "ERROR")
        if error_count > 0:
            return "BLOCK", []  # Cannot proceed with errored agents

        if any(v == "BLOCK" for v in verdicts.values()):
            return "BLOCK", []
        if all(v == "PROCEED" for v in verdicts.values()):
            return "PROCEED", []
        return "MODIFY", modifications

    def _summarize_deliberation(self, round_results: dict) -> str:
        parts = []
        for agent_name in ("analyst", "risk", "compliance"):
            r = round_results.get(agent_name, {})
            parts.append(
                f"{agent_name.capitalize()}: verdict={r.get('verdict')} conf={r.get('confidence')} source={r.get('source', 'unknown')}"
            )
        return " | ".join(parts)

    def _base_result(
        self,
        delib_id: str,
        sid_ref: str,
        rounds: list[dict],
        consensus: str,
        execution_plan: dict | None,
        veto_triggered: bool,
        duration_ms: int,
    ) -> dict:
        return {
            "deliberation_id": delib_id,
            "sid_reference": sid_ref,
            "rounds": rounds,
            "leader_monitors": [],
            "leader_decision": {},
            "final_consensus": consensus,
            "execution_plan": execution_plan,
            "veto_triggered": veto_triggered,
            "deliberation_duration_ms": duration_ms,
            "block_reason": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
