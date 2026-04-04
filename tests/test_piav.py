"""Tests for PlanIntentAlignmentValidator (PIAV)."""

from src.piav import PlanIntentAlignmentValidator


def _base_sid(**overrides):
    sid = {
        "primary_action": "execute_trade",
        "permitted_actions": [
            "query_market_data",
            "analyze_sentiment",
            "verify_constraints",
            "execute_trade",
        ],
        "prohibited_actions": ["transmit_external", "file_write", "shell_exec"],
        "scope": {
            "tickers": ["AAPL"],
            "max_quantity": 10,
            "side": "buy",
            "order_type": "market",
        },
        "reasoning_bounds": {"forbidden_topics": ["portfolio_export"]},
    }
    sid.update(overrides)
    return sid


def _full_trade_plan(**trade_args):
    args = {
        "symbol": "AAPL",
        "qty": 5,
        "side": "buy",
        "type": "market",
    }
    args.update(trade_args)
    return {
        "plan": [
            {"tool": "query_market_data", "args": {"ticker": "AAPL"}, "step": 1},
            {"tool": "analyze_sentiment", "args": {"ticker": "AAPL"}, "step": 2},
            {"tool": "verify_constraints", "args": {"ticker": "AAPL"}, "step": 3},
            {"tool": "execute_trade", "args": args, "step": 4},
        ],
        "reasoning_trace": "Executing within SID.",
    }


def test_no_prohibited_tools_check_passed_when_clean():
    piav = PlanIntentAlignmentValidator()
    r = piav.validate(_full_trade_plan(), _base_sid())
    assert r["status"] == "ALIGNED"
    assert "NO_PROHIBITED_TOOLS" in r["checks_passed"]


def test_prohibited_tool_blocks_and_skips_no_prohibited_flag_meaningfully():
    piav = PlanIntentAlignmentValidator()
    plan = _full_trade_plan()
    plan["plan"][0] = {"tool": "shell_exec", "args": {}, "step": 1}
    r = piav.validate(plan, _base_sid())
    assert r["result"] == "BLOCK"
    assert any("prohibited" in v.lower() for v in r["violations"])
    assert "NO_PROHIBITED_TOOLS" not in r["checks_passed"]


def test_trade_side_mismatch_blocks():
    piav = PlanIntentAlignmentValidator()
    sid = _base_sid()
    plan = _full_trade_plan(side="sell")
    r = piav.validate(plan, sid)
    assert r["result"] == "BLOCK"
    assert any("scope.side" in v for v in r["violations"])


def test_trade_order_type_mismatch_blocks():
    piav = PlanIntentAlignmentValidator()
    sid = _base_sid()
    plan = _full_trade_plan(type="limit")
    r = piav.validate(plan, sid)
    assert r["result"] == "BLOCK"
    assert any("order_type" in v for v in r["violations"])


def test_invalid_qty_no_exception():
    piav = PlanIntentAlignmentValidator()
    plan = _full_trade_plan(qty="five")
    r = piav.validate(plan, _base_sid())
    assert r["result"] == "BLOCK"
    assert any("qty" in v.lower() for v in r["violations"])


def test_uncategorized_permitted_tool_blocks():
    piav = PlanIntentAlignmentValidator()
    sid = _base_sid(
        permitted_actions=_base_sid()["permitted_actions"] + ["custom_research_tool"],
    )
    plan = _full_trade_plan()
    plan["plan"][0] = {
        "tool": "custom_research_tool",
        "args": {},
        "step": 1,
    }
    r = piav.validate(plan, sid)
    assert r["result"] == "BLOCK"
    assert any("uncategorized" in v.lower() for v in r["violations"])


def test_trade_with_empty_scope_tickers_blocks():
    piav = PlanIntentAlignmentValidator()
    sid = _base_sid()
    sid["scope"] = {**sid["scope"], "tickers": []}
    r = piav.validate(_full_trade_plan(), sid)
    assert r["result"] == "BLOCK"
    assert any("no allowed tickers" in v for v in r["violations"])


def test_empty_plan_blocks():
    piav = PlanIntentAlignmentValidator()
    r = piav.validate({"plan": [], "reasoning_trace": ""}, _base_sid())
    assert r["result"] == "BLOCK"
    assert any("no steps" in v.lower() for v in r["violations"])


def test_research_only_adds_research_only_ok():
    piav = PlanIntentAlignmentValidator()
    sid = _base_sid(primary_action="research_only")
    sid["permitted_actions"] = [
        "query_market_data",
        "analyze_sentiment",
        "verify_constraints",
    ]
    plan = {
        "plan": [
            {"tool": "query_market_data", "args": {"ticker": "AAPL"}, "step": 1},
        ],
        "reasoning_trace": "Research.",
    }
    r = piav.validate(plan, sid)
    assert r["status"] == "ALIGNED"
    assert "RESEARCH_ONLY_OK" in r["checks_passed"]


def test_forbidden_topic_word_boundary_no_false_positive_on_substring():
    piav = PlanIntentAlignmentValidator()
    plan = _full_trade_plan()
    plan["reasoning_trace"] = "Avoiding portfolio_exports entirely."
    r = piav.validate(plan, _base_sid())
    assert r["status"] == "ALIGNED"
    assert "REASONING_CLEAN" in r["checks_passed"]


def test_aligns_valid_plan_matches_existing_integration_case():
    piav = PlanIntentAlignmentValidator()
    sid = {
        "permitted_actions": [
            "query_market_data",
            "analyze_sentiment",
            "verify_constraints",
            "execute_trade",
        ],
        "prohibited_actions": ["transmit_external", "file_write", "shell_exec"],
        "scope": {
            "tickers": ["AAPL"],
            "max_quantity": 10,
            "side": "buy",
            "order_type": "market",
        },
        "reasoning_bounds": {
            "allowed_topics": ["AAPL price"],
            "forbidden_topics": ["portfolio rebalancing"],
        },
    }
    plan = {
        "plan": [
            {"tool": "query_market_data", "args": {"ticker": "AAPL"}, "step": 1},
            {"tool": "analyze_sentiment", "args": {"ticker": "AAPL"}, "step": 2},
            {"tool": "verify_constraints", "args": {"ticker": "AAPL"}, "step": 3},
            {
                "tool": "execute_trade",
                "args": {
                    "symbol": "AAPL",
                    "qty": 5,
                    "side": "buy",
                    "type": "market",
                },
                "step": 1,
            },
        ],
        "reasoning_trace": "Checking AAPL price and executing buy order.",
    }
    r = piav.validate(plan, sid)
    assert r["status"] == "ALIGNED", r["violations"]
