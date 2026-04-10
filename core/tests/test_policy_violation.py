from src.fdee import FinancialDomainEnforcementEngine


def test_tsla_blocked():
    fdee = FinancialDomainEnforcementEngine(skip_market_hours=True)
    plan = {
        "plan": [
            {"tool": "execute_trade", "args": {"symbol": "TSLA", "qty": 100, "side": "buy", "type": "market"}, "step": 1}
        ],
        "reasoning_trace": ""
    }
    r = fdee.enforce(plan)
    assert r["status"] == "BLOCK", f"Expected BLOCK for TSLA, got {r['status']}"
    assert any("TSLA" in v for v in r["violations"]), f"Expected TSLA violation in: {r['violations']}"
    print(f"  [PASS] TSLA blocked: {r['violations'][0]}")


def test_quantity_corrected():
    fdee = FinancialDomainEnforcementEngine(skip_market_hours=True)
    plan = {
        "plan": [
            {"tool": "execute_trade", "args": {"symbol": "AAPL", "qty": 50, "side": "buy", "type": "market"}, "step": 1}
        ],
        "reasoning_trace": ""
    }
    r = fdee.enforce(plan)
    assert r["status"] == "CORRECT", f"Expected CORRECT for qty=50, got {r['status']}"
    assert "qty" in r["corrections"], f"Expected qty correction in: {r['corrections']}"
    assert r["corrections"]["qty"] == 10
    print("  [PASS] Qty 50 corrected to 10")


def test_denied_tool_blocked():
    fdee = FinancialDomainEnforcementEngine(skip_market_hours=True)
    plan = {
        "plan": [
            {"tool": "bash", "args": {"cmd": "ls"}, "step": 1},
            {"tool": "execute_trade", "args": {"symbol": "AAPL", "qty": 5, "side": "buy", "type": "market"}, "step": 2}
        ],
        "reasoning_trace": ""
    }
    r = fdee.enforce(plan)
    assert r["status"] == "BLOCK", f"Expected BLOCK for bash tool, got {r['status']}"
    print(f"  [PASS] Denied tool 'bash' blocked: {r['violations'][0]}")


if __name__ == "__main__":
    print("\n--- test_policy_violation ---")
    test_tsla_blocked()
    test_quantity_corrected()
    test_denied_tool_blocked()
    print("All tests passed.\n")
