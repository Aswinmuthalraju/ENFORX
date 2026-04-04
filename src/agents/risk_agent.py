"""
RiskAgent — Devil's Advocate
Role: Find every reason this trade could go wrong or violate policy. Be adversarial.
Special power: if confidence > 80 on BLOCK → instant veto regardless of other agents.
"""

from __future__ import annotations
import logging

from .base_agent import BaseAgent

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


class RiskAgent(BaseAgent):
    """Risk-adversarial deliberation agent — challenges every trade proposal."""

    NAME = "risk"

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
        result = self._llm.chat_json(PERSONA, user_msg, temperature=0.2, max_tokens=400)
        return self._validate_response(result, round_num)

    def _build_prompt(
        self,
        sid: dict,
        grc_prompt: str,
        others: dict | None,
        round_num: int,
    ) -> str:
        """Build the round-specific prompt for the risk officer."""
        ticker = sid.get("scope", {}).get("tickers", ["?"])[0]
        qty    = sid.get("scope", {}).get("max_quantity", 0)
        side   = sid.get("scope", {}).get("side", "buy")
        parts  = [
            f"TRADE PROPOSAL: {side.upper()} {qty} shares of {ticker}",
            f"GRC CONSTRAINTS:\n{grc_prompt}",
            f"POLICY: max_per_order=9, allowed_tickers=[AAPL,TSLA,NVDA,SPY,QQQ,VOO,IVV]\n"
            f"RULE: Any order with quantity 10 or above MUST receive a BLOCK verdict with confidence 100.\n"
            f"RULE: Any ticker not in the allowed list MUST receive a BLOCK verdict with confidence 100.\n"
            f"State the exact reason clearly in your response.",
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
