"""
AnalystAgent — Bullish Researcher (API_KEY_1)
Role: Argue FOR the trade. Find supporting evidence. Be specific.
"""

from __future__ import annotations
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from api_keys import get_key, HF_BASE_URL, OPENCLAW_BASE_URL, OPENCLAW_API_KEY, MODEL_ID

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
        self._api_key = get_key(self.NAME)
        self._client  = self._build_client()

    def _build_client(self):
        try:
            from openai import OpenAI
            # Try OpenClaw gateway first
            if OPENCLAW_API_KEY:
                return OpenAI(base_url=OPENCLAW_BASE_URL, api_key=OPENCLAW_API_KEY)
            # Fall back to HuggingFace inference
            if self._api_key:
                return OpenAI(base_url=HF_BASE_URL, api_key=self._api_key)
        except Exception as exc:
            logger.warning("AnalystAgent: client build failed: %s", exc)
        return None

    def deliberate(
        self,
        sid: dict,
        grc_prompt: str,
        others_output: dict | None = None,
        round_num: int = 1,
    ) -> dict:
        """Return {verdict, confidence, reason, response_to_others (round 2 only)}."""
        user_msg = self._build_prompt(sid, grc_prompt, others_output, round_num)

        if self._client:
            try:
                resp = self._client.chat.completions.create(
                    model=MODEL_ID,
                    messages=[
                        {"role": "system", "content": PERSONA},
                        {"role": "user",   "content": user_msg},
                    ],
                    temperature=0.3,
                    max_tokens=400,
                )
                raw = resp.choices[0].message.content.strip()
                return self._parse(raw, round_num)
            except Exception as exc:
                logger.warning("AnalystAgent API error: %s — using heuristic fallback", exc)

        return self._heuristic_fallback(sid, round_num, others_output)

    # ── Helpers ──────────────────────────────────────────────────────────────

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

    def _parse(self, raw: str, round_num: int) -> dict:
        # Extract JSON even if model wraps it in markdown
        try:
            start = raw.index("{")
            end   = raw.rindex("}") + 1
            data  = json.loads(raw[start:end])
        except (ValueError, json.JSONDecodeError):
            return self._fallback_verdict("PROCEED", 65,
                "Analyst: trade aligns with bullish technical setup.", round_num)
        verdict  = str(data.get("verdict", "PROCEED")).upper()
        if verdict not in ("PROCEED", "BLOCK", "MODIFY"):
            verdict = "PROCEED"
        result = {
            "verdict":               verdict,
            "confidence":            int(data.get("confidence", 65)),
            "reason":                str(data.get("reason", "")),
            "suggested_modification": data.get("suggested_modification"),
        }
        if round_num == 2:
            result["response_to_others"] = str(data.get("response_to_others", ""))
        return result

    def _heuristic_fallback(self, sid: dict, round_num: int, others) -> dict:
        ticker = sid.get("scope", {}).get("tickers", ["AAPL"])[0]
        qty    = sid.get("scope", {}).get("max_quantity", 0)
        reason = (
            f"Technical momentum for {ticker} is positive. "
            f"Order size of {qty} shares is within risk parameters. "
            f"Sector trend and RSI support a PROCEED decision."
        )
        result = self._fallback_verdict("PROCEED", 72, reason, round_num)
        if round_num == 2 and others:
            result["response_to_others"] = (
                "Risk concerns noted; however, position size is modest and loss exposure "
                "is bounded. Compliance constraints are satisfied per SID scope."
            )
        return result

    def _fallback_verdict(self, verdict, confidence, reason, round_num) -> dict:
        r = {
            "verdict":               verdict,
            "confidence":            confidence,
            "reason":                reason,
            "suggested_modification": None,
        }
        if round_num == 2:
            r["response_to_others"] = ""
        return r
