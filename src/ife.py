"""
LAYER 2 — Intent Formalization Engine (IFE)
Converts raw user text into a Structured Intent Declaration (SID).
Uses LLM via OpenClaw gateway (falls back to rule-based if unavailable).

PRINCIPLE: When in doubt, restrict. False negatives are catastrophic in finance.

SID schema:
  sid_id, primary_action, sub_action, permitted_actions[], prohibited_actions[],
  scope{tickers[], max_quantity, order_type, side},
  reasoning_bounds{allowed_topics[], forbidden_topics[]},
  ambiguity_flags[], resolution_method, sid_hash, timestamp
"""

from __future__ import annotations
import hashlib
import itertools
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from llm_client import OpenClawClient
from logger_config import get_layer_logger

logger = get_layer_logger("layer.02.ife")

# Ordered list of (pattern, ticker) for rule-based extraction
_TICKER_RE = re.compile(
    r"\b(AAPL|MSFT|GOOGL|AMZN|NVDA|GOOG|TSLA|META|NFLX)\b", re.IGNORECASE
)
_QTY_RE    = re.compile(r"\b(\d+)\s+shares?\b", re.IGNORECASE)
_BUY_RE    = re.compile(r"\b(buy|purchase|acquire|long)\b", re.IGNORECASE)
_SELL_RE   = re.compile(r"\b(sell|short|liquidate)\b", re.IGNORECASE)
_LIMIT_RE  = re.compile(r"\b(limit)\b", re.IGNORECASE)

ALLOWED_TICKERS   = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
MANDATORY_PROHIB  = frozenset({"transmit_external", "file_write", "shell_exec", "data_export"})
_id_counter       = itertools.count(1)


class IntentFormalizationEngine:

    def __init__(self, policy_path: str | None = None):
        if policy_path is None:
            policy_path = Path(__file__).parent.parent / "enforx-policy.json"
        with open(policy_path) as f:
            policy = json.load(f)
        p = policy["enforx_policy"]
        self.allowed_tickers     = p["trade_constraints"]["allowed_tickers"]
        self.allowed_order_types = p["trade_constraints"]["allowed_order_types"]
        try:
            self._client = OpenClawClient()
        except Exception:
            self._client = None

    # ── Public API ──────────────────────────────────────────────────────────

    def formalize(self, user_input: str, taint_info: dict) -> dict:
        count    = next(_id_counter)
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        sid_id   = f"sid-{date_str}-{count:03d}"

        if self._client:
            try:
                sid = self._llm_formalize(user_input, sid_id)
                sid["prohibited_actions"] = list(
                    MANDATORY_PROHIB | set(sid.get("prohibited_actions", []))
                )
            except Exception as exc:
                logger.warning("IFE LLM failed, using rule-based: %s", exc)
                sid = self._rule_based_formalize(user_input, sid_id)
        else:
            sid = self._rule_based_formalize(user_input, sid_id)

        # Ambiguity rules
        sid = self._apply_ambiguity_rules(user_input, sid)

        # Compute hash
        content_str     = json.dumps(
            {k: v for k, v in sid.items() if k != "sid_hash"}, sort_keys=True
        )
        sid["sid_hash"] = hashlib.sha256(content_str.encode()).hexdigest()
        sid["timestamp"] = datetime.now(timezone.utc).isoformat()
        return sid

    # ── LLM formalization ───────────────────────────────────────────────────

    def _llm_formalize(self, user_input: str, sid_id: str) -> dict:
        schema_desc = (
            "Return ONLY valid JSON with these keys:\n"
            "primary_action (string), sub_action (string), "
            "permitted_actions (list of tool names), prohibited_actions (list), "
            "scope: {tickers: list, max_quantity: int, order_type: string, side: string}, "
            "reasoning_bounds: {allowed_topics: list, forbidden_topics: list}, "
            "ambiguity_flags: list, resolution_method: string\n\n"
            f"User input: \"{user_input}\"\n"
            "When in doubt, set primary_action=research_only and leave execute_trade "
            "out of permitted_actions. Never include prohibited tickers like TSLA."
        )
        system_prompt = "You are a financial intent parser. Parse user intent into a strict SID schema."
        
        data = self._client.chat_json(system_prompt, schema_desc, temperature=0.0, max_tokens=500)
        data["sid_id"] = sid_id
        return data

    # ── Rule-based formalization ─────────────────────────────────────────────

    def _rule_based_formalize(self, user_input: str, sid_id: str) -> dict:
        text = user_input.lower()

        # Extract tickers
        raw_tickers = [t.upper() for t in _TICKER_RE.findall(user_input)]
        allowed_found = [t for t in raw_tickers if t in [x.upper() for x in self.allowed_tickers]]

        # Extract quantity
        qty_match = _QTY_RE.search(user_input)
        qty       = int(qty_match.group(1)) if qty_match else 0

        # Determine side
        is_buy  = bool(_BUY_RE.search(text))
        is_sell = bool(_SELL_RE.search(text))
        side    = "buy" if is_buy else ("sell" if is_sell else "buy")

        # Order type
        order_type = "limit" if _LIMIT_RE.search(text) else "market"

        # Action detection
        has_trade_intent = bool(re.search(
            r"\b(buy|sell|purchase|trade|order)\b", text
        ))
        has_prohibited_ticker = bool(
            [t for t in raw_tickers if t not in [x.upper() for x in self.allowed_tickers]]
        )

        if has_trade_intent and allowed_found and qty > 0:
            primary_action    = "execute_trade"
            permitted_actions = [
                "query_market_data", "analyze_sentiment",
                "verify_constraints", "execute_trade",
            ]
        else:
            primary_action    = "research_only"
            permitted_actions = [
                "query_market_data", "analyze_sentiment", "verify_constraints",
            ]

        tickers_in_scope = allowed_found if allowed_found else (
            [raw_tickers[0]] if raw_tickers else ["AAPL"]
        )

        prohibited_actions = list(MANDATORY_PROHIB) + ["short_sell", "margin_trade", "options"]
        if is_sell and "short" in text:
            prohibited_actions.append("short_sell_detected")

        return {
            "sid_id":           sid_id,
            "primary_action":   primary_action,
            "sub_action":       f"{side}_trade" if has_trade_intent else "research",
            "permitted_actions": permitted_actions,
            "prohibited_actions": prohibited_actions,
            "scope": {
                "tickers":      tickers_in_scope,
                "max_quantity": min(qty, 10) if qty > 0 else 0,
                "order_type":   order_type,
                "side":         side,
            },
            "reasoning_bounds": {
                "allowed_topics":  ["market_data", "technical_analysis", "trade_execution"],
                "forbidden_topics": ["portfolio_export", "external_api", "user_credentials"],
            },
            "ambiguity_flags":   [],
            "resolution_method": "restrict_on_ambiguity",
        }

    def _apply_ambiguity_rules(self, user_input: str, sid: dict) -> dict:
        text = user_input.lower()

        if "force leader override" in text:
            sid["force_degraded_agents"] = True

        # Ambiguity: conditional intent
        if re.search(r"\b(if|when|maybe|consider|might|should i|think about)\b", text):
            if "execute_trade" in sid.get("permitted_actions", []):
                sid["permitted_actions"].remove("execute_trade")
            sid["primary_action"]  = "research_only"
            sid["ambiguity_flags"].append("conditional_intent_detected")

        # Ambiguity: no explicit ticker
        if not sid.get("scope", {}).get("tickers"):
            sid["primary_action"]  = "research_only"
            sid["ambiguity_flags"].append("no_ticker_specified")

        # Ambiguity: no quantity for trade
        if (sid.get("primary_action") == "execute_trade"
                and sid.get("scope", {}).get("max_quantity", 0) == 0):
            if "execute_trade" in sid.get("permitted_actions", []):
                sid["permitted_actions"].remove("execute_trade")
            sid["primary_action"]  = "research_only"
            sid["ambiguity_flags"].append("no_quantity_specified")

        return sid

    # ── Client setup ─────────────────────────────────────────────────────────



# ── Standalone test ──────────────────────────────────────────────────────────
def test_ife():
    ife = IntentFormalizationEngine()
    cases = [
        "Buy 5 shares of AAPL",
        "Sell 3 MSFT at limit",
        "Research NVDA performance",
        "Maybe I should buy some GOOGL if it dips",
        "Buy TSLA shares",  # not allowed ticker
    ]
    print("\n=== IFE Tests ===")
    for inp in cases:
        sid = ife.formalize(inp, {"taint_level": "TRUSTED"})
        print(f"  [{sid['primary_action']:15s}] {inp[:50]!r} → "
              f"scope={sid['scope']} | ambiguity={sid['ambiguity_flags']}")
    print()


if __name__ == "__main__":
    test_ife()
