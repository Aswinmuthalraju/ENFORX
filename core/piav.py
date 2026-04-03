"""
LAYER 5: Plan-Intent Alignment Validator (PIAV)
100% DETERMINISTIC — zero LLM calls.
Checks: does the agent's plan actually match what the SID declared?

ArmorClaw proves the agent followed the plan.
PIAV proves the plan matched the declared intent.
"""

import json
from pathlib import Path
from datetime import datetime, timezone


class PlanIntentAlignmentValidator:
    def __init__(self, policy_path: str = None):
        if policy_path is None:
            policy_path = Path(__file__).parent.parent / "enforx-policy.json"
        with open(policy_path) as f:
            policy = json.load(f)
        self.allowed_order_types = policy["enforx_policy"]["trade_constraints"]["allowed_order_types"]

    def validate(self, plan: dict, sid: dict) -> dict:
        """
        Run 4 deterministic alignment checks.
        Returns validation result with check-by-check breakdown.
        """
        violations = []
        checks = {
            "tools_in_permitted": False,
            "params_in_scope": False,
            "no_prohibited_tools": False,
            "reasoning_in_bounds": False
        }

        plan_steps = plan.get("plan", [])
        plan_tools = [step.get("tool", "") for step in plan_steps]
        permitted = sid.get("permitted_actions", [])
        prohibited = sid.get("prohibited_actions", [])
        scope = sid.get("scope", {})
        bounds = sid.get("reasoning_bounds", {})
        forbidden_topics = bounds.get("forbidden_topics", [])

        # CHECK 1: All tools in plan must be in permitted_actions
        bad_tools = [t for t in plan_tools if t not in permitted]
        if bad_tools:
            violations.append(f"Tools not in permitted_actions: {bad_tools}")
            checks["tools_in_permitted"] = False
        else:
            checks["tools_in_permitted"] = True

        # CHECK 2: Trade parameters within SID scope
        trade_step = next((s for s in plan_steps if s.get("tool") == "execute_trade"), None)
        if trade_step:
            args = trade_step.get("args", {})
            scope_violations = []
            allowed_tickers = scope.get("tickers", [])
            if allowed_tickers and args.get("symbol", "").upper() not in [t.upper() for t in allowed_tickers]:
                scope_violations.append(f"symbol '{args.get('symbol')}' not in declared tickers {allowed_tickers}")
            max_qty = scope.get("max_quantity", 0)
            if max_qty > 0 and args.get("qty", 0) > max_qty:
                scope_violations.append(f"qty {args.get('qty')} exceeds SID max_quantity {max_qty}")
            declared_side = scope.get("side", "")
            if declared_side and declared_side != "none" and args.get("side", "") != declared_side:
                scope_violations.append(f"side '{args.get('side')}' doesn't match declared side '{declared_side}'")
            if args.get("type") and args["type"] not in self.allowed_order_types:
                scope_violations.append(f"order type '{args['type']}' not in allowed order types")
            if scope_violations:
                violations.extend([f"Scope violation: {v}" for v in scope_violations])
                checks["params_in_scope"] = False
            else:
                checks["params_in_scope"] = True
        else:
            checks["params_in_scope"] = True

        # CHECK 3: No prohibited tools in plan
        found_prohibited = [t for t in plan_tools if t in prohibited]
        if found_prohibited:
            violations.append(f"Prohibited tools found in plan: {found_prohibited}")
            checks["no_prohibited_tools"] = False
        else:
            checks["no_prohibited_tools"] = True

        # CHECK 4: Reasoning trace doesn't mention forbidden topics
        reasoning = plan.get("reasoning_trace", "").lower()
        reasoning_violations = []
        for topic in forbidden_topics:
            if topic.lower() in reasoning:
                reasoning_violations.append(f"Reasoning mentions forbidden topic: '{topic}'")
        if reasoning_violations:
            violations.extend(reasoning_violations)
            checks["reasoning_in_bounds"] = False
        else:
            checks["reasoning_in_bounds"] = True

        aligned = len(violations) == 0
        corrective = None
        if not aligned:
            corrective = (
                "Plan rejected. Agent must regenerate a plan that: "
                "(1) uses only permitted tools, "
                "(2) stays within declared scope, "
                "(3) avoids prohibited tools, "
                "(4) reasons only within declared bounds."
            )

        return {
            "status": "ALIGNED" if aligned else "MISALIGNED",
            "checks": checks,
            "violations": violations,
            "corrective_action": corrective,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
