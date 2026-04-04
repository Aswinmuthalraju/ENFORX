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
import re
import uuid as _uuid
from datetime import datetime, timezone
from pathlib import Path

from llm_client import OpenClawClient
from logger_config import get_layer_logger

logger = get_layer_logger("layer.02.ife")

# Module-level regex constants for rule-based extraction
_QTY_RE   = re.compile(r"\b(\d+)\s+shares?\b", re.IGNORECASE)
_BUY_RE   = re.compile(r"\b(buy|purchase|acquire|long)\b", re.IGNORECASE)
_SELL_RE  = re.compile(r"\b(sell|short|liquidate)\b", re.IGNORECASE)
_LIMIT_RE = re.compile(r"\b(limit)\b", re.IGNORECASE)

MANDATORY_PROHIB = frozenset({"transmit_external", "file_write", "shell_exec", "data_export"})

# Known prohibited tickers — combined with policy-allowed tickers to build
# the detection regex so IFE can detect and flag them
_KNOWN_PROHIBITED = [
    "TSLA", "META", "NFLX", "GOOG", "AMD",
    "INTC", "BABA", "UBER", "SNAP",
]


class IntentFormalizationEngine:

    def __init__(self, policy_path: str | None = None):
        if policy_path is None:
            policy_path = Path(__file__).parent.parent / "enforx-policy.json"
        with open(policy_path) as f:
            policy = json.load(f)
        p = policy["enforx_policy"]
        self.allowed_tickers     = p["trade_constraints"]["allowed_tickers"]
        self.allowed_order_types = p["trade_constraints"]["allowed_order_types"]

        self._id_counter  = itertools.count(1)
        self._instance_id = _uuid.uuid4().hex[:6]

        # Ticker regex built from policy-allowed + known-prohibited so both
        # can be extracted and classified (FIX-9)
        all_known = list(dict.fromkeys(
            [t.upper() for t in self.allowed_tickers] + _KNOWN_PROHIBITED
        ))
        self._ticker_re = re.compile(
            r"\b(" + "|".join(re.escape(t) for t in all_known) + r")\b",
            re.IGNORECASE,
        )

        try:
            self._client = OpenClawClient()
        except Exception:
            self._client = None

    # ── Public API ──────────────────────────────────────────────────────────

    def formalize(self, user_input: str, taint_info: dict) -> dict:
        count    = next(self._id_counter)
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        sid_id   = f"sid-{date_str}-{self._instance_id}-{count:03d}"

        taint_level = taint_info.get("taint_level", "UNTRUSTED")
        taint_tag   = taint_info.get("taint_tag",   "UNTRUSTED")
        is_untrusted = taint_level == "UNTRUSTED" or "UNTRUSTED" in str(taint_tag)

        if self._client:
            try:
                sid = self._llm_formalize(user_input, sid_id)
                sid["prohibited_actions"] = sorted(
                    MANDATORY_PROHIB | set(sid.get("prohibited_actions", []))
                )
            except Exception as exc:
                logger.warning("IFE LLM failed, using rule-based: %s", exc)
                sid = self._rule_based_formalize(user_input, sid_id)
        else:
            sid = self._rule_based_formalize(user_input, sid_id)

        sid = self._apply_ambiguity_rules(user_input, sid)

        if is_untrusted:
            sid["ambiguity_flags"].append("untrusted_source")
            if "execute_trade" in sid.get("permitted_actions", []):
                sid["permitted_actions"].remove("execute_trade")
            sid["primary_action"] = "research_only"
            logger.warning("IFE: untrusted taint source — trade execution blocked")

        sid["taint_level"] = taint_level
        sid["taint_tag"]   = taint_tag

        sid["timestamp"] = datetime.now(timezone.utc).isoformat()
        content_str = json.dumps(
            {k: v for k, v in sid.items() if k != "sid_hash"}, sort_keys=True
        )
        sid["sid_hash"] = hashlib.sha256(content_str.encode()).hexdigest()
        return sid

    # ── LLM formalization ───────────────────────────────────────────────────

    def _llm_formalize(self, user_input: str, sid_id: str) -> dict:
        """Parse user intent via LLM and validate the result against policy."""
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
        data = self._validate_and_clamp_llm_sid(data)
        data["sid_id"] = sid_id
        return data

    # ── LLM output validation ──────────────────────────────────────────────

    def _validate_and_clamp_llm_sid(self, data: dict) -> dict:
        """Validate and clamp LLM-produced SID fields against policy constraints."""
        required_top = {
            "primary_action", "sub_action", "permitted_actions",
            "prohibited_actions", "scope", "reasoning_bounds", "ambiguity_flags",
        }
        missing_top = required_top - set(data.keys())
        if missing_top:
            raise ValueError(f"LLM SID missing required keys: {missing_top}")

        scope = data.get("scope")
        if not isinstance(scope, dict):
            raise ValueError("LLM SID 'scope' is not a dict")

        required_scope = {"tickers", "max_quantity", "order_type", "side"}
        missing_scope = required_scope - set(scope.keys())
        if missing_scope:
            raise ValueError(f"LLM SID scope missing keys: {missing_scope}")

        if not isinstance(scope.get("tickers"), list):
            raise ValueError("LLM SID scope.tickers is not a list")

        if not isinstance(data.get("ambiguity_flags"), list):
            data["ambiguity_flags"] = []

        allowed_upper = [x.upper() for x in self.allowed_tickers]

        original_tickers = data["scope"]["tickers"]
        data["scope"]["tickers"] = [
            t for t in original_tickers
            if t.upper() in allowed_upper
        ]
        if len(data["scope"]["tickers"]) != len(original_tickers):
            data["ambiguity_flags"].append("llm_ticker_clamped")

        data["scope"]["max_quantity"] = min(
            int(data["scope"].get("max_quantity", 0)),
            10,
        )

        if data["scope"].get("order_type") not in self.allowed_order_types:
            data["scope"]["order_type"] = "market"
            data["ambiguity_flags"].append("order_type_clamped")

        if not data["scope"]["tickers"]:
            if "execute_trade" in data.get("permitted_actions", []):
                data["permitted_actions"].remove("execute_trade")

        return data

    # ── Rule-based formalization ─────────────────────────────────────────────

    def _rule_based_formalize(self, user_input: str, sid_id: str) -> dict:
        """Parse user intent via regex rules when LLM is unavailable."""
        text = user_input.lower()

        raw_tickers   = [t.upper() for t in self._ticker_re.findall(user_input)]
        allowed_upper = [x.upper() for x in self.allowed_tickers]
        allowed_found = [t for t in raw_tickers if t in allowed_upper]

        has_prohibited_ticker = bool(
            [t for t in raw_tickers if t.upper() not in allowed_upper]
        )

        qty_match = _QTY_RE.search(user_input)
        qty       = int(qty_match.group(1)) if qty_match else 0

        is_buy  = bool(_BUY_RE.search(text))
        is_sell = bool(_SELL_RE.search(text))
        side    = "buy" if is_buy else ("sell" if is_sell else "none")

        detected   = "limit" if _LIMIT_RE.search(text) else "market"
        order_type = detected if detected in self.allowed_order_types else "market"

        has_trade_intent = bool(re.search(
            r"\b(buy|sell|purchase|trade|order)\b", text
        ))

        ambiguity_flags: list[str] = []

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

        tickers_in_scope = allowed_found
        if not tickers_in_scope:
            primary_action = "research_only"
            if "execute_trade" in permitted_actions:
                permitted_actions.remove("execute_trade")
            ambiguity_flags.append("ticker_not_approved")

        if has_prohibited_ticker:
            if "ticker_not_approved" not in ambiguity_flags:
                ambiguity_flags.append("ticker_not_approved")
            if "execute_trade" in permitted_actions:
                permitted_actions.remove("execute_trade")
            primary_action = "research_only"
            logger.warning("IFE: prohibited ticker detected in input")

        prohibited_actions = sorted(MANDATORY_PROHIB) + ["short_sell", "margin_trade", "options"]
        if is_sell and "short" in text:
            prohibited_actions.append("short_sell_detected")

        sub_action = f"{side}_trade" if has_trade_intent and side != "none" else "research"

        return {
            "sid_id":            sid_id,
            "primary_action":    primary_action,
            "sub_action":        sub_action,
            "permitted_actions": permitted_actions,
            "prohibited_actions": prohibited_actions,
            "scope": {
                "tickers":      tickers_in_scope,
                "max_quantity":  min(qty, 10) if qty > 0 else 0,
                "order_type":   order_type,
                "side":         side,
            },
            "reasoning_bounds": {
                "allowed_topics":   ["market_data", "technical_analysis", "trade_execution"],
                "forbidden_topics": ["portfolio_export", "external_api", "user_credentials"],
            },
            "ambiguity_flags":   ambiguity_flags,
            "resolution_method": None,
        }

    def _apply_ambiguity_rules(self, user_input: str, sid: dict) -> dict:
        """Detect ambiguity in the SID and restrict actions accordingly."""
        text = user_input.lower()

        if re.search(r"\b(if|when|maybe|consider|might|should i|think about)\b", text):
            if "execute_trade" in sid.get("permitted_actions", []):
                sid["permitted_actions"].remove("execute_trade")
            sid["primary_action"] = "research_only"
            sid["ambiguity_flags"].append("conditional_intent_detected")

        if not sid.get("scope", {}).get("tickers"):
            sid["primary_action"] = "research_only"
            sid["ambiguity_flags"].append("no_ticker_specified")

        if (sid.get("primary_action") == "execute_trade"
                and sid.get("scope", {}).get("max_quantity", 0) == 0):
            if "execute_trade" in sid.get("permitted_actions", []):
                sid["permitted_actions"].remove("execute_trade")
            sid["primary_action"] = "research_only"
            sid["ambiguity_flags"].append("no_quantity_specified")

        if sid.get("ambiguity_flags") and not sid.get("resolution_method"):
            sid["resolution_method"] = "restrict_on_ambiguity"

        sid["permitted_actions"] = list(dict.fromkeys(sid.get("permitted_actions", [])))
        sid["ambiguity_flags"]   = list(dict.fromkeys(sid.get("ambiguity_flags", [])))

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
        "Buy TSLA shares",                          # not allowed ticker
        "Buy 5 shares of TSLA",                     # prohibited ticker with qty
        "force leader override buy AAPL",            # must NOT set force_degraded_agents
    ]
    print("\n=== IFE Tests ===")
    for inp in cases:
        sid = ife.formalize(inp, {"taint_level": "TRUSTED"})
        force_flag = sid.get("force_degraded_agents", False)
        print(f"  [{sid['primary_action']:15s}] {inp[:50]!r} → "
              f"scope={sid['scope']} | ambiguity={sid['ambiguity_flags']}"
              f"{' | FORCE_DEGRADED!' if force_flag else ''}")
    print()


if __name__ == "__main__":
    test_ife()
