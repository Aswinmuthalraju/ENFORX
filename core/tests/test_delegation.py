from src.dap import DelegationAuthorityProtocol


def test_token_issued():
    dap = DelegationAuthorityProtocol()
    result = dap.issue_token("analyst", "trader", {"action": "buy", "ticker": "AAPL", "max_quantity": 10})
    assert result["status"] == "ISSUED", f"Expected ISSUED, got {result['status']}"
    assert result["token"]["scope"]["max_quantity"] == 10
    print(f"  [PASS] Token issued: max_quantity={result['token']['scope']['max_quantity']}")


def test_delegation_breach_quantity():
    dap = DelegationAuthorityProtocol()
    token_result = dap.issue_token("analyst", "trader", {"action": "buy", "ticker": "AAPL", "max_quantity": 10})
    token = token_result["token"]

    plan_20 = {
        "plan": [
            {"tool": "execute_trade", "args": {"symbol": "AAPL", "qty": 20, "side": "buy", "type": "market"}, "step": 1}
        ]
    }
    r = dap.authorize(token, plan_20, "trader")
    assert r["status"] == "DELEGATION_VIOLATION", f"Expected DELEGATION_VIOLATION, got {r['status']}"
    print(f"  [PASS] Delegation breach (qty) blocked: {r['reason']}")


def test_delegation_valid_trade():
    dap = DelegationAuthorityProtocol()
    token_result = dap.issue_token("analyst", "trader", {"action": "buy", "ticker": "AAPL", "max_quantity": 10})
    token = token_result["token"]

    plan_5 = {
        "plan": [
            {"tool": "execute_trade", "args": {"symbol": "AAPL", "qty": 5, "side": "buy", "type": "market"}, "step": 1}
        ]
    }
    r = dap.authorize(token, plan_5, "trader")
    assert r["status"] == "AUTHORIZED", f"Expected AUTHORIZED, got {r['status']}"
    print(f"  [PASS] Valid delegation authorized: {r['reason']}")


def test_token_single_use():
    dap = DelegationAuthorityProtocol()
    token_result = dap.issue_token("analyst", "trader", {"action": "buy", "ticker": "AAPL", "max_quantity": 10})
    token = token_result["token"]

    plan_5 = {
        "plan": [
            {"tool": "execute_trade", "args": {"symbol": "AAPL", "qty": 5, "side": "buy", "type": "market"}, "step": 1}
        ]
    }
    # First use — should be authorized
    r1 = dap.authorize(token, plan_5, "trader")
    assert r1["status"] == "AUTHORIZED", f"First use: expected AUTHORIZED, got {r1['status']}"

    # Second use — should be blocked
    r2 = dap.authorize(token, plan_5, "trader")
    assert r2["status"] == "DELEGATION_VIOLATION", f"Reuse: expected DELEGATION_VIOLATION, got {r2['status']}"
    print(f"  [PASS] Single-use token enforced: {r2['reason']}")


def test_unauthorized_delegator():
    dap = DelegationAuthorityProtocol()
    result = dap.issue_token("trader", "analyst", {"action": "buy", "ticker": "AAPL", "max_quantity": 5})
    assert result["status"] == "DELEGATION_REFUSED", f"Expected DELEGATION_REFUSED, got {result['status']}"
    print(f"  [PASS] Unauthorized delegator refused: {result['reason']}")


def test_single_agent_mode():
    dap = DelegationAuthorityProtocol()
    plan = {"plan": [{"tool": "execute_trade", "args": {"symbol": "AAPL", "qty": 5, "side": "buy", "type": "market"}, "step": 1}]}
    r = dap.authorize(None, plan, "direct")
    assert r["status"] == "AUTHORIZED", f"Expected AUTHORIZED in single-agent mode, got {r['status']}"
    print("  [PASS] Single-agent mode authorized")


if __name__ == "__main__":
    print("\n--- test_delegation ---")
    test_token_issued()
    test_delegation_breach_quantity()
    test_delegation_valid_trade()
    test_token_single_use()
    test_unauthorized_delegator()
    test_single_agent_mode()
    print("All tests passed.\n")
