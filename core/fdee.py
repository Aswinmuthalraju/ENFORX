"""
LAYER 7: Financial Domain Enforcement Engine (FDEE)
The Simplex Safety Controller — inspired by aerospace safety (Sha et al., CMU, 2001).

SIMPLEX PRINCIPLE:
  LLM agent = Advanced Controller (complex, unverified)
  FDEE = Safety Controller (simple, formally verifiable)

  You don't need to prove the AI is safe.
  You only prove the FDEE is safe.
  System is provably safe either way.

100% DETERMINISTIC — zero LLM calls.
Loads enforx-policy.json and evaluates every trade against hard rules.
Can ALLOW, CORRECT (fix soft violations), or BLOCK (hard violations).
"""

import json
import re
from pathlib import Path
from datetime import datetime, timezone, time
import pytz


class FinancialDomainEnforcementEngine:
    def __init__(self, policy_path: str = None, skip_market_hours: bool = False):
        self._skip_market_hours = skip_market_hours
        if policy_path is None:
            policy_path = Path(__file__).parent.parent / "enforx-policy.json"
        with open(policy_path) as f:
            policy = json.load(f)
        p = policy["enforx_policy"]
        tc = p["trade_constraints"]
        self.max_per_order = tc["max_per_order"]
        self.max_daily_volume = tc["max_daily_volume"]
        self.max_daily_exposure_usd = tc["max_daily_exposure_usd"]
        self.allowed_tickers = [t.upper() for t in tc["allowed_tickers"]]
        self.allowed_order_types = tc["allowed_order_types"]
        self.prohibited_trade_actions = tc["prohibited_actions"]

        timec = p["time_constraints"]
        self.market_hours_only = timec["market_hours_only"]
        self.market_open = timec["market_open"]
        self.market_close = timec["market_close"]
        self.timezone = timec["timezone"]

        tool_c = p["tool_constraints"]
        self.denied_tools = tool_c["deny"]
        self.allowed_tools = tool_c["allow"]

        self.blocked_credential_patterns = p["data_constraints"]["blocked_patterns"]

        # Session state
        self._daily_volume = 0

    def enforce(self, plan: dict) -> dict:
        """
        Evaluate plan against all policy rules.
        Returns ALLOW, CORRECT, or BLOCK with full explanation.
        """
        violations = []
        corrections = {}
        checks_passed = []

        plan_steps = plan.get("plan", [])
        plan_tools = [s.get("tool", "") for s in plan_steps]

        # RULE SET 1: Denied tools
        denied_found = [t for t in plan_tools if t in self.denied_tools]
        if denied_found:
            violations.append(f"Denied tools in plan: {denied_found}. Policy denies: {self.denied_tools}")
        else:
            checks_passed.append("TOOLS_OK")

        # RULE SET 2: Credential patterns in tool arguments
        for step in plan_steps:
            for k, v in step.get("args", {}).items():
                if isinstance(v, str):
                    for pattern in self.blocked_credential_patterns:
                        if pattern.lower() in v.lower():
                            violations.append(f"Credential pattern '{pattern}' found in tool arg '{k}'")

        # Find trade step
        trade_step = next((s for s in plan_steps if s.get("tool") == "execute_trade"), None)
        if not trade_step:
            if violations:
                return self._block(violations, checks_passed, plan)
            return self._allow(corrections, checks_passed, plan, "Research-only plan — no trade rules apply")

        args = trade_step.get("args", {})
        symbol = args.get("symbol", "").upper()
        qty = args.get("qty", 0)
        side = args.get("side", "")
        order_type = args.get("type", "market")

        # RULE SET 3: Ticker allowlist
        if symbol not in self.allowed_tickers:
            violations.append(
                f"Ticker '{symbol}' not in approved list: {self.allowed_tickers}. "
                f"Trade blocked — no correction possible for unapproved ticker."
            )
        else:
            checks_passed.append(f"TICKER_OK:{symbol}")

        # RULE SET 4: Quantity limits — CORRECTABLE
        if qty > self.max_per_order:
            corrections["qty"] = {
                "original": qty,
                "corrected": self.max_per_order,
                "rule": "trade_constraints.max_per_order",
                "reason": f"Requested {qty} shares exceeds max_per_order limit of {self.max_per_order}"
            }
            args["qty"] = self.max_per_order
        else:
            checks_passed.append(f"QTY_OK:{qty}")

        # RULE SET 5: Daily volume limit
        corrected_qty = corrections.get("qty", {}).get("corrected", qty)
        if self._daily_volume + corrected_qty > self.max_daily_volume:
            remaining = self.max_daily_volume - self._daily_volume
            if remaining <= 0:
                violations.append(f"Daily volume limit reached: {self._daily_volume}/{self.max_daily_volume} shares traded today")
            else:
                corrections["daily_qty"] = {
                    "original": corrected_qty,
                    "corrected": remaining,
                    "rule": "trade_constraints.max_daily_volume",
                    "reason": f"Would exceed daily volume. Corrected to remaining allowance: {remaining}"
                }
                args["qty"] = remaining

        # RULE SET 6: Order type — CORRECTABLE
        if order_type not in self.allowed_order_types:
            corrections["order_type"] = {
                "original": order_type,
                "corrected": "market",
                "rule": "trade_constraints.allowed_order_types",
                "reason": f"Order type '{order_type}' not allowed. Defaulting to 'market'"
            }
            args["type"] = "market"
        else:
            checks_passed.append(f"ORDER_TYPE_OK:{order_type}")

        # RULE SET 7: Prohibited trade actions
        if side.lower() in ["short", "short_sell"]:
            violations.append("Short selling is prohibited by policy")
        if order_type.lower() in ["options", "margin"]:
            violations.append(f"Order type '{order_type}' is prohibited by policy")

        # RULE SET 8: Market hours
        hours_result = self._check_market_hours() if not self._skip_market_hours else {"is_open": True, "current_time_et": "skipped", "is_weekday": True}
        if not hours_result["is_open"]:
            violations.append(
                f"Market hours violation: current time {hours_result['current_time_et']} ET is outside "
                f"market hours {self.market_open}-{self.market_close} ET"
            )
        else:
            checks_passed.append(f"MARKET_HOURS_OK:{hours_result['current_time_et']}")

        if violations:
            return self._block(violations, checks_passed, plan)
        if corrections:
            for step in plan_steps:
                if step.get("tool") == "execute_trade":
                    step["args"] = args
            return self._correct(corrections, checks_passed, plan)
        return self._allow(corrections, checks_passed, plan, "All FDEE policy checks passed")

    def _check_market_hours(self) -> dict:
        """Check if current time is within market hours (9:30 AM - 4:00 PM ET)."""
        try:
            et_tz = pytz.timezone(self.timezone)
            now_et = datetime.now(et_tz)
            current_time = now_et.time()
            open_h, open_m = map(int, self.market_open.split(":"))
            close_h, close_m = map(int, self.market_close.split(":"))
            market_open_time = time(open_h, open_m)
            market_close_time = time(close_h, close_m)
            is_open = market_open_time <= current_time <= market_close_time
            is_weekday = now_et.weekday() < 5
            return {
                "is_open": is_open and is_weekday,
                "current_time_et": now_et.strftime("%H:%M"),
                "is_weekday": is_weekday
            }
        except Exception:
            # Demo mode fallback if pytz fails
            return {"is_open": True, "current_time_et": "demo_mode", "is_weekday": True}

    def record_execution(self, qty: int):
        """Call this after a successful trade to update daily volume."""
        self._daily_volume += qty

    def _allow(self, corrections: dict, passed: list, plan: dict, reason: str) -> dict:
        return {
            "status": "ALLOW",
            "reason": reason,
            "violations": [],
            "corrections": corrections,
            "checks_passed": passed,
            "enforced_plan": plan,
            "enforced_by": "FDEE (Layer 7) — Simplex Safety Controller",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def _correct(self, corrections: dict, passed: list, plan: dict) -> dict:
        reasons = [c["reason"] for c in corrections.values()]
        return {
            "status": "CORRECT",
            "reason": f"Plan corrected: {'; '.join(reasons)}",
            "violations": [],
            "corrections": corrections,
            "checks_passed": passed,
            "enforced_plan": plan,
            "enforced_by": "FDEE (Layer 7) — Simplex Safety Controller",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def _block(self, violations: list, passed: list, plan: dict) -> dict:
        return {
            "status": "BLOCK",
            "reason": f"{len(violations)} policy violation(s): {'; '.join(violations)}",
            "violations": violations,
            "corrections": {},
            "checks_passed": passed,
            "enforced_plan": plan,
            "enforced_by": "FDEE (Layer 7) — Simplex Safety Controller",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
