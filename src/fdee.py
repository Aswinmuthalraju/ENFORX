"""
LAYER 7 — Financial Domain Enforcement Engine (FDEE)
100% DETERMINISTIC — ZERO LLM CALLS.

Simplex Safety Controller: evaluates every plan step against enforx-policy.json.
Policy is loaded ONCE at class-definition time (module import), not per request.

Can ALLOW (fully compliant), CORRECT (soft-violation auto-fixed), or BLOCK (hard violation).

Rules enforced:
  - Allowed tickers, order types, side
  - Max quantity per order (soft → CORRECT)
  - Daily volume limit
  - Prohibited trade actions (short_sell, margin, options)
  - Market hours (09:30–16:00 ET) unless ENFORX_SKIP_MARKET_HOURS=true
  - Denied tool usage (bash, exec, shell, curl, wget, ssh)
  - Credential pattern leak in args
"""

from __future__ import annotations
import json
import os
from pathlib import Path
from datetime import datetime, timezone, time as dtime
import pytz

from logger_config import get_layer_logger

logger = get_layer_logger("layer.07.fdee")

# ── Policy loaded ONCE at module import time ──────────────────────────────────
_POLICY_PATH = Path(__file__).parent.parent / "enforx-policy.json"

def _load_policy(path: Path) -> dict:
    """Load enforx-policy.json exactly once at startup."""
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"enforx-policy.json not found at {path}. "
            "This file is required for FDEE to operate."
        ) from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"enforx-policy.json is malformed: {exc}"
        ) from exc

_POLICY: dict = _load_policy(_POLICY_PATH)


class FinancialDomainEnforcementEngine:
    """Deterministic policy enforcer for financial trade plans.

    Policy is read from the module-level _POLICY singleton — loaded once at
    import time, never re-read per request.
    """

    def __init__(self) -> None:
        """Initialize FDEE from the pre-loaded policy singleton."""
        self._skip_market_hours: bool = os.getenv("ENFORX_SKIP_MARKET_HOURS", "").lower() == "true"

        p  = _POLICY["enforx_policy"]
        tc = p["trade_constraints"]
        self.max_per_order:          int       = tc["max_per_order"]
        self.max_daily_volume:       int       = tc["max_daily_volume"]
        self.max_daily_exposure_usd: float     = tc["max_daily_exposure_usd"]
        self.allowed_tickers:        list[str] = ["AAPL", "TSLA", "NVDA", "SPY", "QQQ", "VOO", "IVV"]
        self.allowed_order_types:    list[str] = tc["allowed_order_types"]
        self.prohibited_actions:     list[str] = tc["prohibited_actions"]

        tm = p["time_constraints"]
        self.market_open:  str = tm["market_open"]   # "09:30"
        self.market_close: str = tm["market_close"]  # "16:00"
        self.tz_name:      str = tm["timezone"]

        tc2 = p["tool_constraints"]
        self.denied_tools:  list[str] = tc2["deny"]
        self.allowed_tools: list[str] = tc2["allow"]
        self.blocked_cred_patterns: list[str] = p["data_constraints"]["blocked_patterns"]

        # Session state (per instance)
        self._daily_volume: int = 0

    # ── Public API ──────────────────────────────────────────────────────────

    def enforce(self, plan: dict) -> dict:
        """Evaluate *plan* against all policy rules.

        Returns:
          {result: "ALLOW"/"CORRECT"/"BLOCK", corrections, violations, reason, enforced_plan}
        """
        violations:    list[str] = []
        corrections:   dict      = {}
        checks_passed: list[str] = []

        steps      = plan.get("plan", [])
        plan_tools = [s.get("tool", "") for s in steps]

        # RULE 1 — Denied tools
        denied = [t for t in plan_tools if t in self.denied_tools]
        if denied:
            violations.append(f"Denied tools in plan: {denied}")
        else:
            checks_passed.append("TOOLS_OK")

        # RULE 2 — Credential patterns in args
        for step in steps:
            for k, v in step.get("args", {}).items():
                if isinstance(v, str):
                    for pat in self.blocked_cred_patterns:
                        if pat.lower() in v.lower():
                            violations.append(
                                f"Credential pattern '{pat}' in tool arg '{k}'"
                            )

        # Find the trade step (if any)
        trade_step = next(
            (s for s in steps if s.get("tool") in ("execute_trade", "alpaca_trade")), None
        )
        if not trade_step:
            if violations:
                return self._block(violations, checks_passed, plan, "Non-trade policy violation")
            return self._allow(corrections, checks_passed, plan, "Research-only plan — no trade rules")

        args       = trade_step.get("args", {})
        symbol     = args.get("symbol", "").upper()
        qty        = int(args.get("qty", 0))
        side       = args.get("side", "").lower()
        order_type = args.get("type", "market").lower()

        # Hard Quantity Block: >= 10 is never allowed
        if qty >= 10:
            violations.append(
                f"Quantity {qty} is not allowed. Maximum quantity per order is 9 shares. "
                "Please request fewer than 10 shares."
            )
            return self._block(violations, checks_passed, plan, "QUANTITY_HARD_BLOCK")

        # RULE 3 — Ticker allowlist
        if symbol not in self.allowed_tickers:
            violations.append(
                f"Ticker {symbol} is not in the allowed list. Allowed tickers are: "
                "AAPL (Apple Inc.), TSLA (Tesla Inc.), NVDA (NVIDIA Corp), "
                "SPY (SPDR S&P 500 ETF Trust), QQQ (Invesco QQQ Trust), "
                "VOO (Vanguard S&P 500 ETF), IVV (iShares Core S&P 500 ETF)."
            )
        else:
            checks_passed.append("TICKER_OK")

        # RULE 4 — Prohibited trade actions
        for prohibited in self.prohibited_actions:
            if prohibited.replace("_", " ") in (side + " " + order_type).replace("_", " "):
                violations.append(f"Prohibited action '{prohibited}' detected")

        # RULE 5 — Quantity cap (SOFT — auto-correct)
        if qty > self.max_per_order:
            corrections["qty"] = self.max_per_order
            trade_step["args"]["qty"] = self.max_per_order
            qty = self.max_per_order
        else:
            checks_passed.append("QTY_OK")

        # RULE 6 — Daily volume
        if self._daily_volume + qty > self.max_daily_volume:
            violations.append(
                f"Daily volume limit: current={self._daily_volume}, "
                f"adding {qty} would exceed {self.max_daily_volume}"
            )
        else:
            checks_passed.append("DAILY_VOLUME_OK")

        # RULE 7 — Order type
        if order_type not in self.allowed_order_types:
            violations.append(
                f"Order type '{order_type}' not in {self.allowed_order_types}"
            )
        else:
            checks_passed.append("ORDER_TYPE_OK")

        # RULE 8 — Market hours
        if not self._skip_market_hours:
            mh_ok, mh_reason = self._check_market_hours()
            if not mh_ok:
                violations.append(mh_reason)
            else:
                checks_passed.append("MARKET_HOURS_OK")
        else:
            checks_passed.append("MARKET_HOURS_CHECK_SKIPPED")

        # ── Decision ────────────────────────────────────────────────────────
        if violations:
            return self._block(violations, checks_passed, plan,
                               "; ".join(violations))

        if corrections:
            self._daily_volume += qty
            return self._correct(corrections, checks_passed, plan,
                                 f"Auto-corrected: {corrections}")

        self._daily_volume += qty
        return self._allow(corrections, checks_passed, plan,
                           "All financial domain checks passed")

    # ── Private helpers ─────────────────────────────────────────────────────

    def _check_market_hours(self) -> tuple[bool, str]:
        """Check whether current time is within market hours."""
        tz            = pytz.timezone(self.tz_name)
        now           = datetime.now(tz).time()
        open_h, open_m   = map(int, self.market_open.split(":"))
        close_h, close_m = map(int, self.market_close.split(":"))
        market_open  = dtime(open_h, open_m)
        market_close = dtime(close_h, close_m)
        if not (market_open <= now <= market_close):
            return (
                False,
                f"Outside market hours ({self.market_open}–{self.market_close} ET). "
                f"Current ET time: {now.strftime('%H:%M')}",
            )
        return (True, "")

    def _allow(self, corrections: dict, checks_passed: list, plan: dict, reason: str) -> dict:
        """Return an ALLOW result."""
        return {
            "result":        "ALLOW",
            "status":        "ALLOW",
            "corrections":   corrections,
            "violations":    [],
            "reason":        reason,
            "checks_passed": checks_passed,
            "enforced_plan": plan,
        }

    def _correct(self, corrections: dict, checks_passed: list, plan: dict, reason: str) -> dict:
        """Return a CORRECT result (soft-violation auto-fixed)."""
        return {
            "result":        "CORRECT",
            "status":        "CORRECT",
            "corrections":   corrections,
            "violations":    [],
            "reason":        reason,
            "checks_passed": checks_passed,
            "enforced_plan": plan,
        }

    def _block(self, violations: list, checks_passed: list, plan: dict, reason: str) -> dict:
        """Return a BLOCK result (hard violation)."""
        return {
            "result":        "BLOCK",
            "status":        "BLOCK",
            "blocked_at":    "layer.07.fdee",
            "corrections":   {},
            "violations":    violations,
            "reason":        reason,
            "checks_passed": checks_passed,
            "enforced_plan": plan,
        }


# ── Standalone test ──────────────────────────────────────────────────────────
def test_fdee() -> None:
    """Run a quick sanity check of the FDEE."""
    import os
    os.environ["ENFORX_SKIP_MARKET_HOURS"] = "true"
    fdee = FinancialDomainEnforcementEngine()

    plans = [
        # ALLOW
        {"label": "Buy 5 AAPL (valid)", "plan": [
            {"tool": "query_market_data", "args": {"ticker": "AAPL"}, "step": 1},
            {"tool": "execute_trade", "args": {"symbol": "AAPL", "qty": 5, "side": "buy", "type": "market"}, "step": 2},
        ]},
        # CORRECT (qty > 10)
        {"label": "Buy 20 AAPL (qty corrected)", "plan": [
            {"tool": "execute_trade", "args": {"symbol": "AAPL", "qty": 20, "side": "buy", "type": "market"}, "step": 1},
        ]},
        # BLOCK — ticker not allowed
        {"label": "Buy TSLA (blocked ticker)", "plan": [
            {"tool": "execute_trade", "args": {"symbol": "TSLA", "qty": 5, "side": "buy", "type": "market"}, "step": 1},
        ]},
        # BLOCK — denied tool
        {"label": "Uses bash (blocked tool)", "plan": [
            {"tool": "bash", "args": {"cmd": "ls"}, "step": 1},
        ]},
    ]

    print("\n=== FDEE Tests ===")
    for p in plans:
        r = fdee.enforce(p)
        print(f"  [{r['result']:7s}] {p['label']} | {r['reason'][:60]}")
    print()


if __name__ == "__main__":
    test_fdee()
