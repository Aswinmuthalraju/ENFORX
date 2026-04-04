"""
LAYER 5 — Plan-Intent Alignment Validator (PIAV)
100% DETERMINISTIC — ZERO LLM CALLS.

Compares ExecutionAgent's plan against the SID:
  1. Every tool in plan must be in SID permitted_actions
  2. Plan must NOT include any SID prohibited_actions
  3. Trade-step parameters (symbol, qty, side, order type) must match SID scope
  4. research_only SIDs must not include trade tools
  5. When a trade is present, tools must follow research → analyze → validate → trade
  6. Permitted tools must be registered in TOOL_CATEGORY (sequence validation)
  7. Reasoning trace must not mention forbidden_topics (word-boundary aware)

Returns: {aligned: bool, violations: list, result: "PASS"/"BLOCK", status}
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from logger_config import get_layer_logger
logger = get_layer_logger("layer.05.piav")

TOOL_CATEGORY = {
    "query_market_data":  "research",
    "web_search":         "research",
    "web_fetch":          "research",
    "read_file":          "research",
    "analyze_sentiment":  "analyze",
    "calculate_risk":     "analyze",
    "verify_constraints": "validate",
    "execute_trade":      "trade",
    "alpaca_trade":       "trade",
}

REQUIRED_SEQUENCE = ["research", "analyze", "validate", "trade"]

_TRADE_TOOLS = frozenset({"execute_trade", "alpaca_trade"})


def _safe_int(value: object, *, field: str) -> tuple[int | None, str | None]:
    """Parse int for scope/qty; return (value, error_message)."""
    if value is None:
        return None, f"Missing {field}"
    try:
        return int(value), None
    except (TypeError, ValueError):
        return None, f"Invalid {field}: {value!r}"


def _forbidden_topic_in_trace(topic: str, trace_lower: str) -> bool:
    if not topic or not trace_lower:
        return False
    needle = re.escape(topic.lower())
    return re.search(rf"(?<!\w){needle}(?!\w)", trace_lower) is not None


class PlanIntentAlignmentValidator:

    def validate(self, plan_data: dict, sid: dict) -> dict:
        violations:    list[str] = []
        checks_passed: list[str] = []

        permitted   = sid.get("permitted_actions", [])
        prohibited  = sid.get("prohibited_actions", [])
        scope       = sid.get("scope", {})
        scope_tickers = [t.upper() for t in scope.get("tickers", [])]
        scope_max_qty, scope_qty_err = _safe_int(scope.get("max_quantity", 0), field="scope.max_quantity")
        if scope_qty_err:
            violations.append(f"SID scope: {scope_qty_err}")
            scope_max_qty = 0
        primary      = sid.get("primary_action", "")
        forbidden_t  = sid.get("reasoning_bounds", {}).get("forbidden_topics", [])

        steps      = plan_data.get("plan", [])
        plan_tools = [s.get("tool", "") for s in steps if s.get("tool")]
        trace      = (plan_data.get("reasoning_trace", "") or "").lower()

        # CHECK 0: Non-empty plan
        if not steps:
            violations.append("Plan contains no steps")
        else:
            checks_passed.append("PLAN_NON_EMPTY")

        # CHECK 1: Every tool must be in permitted_actions
        permitted_fail = False
        for tool in plan_tools:
            if tool not in permitted:
                violations.append(f"Tool '{tool}' is not in SID.permitted_actions")
                permitted_fail = True
        if plan_tools and not permitted_fail:
            checks_passed.append("TOOLS_PERMITTED")

        # CHECK 2: No prohibited tools
        had_prohibited_tool_violation = False
        for tool in plan_tools:
            if tool in prohibited:
                violations.append(f"Tool '{tool}' is explicitly prohibited by SID")
                had_prohibited_tool_violation = True
        if not had_prohibited_tool_violation:
            checks_passed.append("NO_PROHIBITED_TOOLS")

        # CHECK 2b: Permitted tools must be categorized for sequence validation
        for tool in plan_tools:
            if tool in permitted and tool not in TOOL_CATEGORY:
                violations.append(
                    f"Tool '{tool}' is permitted but uncategorized for sequence validation "
                    "(update TOOL_CATEGORY)"
                )

        # CHECK 3: Scope validation for trade step
        trade_step = next(
            (s for s in steps if s.get("tool") in _TRADE_TOOLS), None
        )
        if trade_step:
            args   = trade_step.get("args", {})
            ticker = args.get("symbol", args.get("ticker", "")).upper()
            qty, qty_err = _safe_int(args.get("qty"), field="qty")
            if qty_err:
                violations.append(f"Trade step: {qty_err}")
            elif scope_max_qty and scope_max_qty > 0 and qty is not None and qty > scope_max_qty:
                violations.append(
                    f"Quantity {qty} exceeds SID scope max {scope_max_qty}"
                )
            else:
                checks_passed.append("QTY_IN_SCOPE")

            if not scope_tickers:
                violations.append(
                    "Trade step present but SID scope defines no allowed tickers"
                )
            elif ticker not in scope_tickers:
                violations.append(
                    f"Ticker '{ticker}' not in SID scope {scope_tickers}"
                )
            else:
                checks_passed.append("TICKER_IN_SCOPE")

            scope_side = str(scope.get("side", "") or "").lower()
            if scope_side and scope_side not in ("none", "n/a"):
                arg_side = str(args.get("side", "") or "").lower()
                if arg_side != scope_side:
                    violations.append(
                        f"Trade side '{arg_side or '(missing)'}' does not match SID scope.side '{scope_side}'"
                    )
                else:
                    checks_passed.append("SIDE_IN_SCOPE")

            scope_order = str(scope.get("order_type", "") or "").lower()
            if scope_order:
                arg_type = str(args.get("type", "") or "").lower()
                if arg_type != scope_order:
                    violations.append(
                        f"Trade order type '{arg_type or '(missing)'}' does not match "
                        f"SID scope.order_type '{scope_order}'"
                    )
                else:
                    checks_passed.append("ORDER_TYPE_IN_SCOPE")

        # CHECK 4: research_only enforcement
        if primary == "research_only":
            trade_tools = [t for t in plan_tools if TOOL_CATEGORY.get(t) == "trade"]
            if trade_tools:
                violations.append(
                    f"SID is research_only but plan contains trade actions: {trade_tools}"
                )
            else:
                checks_passed.append("RESEARCH_ONLY_OK")
        else:
            checks_passed.append("INTENT_MATCH")

        # CHECK 5: Required sequence (research → analyze → validate → trade)
        categories = [TOOL_CATEGORY.get(t, "unknown") for t in plan_tools]
        rel_cats   = [c for c in categories if c != "unknown"]
        if trade_step:
            req_idx = 0
            for cat in rel_cats:
                if req_idx < len(REQUIRED_SEQUENCE) and cat == REQUIRED_SEQUENCE[req_idx]:
                    req_idx += 1
            if req_idx < len(REQUIRED_SEQUENCE):
                missing = REQUIRED_SEQUENCE[req_idx:]
                violations.append(
                    f"Missing execution sequence steps: {missing}"
                )
            else:
                checks_passed.append("SEQUENCE_OK")

        # CHECK 6: Reasoning trace forbidden topics
        reasoning_violation = False
        for topic in forbidden_t:
            if _forbidden_topic_in_trace(topic, trace):
                violations.append(
                    f"Reasoning trace contains forbidden topic: '{topic}'"
                )
                reasoning_violation = True
        if forbidden_t and not reasoning_violation:
            checks_passed.append("REASONING_CLEAN")
        elif not forbidden_t:
            checks_passed.append("REASONING_CLEAN_NO_TOPICS_DEFINED")

        aligned = len(violations) == 0
        if not aligned:
            logger.warning(
                "PIAV BLOCK — %d violation(s): %s",
                len(violations),
                violations[:3],
            )
        else:
            logger.info("PIAV PASS — checks=%s", checks_passed)
        return {
            "aligned":        aligned,
            "result":         "PASS" if aligned else "BLOCK",
            "status":         "ALIGNED" if aligned else "MISALIGNED",
            "violations":     violations,
            "checks_passed":  checks_passed,
            "timestamp":      datetime.now(timezone.utc).isoformat(),
        }


# ── Standalone test ──────────────────────────────────────────────────────────
def test_piav():
    piav = PlanIntentAlignmentValidator()
    sid = {
        "sid_id":           "sid-test",
        "primary_action":   "execute_trade",
        "permitted_actions": ["query_market_data", "analyze_sentiment",
                              "verify_constraints", "execute_trade"],
        "prohibited_actions": ["transmit_external", "short_sell"],
        "scope": {"tickers": ["AAPL"], "max_quantity": 5, "side": "buy", "order_type": "market"},
        "reasoning_bounds": {"forbidden_topics": ["portfolio_export"]},
        "ambiguity_flags": [],
    }
    plan_ok = {"plan": [
        {"tool": "query_market_data",  "args": {"ticker": "AAPL"}, "step": 1},
        {"tool": "analyze_sentiment",  "args": {"ticker": "AAPL"}, "step": 2},
        {"tool": "verify_constraints", "args": {"ticker": "AAPL"}, "step": 3},
        {"tool": "execute_trade",      "args": {"symbol": "AAPL", "qty": 5, "side": "buy", "type": "market"}, "step": 4},
    ], "reasoning_trace": "Buying AAPL within scope."}

    plan_bad = {"plan": [
        {"tool": "bash",         "args": {}, "step": 1},
        {"tool": "execute_trade","args": {"symbol": "TSLA", "qty": 20, "side": "buy", "type": "market"}, "step": 2},
    ], "reasoning_trace": "Exporting portfolio_export data."}

    print("\n=== PIAV Tests ===")
    for label, plan in [("Valid plan", plan_ok), ("Bad plan", plan_bad)]:
        r = piav.validate(plan, sid)
        print(f"  [{r['result']:5s}] {label}: violations={r['violations'][:2]}")
    print()


if __name__ == "__main__":
    test_piav()
