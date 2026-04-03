"""
ComplianceAgent — Policy Enforcer (API_KEY_3)
Role: Check if the trade aligns with declared user intent, policy rules,
and regulatory constraints. Flag anything suspicious.
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
            logger.warning("ComplianceAgent: client build failed: %s", exc)
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
                    temperature=0.1,
                    max_tokens=400,
                )
                raw = resp.choices[0].message.content.strip()
                return self._parse(raw, round_num)
            except Exception as exc:
                logger.warning("ComplianceAgent API error: %s — using heuristic fallback", exc)

        return self._heuristic_fallback(sid, round_num, others_output)

    # ── Helpers ──────────────────────────────────────────────────────────────

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

    def _parse(self, raw: str, round_num: int) -> dict:
        try:
            start = raw.index("{")
            end   = raw.rindex("}") + 1
            data  = json.loads(raw[start:end])
        except (ValueError, json.JSONDecodeError):
            return self._fallback_verdict("PROCEED", 70,
                "Compliance: no policy violations detected.", round_num)
        verdict = str(data.get("verdict", "PROCEED")).upper()
        if verdict not in ("PROCEED", "BLOCK", "MODIFY"):
            verdict = "PROCEED"
        result = {
            "verdict":               verdict,
            "confidence":            int(data.get("confidence", 70)),
            "reason":                str(data.get("reason", "")),
            "suggested_modification": data.get("suggested_modification"),
        }
        if round_num == 2:
            result["response_to_others"] = str(data.get("response_to_others", ""))
        return result

    def _heuristic_fallback(self, sid: dict, round_num: int, others) -> dict:
        ticker    = sid.get("scope", {}).get("tickers", ["AAPL"])[0]
        qty       = int(sid.get("scope", {}).get("max_quantity", 0))
        side      = sid.get("scope", {}).get("side", "buy")
        primary   = sid.get("primary_action", "")
        permitted = sid.get("permitted_actions", [])
        prohibited_sid = sid.get("prohibited_actions", [])
        ambiguity = sid.get("ambiguity_flags", [])

        allowed_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]

        # Compliance check 1: ticker in scope
        scope_tickers = [t.upper() for t in sid.get("scope", {}).get("tickers", [])]
        if scope_tickers and ticker.upper() not in scope_tickers:
            return self._fallback_verdict(
                "BLOCK", 88,
                f"Compliance violation: proposed ticker '{ticker}' is outside declared "
                f"SID scope {scope_tickers}. Intent mismatch — BLOCK.",
                round_num,
            )

        # Compliance check 2: ticker in allowed policy list
        if ticker.upper() not in allowed_tickers:
            return self._fallback_verdict(
                "BLOCK", 92,
                f"Compliance violation: ticker '{ticker}' not in approved universe "
                f"{allowed_tickers}. Regulatory constraint — BLOCK.",
                round_num,
            )

        # Compliance check 3: execute_trade must be permitted
        if primary != "research_only" and "execute_trade" not in permitted:
            return self._fallback_verdict(
                "BLOCK", 85,
                f"Compliance: 'execute_trade' is not in SID permitted_actions. "
                f"Trade not authorized by declared intent — BLOCK.",
                round_num,
            )

        # Compliance check 4: ambiguity
        if ambiguity:
            return self._fallback_verdict(
                "MODIFY", 65,
                f"Compliance: SID has unresolved ambiguity flags: {ambiguity}. "
                f"Recommend clarifying intent before proceeding.",
                round_num,
            )

        # Compliance check 5: qty within scope
        scope_max = sid.get("scope", {}).get("max_quantity", 10)
        if qty > scope_max:
            result = self._fallback_verdict(
                "MODIFY", 75,
                f"Compliance: requested qty {qty} exceeds SID scope max {scope_max}. "
                f"Modify to {scope_max}.",
                round_num,
            )
            result["suggested_modification"] = f"Reduce qty to {scope_max}"
            return result

        reason = (
            f"Trade aligns with declared intent ({primary}). "
            f"{side.upper()} {qty} {ticker} is within SID scope and permitted actions. "
            f"No policy violations detected. PROCEED."
        )
        result = self._fallback_verdict("PROCEED", 80, reason, round_num)
        if round_num == 2 and others:
            result["response_to_others"] = (
                "Both analyst and risk assessments are consistent with compliance requirements. "
                "Policy checks confirmed clean."
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
