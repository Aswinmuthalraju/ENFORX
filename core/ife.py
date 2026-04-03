"""
LAYER 2: Intent Formalization Engine (IFE)
Converts raw user text to a Structured Intent Declaration (SID).
Uses LLM (via openai SDK) to parse intent into structured JSON.
PRINCIPLE: When in doubt, restrict. False negatives are catastrophic in finance.
"""

from __future__ import annotations
import os
import json
import hashlib
import re
import itertools
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class IntentFormalizationEngine:

    MANDATORY_PROHIBITIONS = frozenset({
        "transmit_external", "file_write", "shell_exec", "data_export"
    })

    _REQUIRED_SID_KEYS = {
        "primary_action", "sub_action", "permitted_actions",
        "prohibited_actions", "scope", "reasoning_bounds", "ambiguity_flags",
    }

    _INJECTION_PATTERNS = re.compile(
        r"ignore previous|disregard|you are now|new instructions",
        re.IGNORECASE,
    )

    def __init__(self, policy_path: str = None):
        if policy_path is None:
            policy_path = Path(__file__).parent.parent / "enforx-policy.json"
        with open(policy_path) as f:
            policy = json.load(f)
        self.allowed_tickers = policy["enforx_policy"]["trade_constraints"]["allowed_tickers"]
        self.allowed_order_types = policy["enforx_policy"]["trade_constraints"]["allowed_order_types"]
        self._sid_counter = itertools.count(1)

        self._client = None
        self._setup_client()

    def _setup_client(self):
        try:
            from openai import OpenAI
            base_url = os.getenv("OPENCLAW_BASE_URL", "http://127.0.0.1:18789/v1")
            api_key = os.getenv("OPENCLAW_API_KEY", "not-set")
            self._client = OpenAI(base_url=base_url, api_key=api_key)
        except Exception:
            self._client = None

    def formalize(self, user_input: str, taint_info: dict) -> dict:
        """
        Convert raw user input to a Structured Intent Declaration (SID).
        Falls back to rule-based if LLM unavailable or parse fails.
        """
        count_val = next(self._sid_counter)
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        sid_id = f"sid-{date_str}-{count_val:03d}"

        if self._client:
            try:
                sid = self._llm_formalize(user_input, sid_id)
                sid["prohibited_actions"] = list(
                    self.MANDATORY_PROHIBITIONS | set(sid.get("prohibited_actions", []))
                )
            except Exception as exc:
                logger.warning("LLM formalization failed, falling back to rule-based: %s", exc)
                sid = self._rule_based_formalize(user_input, sid_id)
        else:
            sid = self._rule_based_formalize(user_input, sid_id)

        sid = self._apply_ambiguity_rules(user_input, sid)

        hash_content = json.dumps({
            "scope": sid["scope"],
            "primary_action": sid["primary_action"],
            "sub_action": sid["sub_action"]
        }, sort_keys=True)
        sid["sid_hash"] = "sha256:" + hashlib.sha256(hash_content.encode()).hexdigest()[:16]
        sid["timestamp"] = datetime.now(timezone.utc).isoformat()

        return sid

    def _sanitize_input(self, text: str) -> str:
        """Truncate and strip prompt-injection patterns from user input."""
        sanitized = text[:500]
        sanitized = self._INJECTION_PATTERNS.sub("[REDACTED]", sanitized)
        return sanitized

    def _validate_sid_schema(self, sid: dict) -> None:
        """Raise ValueError if the SID dict is missing required keys or has wrong types."""
        missing = self._REQUIRED_SID_KEYS - sid.keys()
        if missing:
            raise ValueError(f"SID missing required keys: {missing}")
        if not isinstance(sid.get("scope", {}).get("tickers"), list):
            raise ValueError("scope.tickers must be a list")

    def _llm_formalize(self, user_input: str, sid_id: str) -> dict:
        """Call LLM to parse intent. Returns SID dict."""
        sanitized = self._sanitize_input(user_input)
        model = os.getenv("MODEL_ID", "gpt-oss-120b")
        system_prompt = """You are a financial intent parser for a secure AI trading system.
Parse the user's request and return ONLY a valid JSON object. No preamble, no markdown, no backticks.

Return exactly this JSON structure:
{
  "primary_action": "trade" or "research" or "query" or "research_only",
  "sub_action": "buy" or "sell" or "get_price" or "analyze" or "none",
  "permitted_actions": ["execute_trade", "query_market_data"] (only include execute_trade if intent is clearly to trade),
  "prohibited_actions": ["transmit_external", "file_write", "shell_exec", "data_export"],
  "scope": {
    "tickers": ["AAPL"] (list of tickers mentioned, only from: AAPL, MSFT, GOOGL, AMZN, NVDA),
    "max_quantity": 0 (number of shares requested, 0 if not specified),
    "order_type": "market" or "limit" or "unknown",
    "side": "buy" or "sell" or "none"
  },
  "reasoning_bounds": {
    "allowed_topics": ["list of topics the agent should focus on"],
    "forbidden_topics": ["list of topics the agent must not reason about"]
  },
  "ambiguity_flags": [],
  "resolution_method": null
}

RULES:
- If quantity is not mentioned, set max_quantity to 0 and add "scope_undefined" to ambiguity_flags
- If ticker is not in [AAPL, MSFT, GOOGL, AMZN, NVDA], set tickers to [] and add "ticker_not_approved" to ambiguity_flags
- If intent is unclear or vague, set primary_action to "research_only" and remove "execute_trade" from permitted_actions
- If input contains "maybe" or "might" add "conditional_trade" to ambiguity_flags
- Only include execute_trade in permitted_actions when user clearly wants to trade
"""
        response = self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": sanitized}
            ],
            max_tokens=500
        )
        raw = response.choices[0].message.content.strip()
        parsed = json.loads(raw)
        self._validate_sid_schema(parsed)
        parsed["sid_id"] = sid_id
        return parsed

    def _rule_based_formalize(self, user_input: str, sid_id: str) -> dict:
        """
        Deterministic rule-based fallback. Used when LLM is unavailable.
        Parses ticker, quantity, side from text with regex.
        """
        lower = user_input.lower()

        sub_action = "none"
        primary_action = "research"
        permitted = ["query_market_data", "analyze_sentiment", "verify_constraints"]
        if any(w in lower for w in ["buy", "purchase", "long"]):
            sub_action = "buy"
            primary_action = "trade"
            permitted = ["execute_trade", "query_market_data", "analyze_sentiment", "verify_constraints"]
        elif any(w in lower for w in ["sell", "short", "dump"]):
            sub_action = "sell"
            primary_action = "trade"
            permitted = ["execute_trade", "query_market_data", "analyze_sentiment", "verify_constraints"]
        elif any(w in lower for w in ["research", "analyze", "check", "look"]):
            primary_action = "research"
            permitted = ["query_market_data", "analyze_sentiment", "verify_constraints"]

        tickers = [t for t in self.allowed_tickers if t.lower() in lower]
        all_known_tickers = ["TSLA", "META", "NFLX", "BABA", "UBER", "LYFT", "SNAP", "TWTR", "AMD", "INTC"]

        ambiguity_flags = []

        if not tickers:
            unapproved = [t for t in all_known_tickers if t.lower() in lower]
            if unapproved:
                tickers = unapproved
                if "execute_trade" in permitted:
                    permitted.remove("execute_trade")
                ambiguity_flags.append("ticker_not_approved")

        qty_match = re.search(r'\b(\d+)\s*(?:shares?|stocks?|units?)\b', lower)
        max_qty = int(qty_match.group(1)) if qty_match else 0

        order_type = "limit" if "limit" in lower else "market"

        if max_qty == 0:
            ambiguity_flags.append("scope_undefined")
        approved_in_input = [t for t in self.allowed_tickers if t.lower() in lower]
        if not approved_in_input and primary_action == "trade":
            if "ticker_not_approved" not in ambiguity_flags:
                ambiguity_flags.append("ticker_not_approved")
            if "execute_trade" in permitted:
                permitted.remove("execute_trade")
        if "maybe" in lower or "might" in lower:
            ambiguity_flags.append("conditional_trade")
            if "execute_trade" in permitted:
                permitted.remove("execute_trade")
            primary_action = "research_only"

        if not any(w in lower for w in ["buy", "purchase", "sell", "short"]) and primary_action == "trade":
            primary_action = "research_only"
            permitted = ["query_market_data", "analyze_sentiment", "verify_constraints"]

        ticker_str = tickers[0] if tickers else "unknown"
        allowed_topics = [f"{ticker_str} price", f"{ticker_str} market data", "order execution"] if tickers else ["market research"]
        forbidden_topics = ["other tickers", "portfolio rebalancing", "external transfers", "system configuration"]

        return {
            "sid_id": sid_id,
            "primary_action": primary_action,
            "sub_action": sub_action,
            "permitted_actions": permitted,
            "prohibited_actions": ["transmit_external", "file_write", "shell_exec", "data_export"],
            "scope": {
                "tickers": tickers,
                "max_quantity": max_qty,
                "order_type": order_type,
                "side": sub_action if sub_action in ["buy", "sell"] else "none"
            },
            "reasoning_bounds": {
                "allowed_topics": allowed_topics,
                "forbidden_topics": forbidden_topics
            },
            "ambiguity_flags": ambiguity_flags,
            "resolution_method": None
        }

    def _apply_ambiguity_rules(self, user_input: str, sid: dict) -> dict:
        """Post-process SID with additional ambiguity safety rules."""
        lower = user_input.lower()
        if "maybe" in lower or "might" in lower or "consider" in lower:
            if "conditional_trade" not in sid["ambiguity_flags"]:
                sid["ambiguity_flags"].append("conditional_trade")
            if "execute_trade" in sid["permitted_actions"]:
                sid["permitted_actions"].remove("execute_trade")
        if not sid["scope"]["tickers"]:
            if "ticker_not_approved" not in sid["ambiguity_flags"]:
                sid["ambiguity_flags"].append("ticker_not_approved")
        if sid["ambiguity_flags"] and not sid.get("resolution_method"):
            sid["resolution_method"] = "conservative_default_policy"

        sid["permitted_actions"] = list(dict.fromkeys(sid["permitted_actions"]))
        sid["ambiguity_flags"] = list(dict.fromkeys(sid["ambiguity_flags"]))

        return sid
