"""
LeaderAgent - Pipeline Commander & Agent Supervisor
Monitors all agents, validates quality, makes final meta-decisions.

4 Phases:
  1. Pre-validate pipeline preconditions
  2. Monitor each deliberation round for quality
  3. Make final meta-decision (APPROVE / OVERRIDE_BLOCK / ESCALATE)
  4. Session-level health assessment
"""

from __future__ import annotations
import logging
import itertools
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
_id_counter = itertools.count(1)

# Thresholds
MIN_AGENT_CONFIDENCE = 40
MAX_CONFIDENCE_SPREAD = 50
ESCALATION_THRESHOLD = 4
MIN_REASON_LENGTH = 10


class LeaderAgent:
    NAME = "leader"

    def __init__(self):
        self._anomaly_count = 0
        self._session_decisions: list[dict] = []

    # Phase 1: Pre-Deliberation Validation
    def pre_validate(self, sid: dict, grc_prompt: str, firewall_result: dict) -> dict:
        issues = []

        if firewall_result.get("status") != "PASS":
            issues.append("FIREWALL_NOT_PASSED")

        for field in ("sid_id", "primary_action", "permitted_actions", "scope"):
            if field not in sid:
                issues.append(f"SID_MISSING_{field.upper()}")

        if not sid.get("scope", {}).get("tickers"):
            issues.append("NO_TICKERS_IN_SCOPE")

        if len(grc_prompt) < 100:
            issues.append(f"GRC_FENCE_TOO_SHORT ({len(grc_prompt)} chars)")

        ambiguity = sid.get("ambiguity_flags", [])
        if ambiguity and "execute_trade" in sid.get("permitted_actions", []):
            issues.append("AMBIGUITY_WITH_TRADE_PERMITTED")

        return {
            "proceed": len(issues) == 0,
            "issues": issues,
            "phase": "pre_validation",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Phase 2: Round Monitoring
    def monitor_round(self, round_num: int, round_results: dict) -> dict:
        anomalies = []
        agent_health = {}
        confidences = []

        for agent_name in ("analyst", "risk", "compliance"):
            data = round_results.get(agent_name, {})
            verdict = data.get("verdict", "UNKNOWN")
            confidence = int(data.get("confidence", 0))
            reason = data.get("reason", "")

            confidences.append(confidence)
            health = "HEALTHY"

            if confidence < MIN_AGENT_CONFIDENCE:
                anomalies.append(f"{agent_name}: low_confidence={confidence}")
                health = "DEGRADED"

            if len(reason.strip()) < MIN_REASON_LENGTH:
                anomalies.append(f"{agent_name}: empty_reasoning")
                health = "DEGRADED"

            if verdict not in ("PROCEED", "BLOCK", "MODIFY"):
                anomalies.append(f"{agent_name}: invalid_verdict={verdict}")
                health = "ERROR"

            agent_health[agent_name] = {
                "health": health,
                "verdict": verdict,
                "confidence": confidence,
                "reason_length": len(reason),
            }

        if confidences:
            spread = max(confidences) - min(confidences)
            if spread > MAX_CONFIDENCE_SPREAD:
                anomalies.append(f"confidence_spread={spread}")

            if all(c < 50 for c in confidences):
                anomalies.append("ALL_AGENTS_LOW_CONFIDENCE")

        analyst = round_results.get("analyst", {})
        if (
            analyst.get("verdict") == "PROCEED"
            and any(
                w in analyst.get("reason", "").lower()
                for w in ["violation", "block", "prohibited", "illegal"]
            )
        ):
            anomalies.append("analyst: verdict_reasoning_mismatch")

        self._anomaly_count += len(anomalies)
        quality = "GOOD" if not anomalies else ("DEGRADED" if len(anomalies) <= 2 else "POOR")

        return {
            "round": round_num,
            "quality": quality,
            "anomalies": anomalies,
            "agent_health": agent_health,
            "cumulative_anomalies": self._anomaly_count,
            "needs_escalation": self._anomaly_count >= ESCALATION_THRESHOLD,
            "phase": "round_monitoring",
        }

    # Phase 3: Meta-Decision
    def meta_decide(self, deliberation_result: dict, monitors: list[dict], enforcement_results: dict) -> dict:
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        decision_id = f"leader-{date_str}-{next(_id_counter):03d}"

        consensus = deliberation_result.get("final_consensus", "BLOCK")
        veto = deliberation_result.get("veto_triggered", False)

        reasons = []
        decision = "APPROVE"

        if veto:
            decision = "BLOCK"
            reasons.append("Risk veto triggered - concur with BLOCK")

        elif self._anomaly_count >= ESCALATION_THRESHOLD * 2:
            decision = "ESCALATE"
            reasons.append(f"Anomaly count={self._anomaly_count} - human review needed")

        elif monitors and all(
            monitors[-1].get("agent_health", {}).get(a, {}).get("health") != "HEALTHY"
            for a in ("analyst", "risk", "compliance")
        ):
            decision = "OVERRIDE_BLOCK"
            reasons.append("All agents degraded - override to BLOCK for safety")

        else:
            for layer, result in enforcement_results.items():
                st = result.get("result", result.get("status", ""))
                if st in ("BLOCK", "MISALIGNED", "EMERGENCY_BLOCK"):
                    reasons.append(f"{layer} blocked - concur")
                    break

        if not reasons:
            reasons.append(f"Consensus={consensus}, no anomalies - approved")

        risk_score = self._risk_score(deliberation_result, monitors, enforcement_results)

        result = {
            "decision_id": decision_id,
            "decision": decision,
            "reasons": reasons,
            "consensus": consensus,
            "veto_triggered": veto,
            "anomaly_count": self._anomaly_count,
            "risk_score": risk_score,
            "phase": "meta_decision",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._session_decisions.append(result)
        return result

    # Phase 4: Session Summary
    def session_summary(self) -> dict:
        total = len(self._session_decisions)
        if total == 0:
            return {"total": 0, "health": "NO_DATA"}
        approvals = sum(1 for d in self._session_decisions if d["decision"] == "APPROVE")
        overrides = sum(1 for d in self._session_decisions if d["decision"] == "OVERRIDE_BLOCK")
        escalations = sum(1 for d in self._session_decisions if d["decision"] == "ESCALATE")
        avg_risk = sum(d.get("risk_score", 0) for d in self._session_decisions) / total

        return {
            "total": total,
            "approvals": approvals,
            "overrides": overrides,
            "escalations": escalations,
            "avg_risk": round(avg_risk, 1),
            "health": (
                "HEALTHY"
                if overrides == 0 and escalations == 0
                else "DEGRADED" if escalations == 0 else "CRITICAL"
            ),
        }

    def _risk_score(self, delib: dict, monitors: list[dict], enforcement: dict) -> float:
        score = 0.0
        if delib.get("veto_triggered"):
            score += 30
        for monitor in monitors:
            score += len(monitor.get("anomalies", [])) * 5
        for _, result in enforcement.items():
            st = result.get("result", result.get("status", ""))
            if st == "CORRECT":
                score += 10
            elif st in ("BLOCK", "MISALIGNED", "EMERGENCY_BLOCK"):
                score += 20
        if delib.get("final_consensus") == "MODIFY":
            score += 10
        return min(score, 100.0)
