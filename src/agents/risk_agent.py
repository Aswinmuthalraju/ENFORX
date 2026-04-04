"""
RiskAgent — Devil's Advocate
Role: Find every reason this trade could go wrong or violate policy. Be adversarial.
Special power: if confidence > 80 on BLOCK → instant veto regardless of other agents.
"""

from __future__ import annotations
import logging
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from llm_client import OpenClawClient

logger = logging.getLogger(__name__)

PERSONA = (
    "You are a risk officer reviewing a proposed trade for an autonomous AI agent. "
    "Your SOLE job is to find every reason this trade could go wrong, violate policy, "
    "cause financial harm, or expose the firm to liability. "
    "Be adversarial and specific: cite concentration risk, velocity, sector overlap, "
    "market timing, or any policy ceiling being approached. "
    "You must output a JSON object with exactly these keys: "
    "verdict (PROCEED/BLOCK/MODIFY), confidence (0-100 integer), "
    "reason (string, 1-3 sentences), suggested_modification (string or null). "
    "If you output BLOCK with confidence > 80, your vote is a VETO — pipeline stops immediately."
)

class RiskAgent:
    NAME = "risk"

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
        result = self._llm.chat_json(PERSONA, user_msg, temperature=0.2, max_tokens=400)
        return self._validate_response(result, round_num)

    def _build_prompt(self, sid, grc_prompt, others, round_num):
        ticker = sid.get("scope", {}).get("tickers", ["?"])[0]
        qty    = sid.get("scope", {}).get("max_quantity", 0)
        side   = sid.get("scope", {}).get("side", "buy")
        parts  = [
            f"TRADE PROPOSAL: {side.upper()} {qty} shares of {ticker}",
            f"GRC CONSTRAINTS:\n{grc_prompt}",
            f"POLICY: max_per_order=10, allowed_tickers=[AAPL,MSFT,GOOGL,AMZN,NVDA], "
            f"no short_sell/margin/options",
        ]
        if round_num == 2 and others:
            parts.append(
                "OTHER AGENTS (Round 1):\n"
                f"  Analyst: {others.get('analyst', {}).get('reason', 'N/A')}\n"
                f"  Compliance: {others.get('compliance', {}).get('reason', 'N/A')}"
            )
            parts.append("Respond to their arguments. Stand by your risk assessment if warranted.")
        parts.append("Respond ONLY with valid JSON.")
        return "\n\n".join(parts)

    def _validate_response(self, data: dict, round_num: int) -> dict:
        verdict = str(data.get("verdict", "PROCEED")).upper()
        if verdict not in ("PROCEED", "BLOCK", "MODIFY"):
            verdict = "PROCEED"
        result = {
            "verdict":               verdict,
            "confidence":            int(data.get("confidence", 50)),
            "reason":                str(data.get("reason", "")),
            "suggested_modification": data.get("suggested_modification"),
            "source":                "llm",
            "llm_available":         True,
        }
        if round_num == 2:
            result["response_to_others"] = str(data.get("response_to_others", ""))
        return result
