"""
LAYER 5 — Plan-Intent Alignment Validator (PIAV)
100% DETERMINISTIC — ZERO LLM CALLS.

Compares ExecutionAgent's plan against the SID:
  1. Every tool in plan must be in SID permitted_actions
  2. Plan parameters (ticker, qty) must be within SID scope
  3. Plan must NOT include any SID prohibited_actions
  4. Reasoning trace must not mention forbidden_topics

Returns: {aligned: bool, violations: list, result: "PASS"/"BLOCK", status}
"""

from __future__ import annotations
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


class PlanIntentAlignmentValidator:

    def validate(self, plan_data: dict, sid: dict) -> dict:
        violations:    list[str] = []
        checks_passed: list[str] = []

        permitted   = sid.get("permitted_actions", [])
        prohibited  = sid.get("prohibited_actions", [])
        scope       = sid.get("scope", {})
        scope_tickers = [t.upper() for t in scope.get("tickers", [])]
        scope_max_qty = int(scope.get("max_quantity", 0))
        primary      = sid.get("primary_action", "")
        forbidden_t  = sid.get("reasoning_bounds", {}).get("forbidden_topics", [])

        steps      = plan_data.get("plan", [])
        plan_tools = [s.get("tool", "") for s in steps]
        trace      = (plan_data.get("reasoning_trace", "") or "").lower()

        # CHECK 1: Every tool must be in permitted_actions
        for tool in plan_tools:
            if tool not in permitted:
                violations.append(f"Tool '{tool}' is not in SID.permitted_actions")
        if not violations:
            checks_passed.append("TOOLS_PERMITTED")

        # CHECK 2: No prohibited tools
        for tool in plan_tools:
            if tool in prohibited:
                violations.append(f"Tool '{tool}' is explicitly prohibited by SID")
        checks_passed.append("NO_PROHIBITED_TOOLS") if len(violations) == len(
            [v for v in violations if "not in SID.permitted_actions" in v]
        ) else None

        # CHECK 3: Scope validation for trade step
        trade_step = next(
            (s for s in steps if s.get("tool") in ("execute_trade", "alpaca_trade")), None
        )
        if trade_step:
            args   = trade_step.get("args", {})
            ticker = args.get("symbol", args.get("ticker", "")).upper()
            qty    = int(args.get("qty", 0))

            if scope_tickers and ticker not in scope_tickers:
                violations.append(
                    f"Ticker '{ticker}' not in SID scope {scope_tickers}"
                )
            else:
                checks_passed.append("TICKER_IN_SCOPE")

            if scope_max_qty > 0 and qty > scope_max_qty:
                violations.append(
                    f"Quantity {qty} exceeds SID scope max {scope_max_qty}"
                )
            else:
                checks_passed.append("QTY_IN_SCOPE")

        # CHECK 4: research_only enforcement
        if primary == "research_only":
            trade_tools = [t for t in plan_tools if TOOL_CATEGORY.get(t) == "trade"]
            if trade_tools:
                violations.append(
                    f"SID is research_only but plan contains trade actions: {trade_tools}"
                )
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
        for topic in forbidden_t:
            if topic.lower() in trace:
                violations.append(
                    f"Reasoning trace contains forbidden topic: '{topic}'"
                )
        if not any("forbidden topic" in v for v in violations):
            checks_passed.append("REASONING_CLEAN")

        aligned = len(violations) == 0
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
