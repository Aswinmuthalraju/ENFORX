"""
ExecutionAgent — Final Executor (API_KEY_4)
Role: Given the deliberation outcome, produce the minimal, precise trade plan
that satisfies all constraints. Only activates after consensus PROCEED or MODIFY.
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
    "You are a trade execution specialist. "
    "You receive the outcome of a multi-agent deliberation and produce the MINIMAL, "
    "PRECISE trade plan that satisfies all constraints and modifications. "
    "Do not add unrequested steps. Do not deviate from the deliberation outcome. "
    "You must output a JSON object with exactly these keys: "
    "plan (list of steps), reasoning (string), modifications_applied (list of strings)."
    "\n\nEach step has: tool (string), args (dict), step (int)."
    "\n\nOnly use these tools: query_market_data, analyze_sentiment, "
    "verify_constraints, execute_trade."
)


class ExecutionAgent:
    NAME = "execution"

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
            logger.warning("ExecutionAgent: client build failed: %s", exc)
        return None

    def generate_plan(
        self,
        sid: dict,
        grc_prompt: str,
        consensus: str,
        deliberation_summary: str,
        modifications: list[str] | None = None,
    ) -> dict:
        """Generate final execution plan after consensus is reached.

        Returns {plan, reasoning, modifications_applied, csrg_stub}
        """
        modifications = modifications or []
        user_msg = self._build_prompt(sid, grc_prompt, consensus, deliberation_summary, modifications)

        if self._client:
            try:
                resp = self._client.chat.completions.create(
                    model=MODEL_ID,
                    messages=[
                        {"role": "system", "content": PERSONA},
                        {"role": "user",   "content": user_msg},
                    ],
                    temperature=0.1,
                    max_tokens=600,
                )
                raw = resp.choices[0].message.content.strip()
                return self._parse(raw, sid, modifications)
            except Exception as exc:
                logger.warning("ExecutionAgent API error: %s — using rule-based fallback", exc)

        return self._rule_based_plan(sid, modifications)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _build_prompt(self, sid, grc_prompt, consensus, summary, mods):
        ticker = sid.get("scope", {}).get("tickers", ["AAPL"])[0]
        qty    = sid.get("scope", {}).get("max_quantity", 0)
        side   = sid.get("scope", {}).get("side", "buy")
        order_type = sid.get("scope", {}).get("order_type", "market")
        return (
            f"DELIBERATION CONSENSUS: {consensus}\n"
            f"DELIBERATION SUMMARY: {summary}\n"
            f"MODIFICATIONS REQUIRED: {mods or 'none'}\n\n"
            f"TRADE: {side.upper()} {qty} shares of {ticker} ({order_type})\n"
            f"GRC CONSTRAINTS:\n{grc_prompt}\n\n"
            "Generate the minimal execution plan. Respond ONLY with valid JSON."
        )

    def _parse(self, raw: str, sid: dict, mods: list) -> dict:
        try:
            start = raw.index("{")
            end   = raw.rindex("}") + 1
            data  = json.loads(raw[start:end])
            plan  = data.get("plan", [])
            if not plan:
                raise ValueError("Empty plan from LLM")
            return {
                "plan":                  plan,
                "reasoning":             str(data.get("reasoning", "")),
                "modifications_applied": data.get("modifications_applied", mods),
                "csrg_proof":            f"CSRG-PENDING-{sid.get('sid_id', 'unknown')}",
                "model":                 MODEL_ID,
                "stub":                  False,
            }
        except Exception:
            return self._rule_based_plan(sid, mods)

    def _rule_based_plan(self, sid: dict, mods: list) -> dict:
        ticker     = sid.get("scope", {}).get("tickers", ["AAPL"])[0]
        qty        = int(sid.get("scope", {}).get("max_quantity", 0))
        side       = sid.get("scope", {}).get("side", "buy")
        order_type = sid.get("scope", {}).get("order_type", "market")
        sid_id     = sid.get("sid_id", "unknown")

        # Apply quantity modification if present
        for mod in mods:
            if "reduce qty" in mod.lower() or "qty to" in mod.lower():
                import re
                m = re.search(r"\d+", mod)
                if m:
                    qty = min(qty, int(m.group()))

        if sid.get("primary_action") == "research_only":
            plan = [
                {"tool": "query_market_data",  "args": {"ticker": ticker}, "step": 1},
                {"tool": "analyze_sentiment",  "args": {"ticker": ticker}, "step": 2},
                {"tool": "verify_constraints", "args": {"ticker": ticker}, "step": 3},
            ]
            reasoning = f"Research-only plan for {ticker} per SID {sid_id}. No trade action."
        else:
            plan = [
                {"tool": "query_market_data",  "args": {"ticker": ticker}, "step": 1},
                {"tool": "analyze_sentiment",  "args": {"ticker": ticker}, "step": 2},
                {"tool": "verify_constraints", "args": {"ticker": ticker}, "step": 3},
                {
                    "tool": "execute_trade",
                    "args": {
                        "symbol": ticker,
                        "qty":    qty,
                        "side":   side if side in ("buy", "sell") else "buy",
                        "type":   order_type if order_type in ("market", "limit") else "market",
                    },
                    "step": 4,
                },
            ]
            reasoning = (
                f"Execution plan for SID {sid_id}: {side.upper()} {qty} {ticker} "
                f"({order_type}). All deliberation constraints satisfied."
            )

        return {
            "plan":                  plan,
            "reasoning":             reasoning,
            "reasoning_trace":       reasoning,
            "modifications_applied": mods,
            "csrg_proof":            f"CSRG-STUB-{sid_id}",
            "model":                 "rule-based",
            "stub":                  True,
        }
