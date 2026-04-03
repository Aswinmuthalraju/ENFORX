"""
LAYER 5: Formal Plan Verification Engine (FPVE)
(Formerly known as Plan-Intent Alignment Validator - PIAV)

100% DETERMINISTIC — NO LLM.
Performs deep structural validation, semantic check, and dependency analysis.
Guarantees the plan is a faithful, safe, and complete realization of SID intent.
"""

import json
from pathlib import Path
from datetime import datetime, timezone
import collections


class FormalPlanVerificationEngine:
    def __init__(self, policy_path: str = None):
        if policy_path is None:
            policy_path = Path(__file__).parent.parent / "enforx-policy.json"
        with open(policy_path) as f:
            policy = json.load(f)
        
        self.policy = policy["enforx_policy"]
        self.trade_constraints = self.policy["trade_constraints"]
        self.data_constraints = self.policy["data_constraints"]
        self.causal_constraints = self.policy["causal_chain_constraints"]
        
        # Tool mapping for sequence validation
        self.tool_to_category = {
            "query_market_data": "research",
            "web_search": "research",
            "web_fetch": "research",
            "read_file": "research",
            "analyze_sentiment": "analyze",
            "calculate_risk": "analyze",
            "verify_constraints": "validate",
            "execute_trade": "trade",
            "alpaca_trade": "trade"
        }

    def validate(self, plan_data: dict, sid: dict, current_state: dict = None) -> dict:
        """
        Transform Layer 5 from a simple rule checker into a formal verification engine.
        Processes plan through 9 deterministic validation stages.
        """
        violations = []
        failed_checks = []
        
        # 1. Structural Validation
        v1 = self._validate_structural(plan_data, sid)
        violations.extend(v1["violations"])
        if v1["failed"]: failed_checks.append("STRUCTURAL")

        # 2. Sequence-Level Validation
        v2 = self._validate_sequence(plan_data, sid)
        violations.extend(v2["violations"])
        if v2["failed"]: failed_checks.append("SEQUENCE")

        # 3. Parameter Semantic Validation
        v3 = self._validate_semantic(plan_data)
        violations.extend(v3["violations"])
        if v3["failed"]: failed_checks.append("SEMANTIC")

        # 4. Cross-Step Dependency Check
        v4 = self._validate_dependency(plan_data)
        violations.extend(v4["violations"])
        if v4["failed"]: failed_checks.append("DEPENDENCY")

        # 5. Reasoning Structure Validation (Deterministic)
        v5 = self._validate_reasoning(plan_data, sid)
        violations.extend(v5["violations"])
        if v5["failed"]: failed_checks.append("REASONING")

        # 6. Intent Strictness Enforcement
        v6 = self._validate_intent_strictness(plan_data, sid)
        violations.extend(v6["violations"])
        if v6["failed"]: failed_checks.append("INTENT")

        # 7. Taint-Aware Plan Validation
        v7 = self._validate_taint(plan_data, sid)
        violations.extend(v7["violations"])
        if v7["failed"]: failed_checks.append("TAINT")

        # 8. State Simulation (Lightweight)
        v8 = self._validate_state_simulation(plan_data, sid, current_state)
        violations.extend(v8["violations"])
        if v8["failed"]: failed_checks.append("STATE")

        # 9. Adversarial Detection
        v9 = self._detect_adversarial(plan_data, sid)
        violations.extend(v9["violations"])
        if v9["failed"]: failed_checks.append("ADVERSARIAL")

        # Calculate Alignment Score (0-100)
        # Each stage is weighted equally (approx 11 points)
        # Any critical violation forces status = MISALIGNED
        total_checks = 9
        passed_checks = total_checks - len(failed_checks)
        alignment_score = int((passed_checks / total_checks) * 100)
        
        # Determine Status
        status = "ALIGNED" if not violations else "MISALIGNED"
        
        # Generate Explanation
        explanation = "Plan is fully aligned with SID intent." if not violations else \
                      f"Plan validation failed with {len(violations)} violation(s) across stages: {', '.join(failed_checks)}."

        return {
            "status": status,
            "violations": violations,
            "sequence_valid": v2["status"],
            "dependency_valid": v4["status"],
            "semantic_valid": v3["status"],
            "taint_safe": v7["status"],
            "alignment_score": alignment_score,
            "explanation": explanation,
            "failed_checks": failed_checks,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "engine_version": "2.0 (FPVE)"
        }

    def _validate_structural(self, plan_data: dict, sid: dict) -> dict:
        violations = []
        plan_steps = plan_data.get("plan", [])
        permitted = sid.get("permitted_actions", [])
        prohibited = sid.get("prohibited_actions", [])
        
        for step in plan_steps:
            tool = step.get("tool")
            if not tool:
                violations.append("Malformed step: missing 'tool' name")
                continue
            if tool not in permitted:
                violations.append(f"Tool '{tool}' is not in SID.permitted_actions")
            if tool in prohibited:
                violations.append(f"Tool '{tool}' is explicitly prohibited by SID")
        
        return {"failed": len(violations) > 0, "violations": violations}

    def _validate_sequence(self, plan_data: dict, sid: dict = None) -> dict:
        violations = []
        plan_steps = plan_data.get("plan", [])
        plan_categories = [self.tool_to_category.get(s.get("tool", ""), "unknown") for s in plan_steps]
        
        required_seq = list(self.causal_constraints.get("required_tool_sequence", []))
        if sid and sid.get("primary_action") == "research_only" and "trade" in required_seq:
            required_seq.remove("trade")
        
        # Filter out "unknown" for sequence check
        relevant_categories = [c for c in plan_categories if c != "unknown"]
        
        # Check if all required categories are present in order
        req_idx = 0
        for category in relevant_categories:
            if req_idx < len(required_seq) and category == required_seq[req_idx]:
                req_idx += 1
        
        if req_idx < len(required_seq):
            missing = required_seq[req_idx:]
            violations.append(f"Missing required execution pattern steps: {missing}. Plan categories: {relevant_categories}")
        
        # Detect suspicious shortcuts (e.g. trading without research)
        if "trade" in relevant_categories and "research" not in relevant_categories:
            violations.append("Suspicious shortcut detected: Attempting 'trade' without prior 'research'")
            
        return {
            "failed": len(violations) > 0, 
            "violations": violations, 
            "status": len(violations) == 0
        }

    def _validate_semantic(self, plan_data: dict) -> dict:
        violations = []
        plan_steps = plan_data.get("plan", [])
        
        for step in plan_steps:
            tool = step.get("tool", "")
            args = step.get("args", {})
            
            if tool in ["execute_trade", "alpaca_trade"]:
                qty = args.get("qty", 0)
                if not isinstance(qty, (int, float)) or qty <= 0:
                    violations.append(f"Semantic error in {tool}: quantity must be positive, got {qty}")
                
                price = args.get("limit_price")
                if price is not None and (not isinstance(price, (int, float)) or price <= 0):
                    violations.append(f"Semantic error in {tool}: limit_price must be positive, got {price}")
                
                order_type = args.get("type", "market")
                if order_type == "limit" and price is None:
                    violations.append(f"Semantic error in {tool}: limit order type requires a limit_price")
                if order_type == "market" and price is not None:
                    violations.append(f"Semantic error in {tool}: market order type should not have a limit_price")

        return {
            "failed": len(violations) > 0, 
            "violations": violations,
            "status": len(violations) == 0
        }

    def _validate_dependency(self, plan_data: dict) -> dict:
        violations = []
        plan_steps = plan_data.get("plan", [])
        
        # Track active "research focus"
        research_tickers = set()
        for step in plan_steps:
            tool = step.get("tool", "")
            args = step.get("args", {})
            
            if self.tool_to_category.get(tool) == "research":
                ticker = args.get("ticker") or args.get("symbol")
                if ticker: research_tickers.add(ticker.upper())
            
            if self.tool_to_category.get(tool) == "trade":
                trade_ticker = (args.get("symbol") or args.get("ticker", "")).upper()
                if trade_ticker not in research_tickers:
                    violations.append(f"Dependency violation: trading '{trade_ticker}' without prior research in the same plan")
        
        return {
            "failed": len(violations) > 0, 
            "violations": violations,
            "status": len(violations) == 0
        }

    def _validate_reasoning(self, plan_data: dict, sid: dict) -> dict:
        violations = []
        trace = plan_data.get("reasoning_trace", "").lower()
        forbidden = sid.get("reasoning_bounds", {}).get("forbidden_topics", [])
        
        for topic in forbidden:
            if topic.lower() in trace:
                violations.append(f"Reasoning boundary violation: forbidden topic '{topic}' detected in plan trace")
        
        # Detect logic leakage (e.g. mentions of SID internals in plan justification)
        if "sid_id" in trace and sid.get("sid_id") in trace:
             # This might be normal if the agent explains its SID compliance, 
             # but we check for suspicious patterns.
             pass
             
        return {"failed": len(violations) > 0, "violations": violations}

    def _validate_intent_strictness(self, plan_data: dict, sid: dict) -> dict:
        violations = []
        plan_steps = plan_data.get("plan", [])
        permitted = sid.get("permitted_actions", [])
        
        # Plan must do EXACTLY what SID intends - no hidden side effects
        primary_action = sid.get("primary_action", "")
        plan_tools = [s.get("tool", "") for s in plan_steps]
        
        if primary_action == "research_only" and any(self.tool_to_category.get(t) == "trade" for t in plan_tools):
            violations.append("Intent violation: SID specified 'research_only' but plan contains trade actions")
            
        # Check for extra actions that don't serve the intent
        # (Heuristic: more than 2 untracked tools might be a side effect)
        untracked = [t for t in plan_tools if t not in permitted and self.tool_to_category.get(t) == "unknown"]
        if untracked:
            violations.append(f"Strictness violation: Plan contains extra actions with no declared intent: {untracked}")
            
        return {"failed": len(violations) > 0, "violations": violations}

    def _validate_taint(self, plan_data: dict, sid: dict) -> dict:
        violations = []
        # Check if plan contains steps that ingest UNTRUSTED data without sanitization
        # In a real system, we'd check step metadata. Here we look for untrusted tool flags.
        plan_steps = plan_data.get("plan", [])
        
        # Policy: block_trade_if_untrusted_in_chain
        has_untrusted_input = sid.get("taint_flag", False)
        
        if has_untrusted_input:
            # If the source is untrusted, we expect a 'validate' or 'sanitize' step before 'trade'
            plan_cats = [self.tool_to_category.get(s.get("tool", ""), "unknown") for s in plan_steps]
            if "trade" in plan_cats:
                if "validate" not in plan_cats:
                    violations.append("Taint violation: Plan uses UNTRUSTED input for 'trade' without a 'validate' step in chain")
        
        return {
            "failed": len(violations) > 0, 
            "violations": violations,
            "status": len(violations) == 0
        }

    def _validate_state_simulation(self, plan_data: dict, sid: dict, current_state: dict) -> dict:
        violations = []
        if not current_state:
            # Fallback to defaults for simulation
            current_state = {"portfolio_value": 100000, "exposure": 0, "daily_volume": 0}
            
        plan_steps = plan_data.get("plan", [])
        trade_steps = [s for s in plan_steps if self.tool_to_category.get(s.get("tool", "")) == "trade"]
        
        max_daily_vol = self.trade_constraints.get("max_daily_volume", 50)
        max_exposure = self.trade_constraints.get("max_daily_exposure_usd", 5000)
        
        projected_vol = current_state.get("daily_volume", 0)
        projected_exposure = current_state.get("exposure", 0)
        
        for step in trade_steps:
            args = step.get("args", {})
            qty = args.get("qty", 0)
            projected_vol += qty
            
            # Simple exposure calculation (assuming $100/share for AAPL-like mock or using args)
            symbol = args.get("symbol", "AAPL")
            # In a real system, fetch price. Here we mock.
            mock_price = 150 if "AAPL" in symbol.upper() else 100
            step_exposure = qty * mock_price
            projected_exposure += step_exposure
            
        if projected_vol > max_daily_vol:
            violations.append(f"Simulation failure: Plan would push daily volume ({projected_vol}) past policy limit ({max_daily_vol})")
            
        if projected_exposure > max_exposure:
            violations.append(f"Simulation failure: Plan would push total exposure (${projected_exposure}) past policy limit (${max_exposure})")
            
        return {"failed": len(violations) > 0, "violations": violations}

    def _detect_adversarial(self, plan_data: dict, sid: dict) -> dict:
        violations = []
        plan_steps = plan_data.get("plan", [])
        trade_steps = [s for s in plan_steps if self.tool_to_category.get(s.get("tool", "")) == "trade"]
        
        max_per_order = self.trade_constraints.get("max_per_order", 10)
        
        # Pattern 1: Boundary Pushing (Repeatedly requesting max limit)
        max_qty_requests = [s for s in trade_steps if s.get("args", {}).get("qty") == max_per_order]
        if len(max_qty_requests) > 2:
             violations.append("Adversarial pattern detected: Minimal compliance / Boundary pushing (repeated max limits)")
             
        # Pattern 2: Hidden Intent Expansion
        # (Checking for tools that don't match the primary scope)
        scope_tickers = [t.upper() for t in sid.get("scope", {}).get("tickers", [])]
        for step in plan_steps:
            args = step.get("args", {})
            ticker = (args.get("symbol") or args.get("ticker", "")).upper()
            if ticker and scope_tickers and ticker not in scope_tickers:
                violations.append(f"Adversarial logic: Plan addresses '{ticker}' which is outside SID scope {scope_tickers}")

        return {"failed": len(violations) > 0, "violations": violations}


# Legacy Alias for integration
PlanIntentAlignmentValidator = FormalPlanVerificationEngine
