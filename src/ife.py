"""
LAYER 2 — Intent Formalization Engine (IFE)
Converts raw user text into a Structured Intent Declaration (SID).
Uses LLM via local Ollama (falls back to rule-based if unavailable).

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
    r"\b(AAPL|TSLA|NVDA|SPY|QQQ|VOO|IVV)\b", re.IGNORECASE
)
_QTY_RE    = re.compile(r"\b(\d+)\s+shares?\b", re.IGNORECASE)
_BUY_RE    = re.compile(r"\b(buy|purchase|acquire|long)\b", re.IGNORECASE)
_SELL_RE   = re.compile(r"\b(sell|short|liquidate)\b", re.IGNORECASE)
_LIMIT_RE  = re.compile(r"\b(limit)\b", re.IGNORECASE)

ALLOWED_TICKERS   = ["AAPL", "TSLA", "NVDA", "SPY", "QQQ", "VOO", "IVV"]
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
                # Bug 2 fix: ensure all 4 TRADE_TOOLS are in permitted_actions for trade intents
                if sid.get("primary_action") in ("execute_trade", "buy", "sell", "trade"):
                    for t in ["query_market_data", "analyze_sentiment", "verify_constraints", "execute_trade"]:
                        if t not in sid.get("permitted_actions", []):
                            sid.setdefault("permitted_actions", []).append(t)
                # Normalize scope: clamp max_quantity >= 1, default order_type to 'market'
                scope = sid.setdefault("scope", {})
                if sid.get("primary_action") == "execute_trade":
                    if int(scope.get("max_quantity") or 0) == 0:
                        scope["max_quantity"] = 1
                if not scope.get("order_type"):
                    scope["order_type"] = "market"
            except Exception as exc:
                logger.warning("IFE LLM failed, using rule-based: %s", exc)
                sid = self._rule_based_formalize(user_input, sid_id)
        else:
            sid = self._rule_based_formalize(user_input, sid_id)

        # Post-generation validation: force execute_trade into permitted_actions
        # whenever primary_action is execute_trade — LLMs sometimes forget it
        if sid.get("primary_action") == "execute_trade":
            if "execute_trade" not in sid.get("permitted_actions", []):
                logger.warning("IFE: execute_trade missing from permitted_actions — force-adding")
                sid.setdefault("permitted_actions", []).append("execute_trade")

        # Unrecognized-ticker detection: flag tokens that look like tickers but aren't known
        sid = self._flag_unrecognized_tickers(user_input, sid)

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
            f"User input: \"{user_input}\"\n\n"
            "CLASSIFICATION RULES:\n"
            "- Set primary_action=execute_trade when the user uses a clear trade verb "
            "(buy/sell/purchase) with a specific ticker AND quantity — even if a price "
            "condition is given (e.g. 'if price is under 200' is a price trigger, NOT ambiguity).\n"
            "- Set primary_action=research_only ONLY when the user expresses uncertainty "
            "('maybe', 'should I', 'consider', 'think about') or gives no specific action.\n"
            "- A price condition like 'if price < X' signals order_type=limit, not ambiguity.\n"
            "- Never include prohibited tickers like TSLA.\n\n"
            "IMPORTANT: Allowed tickers are ONLY: AAPL, TSLA, NVDA, SPY, QQQ, VOO, IVV. "
            "Any other ticker is invalid and must be flagged with ambiguity_flags: ['unrecognized_ticker'] "
            "and resolution_method: 'block_on_ambiguity'.\n\n"
            "IMPORTANT: For any BUY or SELL command, permitted_actions MUST always include ALL of: "
            "query_market_data, analyze_sentiment, verify_constraints, execute_trade. "
            "Never omit execute_trade for trade commands. "
            "Only exclude execute_trade for research_only commands."
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

        # Extract quantity — default to 1 (never 0) so PIAV never blocks on missing qty
        qty_match = _QTY_RE.search(user_input)
        qty       = int(qty_match.group(1)) if qty_match else 1  # Bug 3 fix: default to 1

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

        # Bug 2 fix: TRADE_TOOLS always present for trade intents
        TRADE_TOOLS = [
            "query_market_data", "analyze_sentiment",
            "verify_constraints", "execute_trade",
        ]

        if has_trade_intent and allowed_found:
            primary_action    = "execute_trade"
            permitted_actions = list(TRADE_TOOLS)  # always all 4
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

        # Bug 3 fix: max_quantity always >= 1 for trade intents
        safe_qty = max(min(qty, 9), 1)

        return {
            "sid_id":           sid_id,
            "primary_action":   primary_action,
            "sub_action":       f"{side}_trade" if has_trade_intent else "research",
            "permitted_actions": permitted_actions,
            "prohibited_actions": prohibited_actions,
            "scope": {
                "tickers":      tickers_in_scope,
                "max_quantity": safe_qty if primary_action == "execute_trade" else (min(qty, 9) if qty > 0 else 0),
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

        # Ambiguity: conditional intent — only when conditional PRECEDES the trade verb
        # e.g. "maybe buy AAPL" → ambiguous; "buy AAPL if price < 200" → NOT ambiguous
        conditional_match = re.search(r"\b(if|when|maybe|consider|might|should i|think about)\b", text)
        trade_verb_match  = re.search(r"\b(buy|sell|purchase|trade|order)\b", text)
        if conditional_match and (not trade_verb_match or conditional_match.start() < trade_verb_match.start()):
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

        # Quantity validation: >= 10 is blocked
        qty = int(sid.get("scope", {}).get("max_quantity", 0))
        if qty >= 10:
            sid.setdefault("ambiguity_flags", []).append("quantity_exceeded")
            sid["resolution_method"] = "block_on_ambiguity"

        return sid

    def _flag_unrecognized_tickers(self, user_input: str, sid: dict) -> dict:
        """Detect token-like words (ALL_CAPS or mixed-case, 2-6 chars) that look like
        ticker symbols but are not in the known allowed list. Flags them so
        downstream layers can surface a helpful error and block cleanly."""
        # All tickers we recognise (allowed + common known ones)
        known_tickers = {
            "AAPL", "TSLA", "NVDA", "SPY", "QQQ", "VOO", "IVV",
        }
        # Look for capitalised word-tokens that smell like tickers
        candidates = re.findall(r"\b([A-Z][A-Z0-9]{1,5})\b", user_input)
        # Also accept title-case single words of 2–6 chars after a trade verb
        trade_context = re.search(r"\b(buy|sell|purchase|trade)\b", user_input.lower())
        if trade_context:
            candidates += re.findall(r"\b([A-Z][a-z]{1,5})\b", user_input)
        unrecognised = [
            c.upper() for c in candidates
            if c.upper() not in known_tickers
            and c.upper() not in ("OF", "IN", "AT", "THE", "BUY", "SELL",
                                   "SHARES", "SHARE", "STOCK", "A", "AN",
                                   "I", "MY", "FOR", "AND", "OR")
        ]
        scope_tickers = [t.upper() for t in sid.get("scope", {}).get("tickers", [])]
        
        # Check if any ticker in scope is unknown
        unknown_in_scope = [t for t in scope_tickers if t not in known_tickers]
        if unknown_in_scope:
            logger.warning("IFE: unauthorized ticker(s) in scope: %s", unknown_in_scope)
            sid.setdefault("ambiguity_flags", []).append("unrecognized_ticker")
            sid["resolution_method"] = "block_on_ambiguity"
            return sid

        bad = [t for t in unrecognised if t not in known_tickers and t not in scope_tickers]
        if bad:
            logger.warning("IFE: unrecognized ticker-like token(s): %s", bad)
            sid.setdefault("ambiguity_flags", []).append("unrecognized_ticker")
            sid["unrecognized_tickers"] = bad
            sid["resolution_method"] = "block_on_ambiguity"
        return sid

    # ── Client setup ─────────────────────────────────────────────────────────



# ── Standalone test ──────────────────────────────────────────────────────────
def test_ife():
    ife = IntentFormalizationEngine()
    cases = [
        "Buy 5 shares of AAPL",
        "Sell 3 TSLA at limit",
        "Research NVDA performance",
        "Maybe I should buy some SPY if it dips",
        "Buy MSFT shares",  # not allowed ticker
    ]
    print("\n=== IFE Tests ===")
    for inp in cases:
        sid = ife.formalize(inp, {"taint_level": "TRUSTED"})
        print(f"  [{sid['primary_action']:15s}] {inp[:50]!r} → "
              f"scope={sid['scope']} | ambiguity={sid['ambiguity_flags']}")
    print()


if __name__ == "__main__":
    test_ife()
