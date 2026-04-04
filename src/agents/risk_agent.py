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
    "Your job is to check whether the trade violates policy constraints. "
    "If the trade is within policy limits, output PROCEED. "
    "Only output BLOCK if there is a genuine quantitative policy violation (wrong ticker, qty>=10, prohibited action). "
    "Do NOT block on market conditions, opinions, or speculative risk — only hard policy rules. "
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
        result = self._llm.chat_json(PERSONA, user_msg, temperature=0.05, max_tokens=400)
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
        allowed_tickers = ["AAPL", "TSLA", "NVDA", "SPY", "QQQ", "VOO", "IVV"]
        ticker_ok  = ticker.upper() in allowed_tickers
        qty_ok     = 0 < qty < 10
        parts  = [
            f"TRADE PROPOSAL: {side.upper()} {qty} shares of {ticker}",
            f"POLICY CHECK:\n"
            f"  - Allowed tickers: {allowed_tickers}\n"
            f"  - Ticker '{ticker}' is {'ALLOWED' if ticker_ok else 'NOT ALLOWED'}\n"
            f"  - Quantity {qty} is {'WITHIN LIMIT (max 9)' if qty_ok else 'EXCEEDS LIMIT (max 9)'}\n"
            f"  - Max per order: 9 shares\n"
            f"  - Prohibited actions: short_sell, margin_trade, options",
            f"RULE: If ticker is in allowed list AND qty is 1-9, verdict MUST be PROCEED.\n"
            f"RULE: If ticker is NOT in allowed list, verdict MUST be BLOCK with confidence 100.\n"
            f"RULE: If qty >= 10, verdict MUST be BLOCK with confidence 100.\n"
            f"GRC CONSTRAINTS:\n{grc_prompt}",
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
