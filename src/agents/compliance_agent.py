"""
ComplianceAgent — Policy Enforcer
Role: Check if the trade aligns with declared user intent, policy rules,
and regulatory constraints. Flag anything suspicious.
"""

from __future__ import annotations
import logging
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from llm_client import OpenClawClient

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

class ComplianceAgent:
    NAME = "compliance"

    def __init__(self):
        self._llm = OpenClawClient()

    def deliberate(
        self,
        sid: dict,
        grc_prompt: str,
        others_output: dict | None = None,
        round_num: int = 1,
    ) -> dict:
        user_msg = self._build_prompt(sid, grc_prompt, others_output, round_num)
        result = self._llm.chat_json(PERSONA, user_msg, temperature=0.1, max_tokens=400)
        return self._validate_response(result, round_num)

    def _build_prompt(self, sid, grc_prompt, others, round_num):
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
        verdict = str(data.get("verdict", "PROCEED")).upper()
        if verdict not in ("PROCEED", "BLOCK", "MODIFY"):
            verdict = "PROCEED"
        result = {
            "verdict":               verdict,
            "confidence":            int(data.get("confidence", 70)),
            "reason":                str(data.get("reason", "")),
            "suggested_modification": data.get("suggested_modification"),
            "source":                "llm",
            "llm_available":         True,
        }
        if round_num == 2:
            result["response_to_others"] = str(data.get("response_to_others", ""))
        return result
