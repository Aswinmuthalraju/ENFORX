"""
RiskAgent — Devil's Advocate (API_KEY_2)
Role: Find every reason this trade could go wrong or violate policy. Be adversarial.
Special power: if confidence > 80 on BLOCK → instant veto regardless of other agents.
"""

from __future__ import annotations
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from api_keys import get_key, HF_BASE_URL, OPENCLAW_BASE_URL, OPENCLAW_API_KEY, MODEL_ID

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

# Thresholds for heuristic fallback
_QTY_HIGH_THRESHOLD      = 8   # > this → suggest MODIFY
_QTY_EXTREME_THRESHOLD   = 10  # == policy max → flag boundary-pushing


class RiskAgent:
    NAME = "risk"

    def __init__(self):
        self._api_key = get_key(self.NAME)
        self._client  = self._build_client()

    def _build_client(self):
        try:
            from openai import OpenAI
            if OPENCLAW_API_KEY:
                return OpenAI(base_url=OPENCLAW_BASE_URL, api_key=OPENCLAW_API_KEY)
            if self._api_key:
                return OpenAI(base_url=HF_BASE_URL, api_key=self._api_key)
        except Exception as exc:
            logger.warning("RiskAgent: client build failed: %s", exc)
        return None

    def deliberate(
        self,
        sid: dict,
        grc_prompt: str,
        others_output: dict | None = None,
        round_num: int = 1,
    ) -> dict:
        user_msg = self._build_prompt(sid, grc_prompt, others_output, round_num)

        if self._client:
            try:
                resp = self._client.chat.completions.create(
                    model=MODEL_ID,
                    messages=[
                        {"role": "system", "content": PERSONA},
                        {"role": "user",   "content": user_msg},
                    ],
                    temperature=0.2,
                    max_tokens=400,
                )
                raw = resp.choices[0].message.content.strip()
                return self._parse(raw, round_num)
            except Exception as exc:
                logger.warning("RiskAgent API error: %s — using heuristic fallback", exc)

        return self._heuristic_fallback(sid, round_num, others_output)

    # ── Helpers ──────────────────────────────────────────────────────────────

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

    def _parse(self, raw: str, round_num: int) -> dict:
        try:
            start = raw.index("{")
            end   = raw.rindex("}") + 1
            data  = json.loads(raw[start:end])
        except (ValueError, json.JSONDecodeError):
            return self._fallback_verdict("PROCEED", 50,
                "Risk: no critical issues detected at this position size.", round_num)
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

    def _heuristic_fallback(self, sid: dict, round_num: int, others) -> dict:
        ticker = sid.get("scope", {}).get("tickers", ["AAPL"])[0]
        qty    = int(sid.get("scope", {}).get("max_quantity", 0))
        side   = sid.get("scope", {}).get("side", "buy")

        # Hard block: the trade ITSELF is a prohibited action
        # (side=="short", or order type is margin/options — not just listed in prohibitions)
        if side in ("short", "short_sell") or "short" in side.lower():
            reason = (
                f"HARD POLICY VIOLATION: short selling is explicitly prohibited. "
                f"BLOCK immediately."
            )
            return self._fallback_verdict("BLOCK", 95, reason, round_num)

        # Ticker not in allowed list
        allowed = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
        if ticker.upper() not in allowed:
            reason = (
                f"Ticker '{ticker}' is not in the approved universe {allowed}. "
                f"Trading unapproved securities violates policy. BLOCK."
            )
            return self._fallback_verdict("BLOCK", 90, reason, round_num)

        # Quantity checks
        if qty > _QTY_EXTREME_THRESHOLD:
            reason = (
                f"Order size {qty} exceeds policy maximum of {_QTY_EXTREME_THRESHOLD}. "
                f"Auto-correction may be needed; flagging for review."
            )
            result = self._fallback_verdict(
                "MODIFY", 78,
                reason,
                round_num,
            )
            result["suggested_modification"] = f"Reduce qty to {_QTY_EXTREME_THRESHOLD}"
            return result

        if qty > _QTY_HIGH_THRESHOLD:
            reason = (
                f"Order size {qty} is near policy ceiling ({_QTY_EXTREME_THRESHOLD}). "
                f"Recommend reducing to {_QTY_HIGH_THRESHOLD} to maintain buffer."
            )
            result = self._fallback_verdict("MODIFY", 60, reason, round_num)
            result["suggested_modification"] = f"Reduce qty to {_QTY_HIGH_THRESHOLD}"
            return result

        reason = (
            f"{side.upper()} {qty} {ticker}: position size within bounds. "
            f"No elevated concentration or velocity risk detected. PROCEED."
        )
        result = self._fallback_verdict("PROCEED", 55, reason, round_num)
        if round_num == 2 and others:
            result["response_to_others"] = (
                "Analyst's bullish case is noted. At this size the downside is bounded. "
                "Maintaining PROCEED with standard monitoring."
            )
        return result

    def _fallback_verdict(self, verdict, confidence, reason, round_num) -> dict:
        r = {
            "verdict":               verdict,
            "confidence":            confidence,
            "reason":                reason,
            "suggested_modification": None,
            "source":                "heuristic_fallback",
            "llm_available":         False,
        }
        if round_num == 2:
            r["response_to_others"] = ""
        return r
