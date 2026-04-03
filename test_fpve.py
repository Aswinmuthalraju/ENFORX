"""
TEST: Formal Plan Verification Engine (FPVE) Demonstration
Tests the 9-stage deterministic validation pipeline.
"""

import json
from core.piav import FormalPlanVerificationEngine

def test_fpve_demonstration():
    fpve = FormalPlanVerificationEngine()
    
    # Mock SID
    sid = {
        "sid_id": "sid-456",
        "primary_action": "trade_execution",
        "permitted_actions": ["query_market_data", "execute_trade", "verify_constraints", "calculate_risk"],
        "prohibited_actions": ["short_sell"],
        "scope": {
            "tickers": ["AAPL", "MSFT"],
            "max_quantity": 10,
            "side": "buy"
        },
        "reasoning_bounds": {
            "forbidden_topics": ["margin_trading", "leverage"]
        },
        "taint_flag": True  # Injected untrusted data source detected
    }

    # CASE 1: VALID PLAN (Sequential, Semantic Correct, Dependency Valid, Taint-Aware)
    valid_plan = {
        "plan": [
            {"tool": "query_market_data", "args": {"ticker": "AAPL"}, "step": 1},
            {"tool": "calculate_risk", "args": {"ticker": "AAPL"}, "step": 2},
            {"tool": "verify_constraints", "args": {"ticker": "AAPL", "qty": 5}, "step": 3},
            {"tool": "execute_trade", "args": {"symbol": "AAPL", "qty": 5, "side": "buy", "type": "market"}, "step": 4}
        ],
        "reasoning_trace": "Researching AAPL. Calculating risk. Validating constraints. Executing small buy."
    }

    # CASE 2: INVALID PLAN (Missing step, Semantic Error, Dependency Violation, Forbidden Topic)
    invalid_plan = {
        "plan": [
            # Missing "research" (query_market_data) for MSFT
            {"tool": "execute_trade", "args": {"symbol": "MSFT", "qty": -5, "side": "buy"}, "step": 1}, # Semantic error: negative qty
            {"tool": "read_file", "args": {"file": "/etc/passwd"}, "step": 2} # Prohibited tool rule (not in permitted list)
        ],
        "reasoning_trace": "Mentions margin_trading which is forbidden. Also reordering steps."
    }

    print("\n" + "="*80)
    print("🚀 TESTING FORMAL PLAN VERIFICATION ENGINE (FPVE)")
    print("="*80)

    print("\n[RUNNING VALIDATION] CASE 1: PERFECT ALIGNMENT")
    res1 = fpve.validate(valid_plan, sid)
    print(json.dumps(res1, indent=2))

    print("\n" + "-"*80)
    print("\n[RUNNING VALIDATION] CASE 2: MULTI-STAGE MISALIGNMENT")
    res2 = fpve.validate(invalid_plan, sid)
    print(json.dumps(res2, indent=2))
    
    print("\n" + "="*80)
    print("DONE.")

if __name__ == "__main__":
    test_fpve_demonstration()
