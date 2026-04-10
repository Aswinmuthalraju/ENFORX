"""
ComplianceAgent — Policy Enforcer
Role: Check if the trade aligns with declared user intent, policy rules,
and regulatory constraints. Flag anything suspicious.
"""

from __future__ import annotations
import logging

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

PERSONA = (
    "You are a compliance officer for an autonomous AI trading system. "
    "Your job is to check whether this trade aligns with the declared user intent, "
    "policy rules, and regulatory constraints. "
    "Flag anything suspicious: scope mismatch, prohibited actions, taint contamination, "
    "intent deviation, or regulatory concerns. "
    "You must output a JSON object with exactly these keys: "
    "verdict (PROCEED/BLOCK/MODIFY), confidence (0-100 integer), "
    "reason (string, 1-3 sentences), suggested_modification (string or null)."
)


class ComplianceAgent(BaseAgent):
    """Compliance-focused deliberation agent — checks policy adherence."""

    NAME = "compliance"

    def deliberate(
        self,
        sid: dict,
        grc_prompt: str,
        others_output: dict | None = None,
        round_num: int = 1,
    ) -> dict:
        """Return {verdict, confidence, reason, response_to_others (round 2 only)}.

        Raises RuntimeError if the LLM endpoint is unreachable after retries.
        """
        user_msg = self._build_prompt(sid, grc_prompt, others_output, round_num)
        result = self._llm.chat_json(PERSONA, user_msg, temperature=0.1, max_tokens=400)
        return self._validate_response(result, round_num)

    def _build_prompt(
        self,
        sid: dict,
        grc_prompt: str,
        others: dict | None,
        round_num: int,
    ) -> str:
        """Build the round-specific prompt for the compliance officer."""
        ticker    = sid.get("scope", {}).get("tickers", ["?"])[0]
        qty       = sid.get("scope", {}).get("max_quantity", 0)
        side      = sid.get("scope", {}).get("side", "buy")
        primary   = sid.get("primary_action", "unknown")
        permitted = sid.get("permitted_actions", [])
        prohibited = sid.get("prohibited_actions", [])
        parts = [
            f"TRADE PROPOSAL: {side.upper()} {qty} shares of {ticker}",
            f"DECLARED INTENT: primary_action={primary}",
            f"PERMITTED ACTIONS: {permitted}",
            f"PROHIBITED ACTIONS: {prohibited}",
            f"GRC CONSTRAINTS:\n{grc_prompt}",
            f"POLICY: max_per_order=9, allowed_tickers=[AAPL,TSLA,NVDA,SPY,QQQ,VOO,IVV]\n"
            f"RULE: If quantity is 10 or more, verdict must be BLOCK.\n"
            f"RULE: If ticker is not in the allowed list, verdict must be BLOCK.\n"
            f"Always state the specific reason.",
        ]
        if round_num == 2 and others:
            parts.append(
                "OTHER AGENTS (Round 1):\n"
                f"  Analyst: {others.get('analyst', {}).get('reason', 'N/A')}\n"
                f"  Risk: {others.get('risk', {}).get('reason', 'N/A')}"
            )
            parts.append("Consider their perspectives and finalize your compliance assessment.")
        parts.append("Respond ONLY with valid JSON.")
        return "\n\n".join(parts)

    def _validate_response(self, data: dict, round_num: int) -> dict:
        """Validate response and set compliance-specific confidence default."""
        result = super()._validate_response(data, round_num)
        # Compliance default confidence is 70
        if not data.get("confidence"):
            result["confidence"] = 70
        return result
