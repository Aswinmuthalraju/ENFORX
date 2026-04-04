"""
AnalystAgent — Bullish Researcher
Role: Argue FOR the trade. Find supporting evidence. Be specific.
"""

from __future__ import annotations
import logging
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from llm_client import OpenClawClient

logger = logging.getLogger(__name__)

PERSONA = (
    "You are a senior financial analyst reviewing a potential trade. "
    "Your SOLE job in this deliberation is to argue WHY this trade makes sense. "
    "Find supporting evidence: price momentum, sector trends, volume signals, "
    "valuation metrics, or fundamental catalysts. Be specific and quantitative. "
    "You must output a JSON object with exactly these keys: "
    "verdict (PROCEED/BLOCK/MODIFY), confidence (0-100 integer), "
    "reason (string, 1-3 sentences), suggested_modification (string or null)."
)

class AnalystAgent:
    NAME = "analyst"

    def __init__(self):
        self._llm = OpenClawClient()

    def deliberate(
        self,
        sid: dict,
        grc_prompt: str,
        others_output: dict | None = None,
        round_num: int = 1,
    ) -> dict:
        """Return {verdict, confidence, reason, response_to_others (round 2 only)}."""
        user_msg = self._build_prompt(sid, grc_prompt, others_output, round_num)
        
        # This WILL raise ConnectionError if Ollama is down.
        # The deliberation orchestrator handles the error.
        result = self._llm.chat_json(PERSONA, user_msg, temperature=0.3, max_tokens=400)
        return self._validate_response(result, round_num)

    def _build_prompt(self, sid, grc_prompt, others, round_num):
        ticker = sid.get("scope", {}).get("tickers", ["?"])[0]
        qty    = sid.get("scope", {}).get("max_quantity", 0)
        side   = sid.get("scope", {}).get("side", "buy")
        parts  = [
            f"TRADE PROPOSAL: {side.upper()} {qty} shares of {ticker}",
            f"GRC CONSTRAINTS:\n{grc_prompt}",
            f"SID SUMMARY: {sid.get('primary_action')} | scope={sid.get('scope')}",
        ]
        if round_num == 2 and others:
            parts.append(
                "OTHER AGENTS (Round 1):\n"
                f"  Risk: {others.get('risk', {}).get('reason', 'N/A')}\n"
                f"  Compliance: {others.get('compliance', {}).get('reason', 'N/A')}"
            )
            parts.append("Respond to their concerns while maintaining your bullish case.")
        parts.append("Respond ONLY with valid JSON.")
        return "\n\n".join(parts)

    def _validate_response(self, data: dict, round_num: int) -> dict:
        verdict = str(data.get("verdict", "PROCEED")).upper()
        if verdict not in ("PROCEED", "BLOCK", "MODIFY"):
            verdict = "PROCEED"
        result = {
            "verdict":               verdict,
            "confidence":            int(data.get("confidence", 65)),
            "reason":                str(data.get("reason", "")),
            "suggested_modification": data.get("suggested_modification"),
            "source":                "llm",
            "llm_available":         True,
        }
        if round_num == 2:
            result["response_to_others"] = str(data.get("response_to_others", ""))
        return result
