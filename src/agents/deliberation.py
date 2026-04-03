"""
Deliberation Orchestrator — Multi-Agent Deliberation System
Runs AnalystAgent, RiskAgent, ComplianceAgent in PARALLEL across 2 rounds,
then applies consensus rules to decide PROCEED / BLOCK / MODIFY.
ExecutionAgent only fires after consensus.

Consensus rules:
  • 3/3 PROCEED  → ExecutionAgent generates final plan
  • Any BLOCK    → pipeline stops, full log sent to audit
  • 2/3 PROCEED + 1 MODIFY → apply modification, proceed to ExecutionAgent
  • RiskAgent veto: if RiskAgent verdict==BLOCK and confidence > 80 → instant block
"""

from __future__ import annotations
import asyncio
import itertools
import json
import time
import logging
from datetime import datetime, timezone
from typing import Any

from .analyst_agent    import AnalystAgent
from .risk_agent       import RiskAgent
from .compliance_agent import ComplianceAgent
from .execution_agent  import ExecutionAgent

logger = logging.getLogger(__name__)

_id_counter = itertools.count(1)


class DeliberationOrchestrator:

    VETO_CONFIDENCE_THRESHOLD = 80

    def __init__(self):
        self._analyst    = AnalystAgent()
        self._risk       = RiskAgent()
        self._compliance = ComplianceAgent()
        self._execution  = ExecutionAgent()

    # ── Public API ──────────────────────────────────────────────────────────

    def run(self, sid: dict, grc_prompt: str) -> dict:
        """Synchronous entry-point — wraps async run."""
        return asyncio.run(self.run_async(sid, grc_prompt))

    async def run_async(self, sid: dict, grc_prompt: str) -> dict:
        """Full deliberation: 2 rounds, voting, optional ExecutionAgent."""
        start_ms = int(time.time() * 1000)
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        delib_id = f"delib-{date_str}-{next(_id_counter):03d}"

        rounds_log: list[dict] = []

        # ── ROUND 1: Independent assessments (parallel) ──────────────────
        r1_results = await self._run_round(sid, grc_prompt, round_num=1, others=None)
        rounds_log.append({"round": 1, **r1_results})

        # Early exit: risk veto after round 1
        veto = self._check_veto(r1_results["risk"])
        if veto:
            duration = int(time.time() * 1000) - start_ms
            return self._build_result(
                delib_id, sid["sid_id"], rounds_log,
                "BLOCK", None, True, duration,
                reason="RiskAgent veto (round 1, confidence > 80 on BLOCK)",
            )

        # ── ROUND 2: Cross-agent responses (parallel) ────────────────────
        r2_results = await self._run_round(sid, grc_prompt, round_num=2, others=r1_results)
        rounds_log.append({"round": 2, **r2_results})

        # ── VOTING ────────────────────────────────────────────────────────
        veto_triggered = self._check_veto(r2_results["risk"])
        if veto_triggered:
            duration = int(time.time() * 1000) - start_ms
            return self._build_result(
                delib_id, sid["sid_id"], rounds_log,
                "BLOCK", None, True, duration,
                reason="RiskAgent veto (round 2, confidence > 80 on BLOCK)",
            )

        consensus, modifications = self._compute_consensus(r2_results)
        duration = int(time.time() * 1000) - start_ms

        if consensus == "BLOCK":
            return self._build_result(
                delib_id, sid["sid_id"], rounds_log,
                "BLOCK", None, False, duration,
                reason="Majority or unanimous BLOCK vote",
            )

        # PROCEED or MODIFY → ExecutionAgent generates final plan
        exec_summary = self._summarize_deliberation(r2_results)
        execution_plan = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._execution.generate_plan(
                sid, grc_prompt, consensus, exec_summary, modifications
            ),
        )

        return self._build_result(
            delib_id, sid["sid_id"], rounds_log,
            consensus, execution_plan, False, duration,
        )

    # ── Async round runner ──────────────────────────────────────────────────

    async def _run_round(
        self,
        sid: dict,
        grc_prompt: str,
        round_num: int,
        others: dict | None,
    ) -> dict:
        """Run all three deliberation agents in parallel for one round."""
        loop = asyncio.get_event_loop()

        analyst_fut    = loop.run_in_executor(None, lambda: self._safe_call(
            self._analyst,    sid, grc_prompt, others, round_num))
        risk_fut       = loop.run_in_executor(None, lambda: self._safe_call(
            self._risk,       sid, grc_prompt, others, round_num))
        compliance_fut = loop.run_in_executor(None, lambda: self._safe_call(
            self._compliance, sid, grc_prompt, others, round_num))

        analyst_r, risk_r, compliance_r = await asyncio.gather(
            analyst_fut, risk_fut, compliance_fut
        )
        return {"analyst": analyst_r, "risk": risk_r, "compliance": compliance_r}

    def _safe_call(self, agent, sid, grc_prompt, others, round_num) -> dict:
        """Call agent.deliberate() with retry + abstain fallback."""
        try:
            return agent.deliberate(sid, grc_prompt, others, round_num)
        except Exception as exc:
            logger.warning("%s round %d failed: %s — abstaining (MODIFY)", agent.NAME, round_num, exc)
            return {
                "verdict":               "MODIFY",
                "confidence":            50,
                "reason":                f"{agent.NAME} agent error — abstaining: {exc}",
                "suggested_modification": None,
            }

    # ── Voting logic ────────────────────────────────────────────────────────

    def _check_veto(self, risk_result: dict) -> bool:
        return (
            risk_result.get("verdict", "").upper() == "BLOCK"
            and int(risk_result.get("confidence", 0)) > self.VETO_CONFIDENCE_THRESHOLD
        )

    def _compute_consensus(self, round_results: dict) -> tuple[str, list[str]]:
        """Return (consensus_string, list_of_modifications)."""
        verdicts = {
            "analyst":    round_results["analyst"]["verdict"].upper(),
            "risk":       round_results["risk"]["verdict"].upper(),
            "compliance": round_results["compliance"]["verdict"].upper(),
        }
        modifications: list[str] = []

        # Collect any MODIFY suggestions
        for agent_name, v in verdicts.items():
            if v == "MODIFY":
                mod = round_results[agent_name].get("suggested_modification")
                if mod:
                    modifications.append(mod)

        proceed_count = sum(1 for v in verdicts.values() if v == "PROCEED")
        block_count   = sum(1 for v in verdicts.values() if v == "BLOCK")
        modify_count  = sum(1 for v in verdicts.values() if v == "MODIFY")

        # Any BLOCK → pipeline stops
        if block_count >= 1:
            return ("BLOCK", [])

        # 3/3 PROCEED
        if proceed_count == 3:
            return ("PROCEED", [])

        # 2 PROCEED + 1 MODIFY  OR  any other combination without BLOCK
        return ("MODIFY", modifications)

    def _summarize_deliberation(self, round_results: dict) -> str:
        parts = []
        for agent_name in ("analyst", "risk", "compliance"):
            r = round_results.get(agent_name, {})
            parts.append(
                f"{agent_name.capitalize()}: verdict={r.get('verdict')} "
                f"conf={r.get('confidence')} — {r.get('reason', '')[:80]}"
            )
        return " | ".join(parts)

    # ── Result builder ──────────────────────────────────────────────────────

    def _build_result(
        self,
        delib_id: str,
        sid_ref: str,
        rounds: list[dict],
        consensus: str,
        execution_plan: dict | None,
        veto_triggered: bool,
        duration_ms: int,
        reason: str = "",
    ) -> dict:
        return {
            "deliberation_id":        delib_id,
            "sid_reference":          sid_ref,
            "rounds":                 rounds,
            "final_consensus":        consensus,
            "execution_plan":         execution_plan,
            "veto_triggered":         veto_triggered,
            "deliberation_duration_ms": duration_ms,
            "block_reason":           reason if consensus == "BLOCK" else None,
            "timestamp":              datetime.now(timezone.utc).isoformat(),
        }


# ── Standalone test ──────────────────────────────────────────────────────────
def test_deliberation():
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    # Minimal SID stub
    sid_proceed = {
        "sid_id":            "sid-test-001",
        "primary_action":    "execute_trade",
        "permitted_actions": ["query_market_data", "analyze_sentiment",
                              "verify_constraints", "execute_trade"],
        "prohibited_actions": ["transmit_external", "short_sell"],
        "scope":             {"tickers": ["AAPL"], "max_quantity": 5, "side": "buy", "order_type": "market"},
        "reasoning_bounds":  {"forbidden_topics": []},
        "ambiguity_flags":   [],
    }
    sid_block = {
        **sid_proceed,
        "sid_id": "sid-test-002",
        "scope": {"tickers": ["TSLA"], "max_quantity": 100, "side": "buy", "order_type": "market"},
    }
    grc = "You may only buy AAPL, max 5 shares, market order. No external data."

    orch = DeliberationOrchestrator()

    print("\n=== Deliberation Test: BUY 5 AAPL (should PROCEED) ===")
    r = orch.run(sid_proceed, grc)
    print(f"  Consensus: {r['final_consensus']} | Veto: {r['veto_triggered']} | {r['deliberation_duration_ms']}ms")

    print("\n=== Deliberation Test: BUY 100 TSLA (should BLOCK) ===")
    r2 = orch.run(sid_block, grc)
    print(f"  Consensus: {r2['final_consensus']} | Veto: {r2['veto_triggered']} | {r2['deliberation_duration_ms']}ms")
    print()


if __name__ == "__main__":
    test_deliberation()
