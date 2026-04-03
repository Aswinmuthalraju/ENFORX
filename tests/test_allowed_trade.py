from enforxguard.input_firewall import InputFirewall
from core.fdee import FinancialDomainEnforcementEngine
from core.piav import PlanIntentAlignmentValidator


def test_input_firewall_passes_clean():
    fw = InputFirewall()
    result = fw.scan("Buy 5 shares of AAPL")
    assert result["status"] == "PASS", f"Expected PASS, got {result['status']}: {result}"
    assert result["taint_tag"] == "TRUSTED", f"Expected TRUSTED taint, got {result['taint_tag']}"
    print("  [PASS] Input firewall accepts clean input")


def test_fdee_allows_valid_trade():
    fdee = FinancialDomainEnforcementEngine(skip_market_hours=True)
    plan = {
        "plan": [
            {"tool": "execute_trade", "args": {"symbol": "AAPL", "qty": 5, "side": "buy", "type": "market"}, "step": 1}
        ],
        "reasoning_trace": ""
    }
    r = fdee.enforce(plan)
    assert r["status"] in ["ALLOW", "CORRECT"], f"Expected ALLOW/CORRECT, got {r['status']}: {r['reason']}"
    print(f"  [PASS] FDEE allows valid trade (status: {r['status']})")


def test_piav_aligns_valid_plan():
    piav = PlanIntentAlignmentValidator()
    sid = {
        "permitted_actions": ["execute_trade", "query_market_data"],
        "prohibited_actions": ["transmit_external", "file_write", "shell_exec"],
        "scope": {"tickers": ["AAPL"], "max_quantity": 10, "side": "buy", "order_type": "market"},
        "reasoning_bounds": {"allowed_topics": ["AAPL price"], "forbidden_topics": ["portfolio rebalancing"]}
    }
    plan = {
        "plan": [
            {"tool": "execute_trade", "args": {"symbol": "AAPL", "qty": 5, "side": "buy", "type": "market"}, "step": 1}
        ],
        "reasoning_trace": "Checking AAPL price and executing buy order."
    }
    r = piav.validate(plan, sid)
    assert r["status"] == "ALIGNED", f"Expected ALIGNED, got {r['status']}: {r['violations']}"
    print("  [PASS] PIAV aligns valid plan with SID")


if __name__ == "__main__":
    print("\n--- test_allowed_trade ---")
    test_input_firewall_passes_clean()
    test_fdee_allows_valid_trade()
    test_piav_aligns_valid_plan()
    print("All tests passed.\n")
