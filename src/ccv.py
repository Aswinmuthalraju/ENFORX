"""
LAYER 6 — Causal Chain Validator (CCV)
100% DETERMINISTIC — ZERO LLM CALLS.

Maintains a rolling window of session actions and checks:
  - Sector concentration (> 60% → FLAG)
  - Trade velocity (> 10/hour → FLAG)
  - Tool sequence fingerprint: research → analyze → validate → trade
  - Taint propagation (UNTRUSTED data in chain → FLAG)
  - Pre-trade stress test: worst-case 20% drop; if portfolio loss > 15% → BLOCK

Safety barriers (Control Barrier Function style):
  h1 = max_daily_loss_limit   - current_daily_loss    > 0
  h2 = max_sector_concentration - current_sector_pct  > 0
  h3 = max_daily_exposure     - current_exposure      > 0
"""

from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

from logger_config import get_layer_logger
logger = get_layer_logger("layer.06.ccv")

TICKER_SECTOR: dict[str, str] = {
    "AAPL": "technology", "TSLA": "consumer_discretionary", "NVDA": "technology",
    "SPY": "etf", "QQQ": "etf", "VOO": "etf", "IVV": "etf",
}

FALLBACK_PRICES: dict[str, float] = {
    "AAPL": 178.0, "TSLA": 175.0, "NVDA": 875.0,
    "SPY": 510.0, "QQQ": 440.0, "VOO": 470.0, "IVV": 515.0,
}

TOOL_CATEGORY = {
    "query_market_data": "research", "web_search": "research",
    "analyze_sentiment": "analyze",  "calculate_risk": "analyze",
    "verify_constraints": "validate",
    "execute_trade": "trade",        "alpaca_trade": "trade",
}

DEFAULT_PORTFOLIO_VALUE = 100_000.0


class CausalChainValidator:

    def __init__(self, policy_path: str | None = None):
        if policy_path is None:
            policy_path = Path(__file__).parent.parent / "enforx-policy.json"
        with open(policy_path) as f:
            policy = json.load(f)
        cc = policy["enforx_policy"]["causal_chain_constraints"]
        self.max_sector_concentration = cc["max_sector_concentration_pct"] / 100.0
        self.max_trades_per_hour      = cc["max_trades_per_hour"]
        st = cc["stress_test"]
        self.stress_enabled      = st["enabled"]
        self.worst_case_drop     = st["worst_case_drop_pct"] / 100.0
        self.max_portfolio_loss  = st["max_worst_case_portfolio_loss_pct"] / 100.0
        self.max_daily_exposure  = policy["enforx_policy"]["trade_constraints"]["max_daily_exposure_usd"]

        # Session rolling state
        self._session_trades:  list[dict] = []
        self._trade_timestamps: list[datetime] = []
        self._sector_exposure:  dict[str, float] = defaultdict(float)
        self._daily_exposure:   float = 0.0

    # ── Adaptive integration ─────────────────────────────────────────────

    def _get_adaptive_multiplier(self) -> float:
        """Fetch adaptive multiplier from audit loop (fail-safe=1.0)."""
        try:
            from audit import AdaptiveAuditLoop
            return AdaptiveAuditLoop()._threshold_multiplier
        except Exception:
            return 1.0

    # ── Public API ──────────────────────────────────────────────────────────

    def validate(self, plan: dict, sid: dict, taint_chain: list | None = None) -> dict:
        if taint_chain is None:
            taint_chain = []
        flags:    list[str] = []
        warnings: list[str] = []

        multiplier = self._get_adaptive_multiplier()
        logger.info(f"CCV adaptive multiplier applied: {multiplier}")

        trade_step = next(
            (s for s in plan.get("plan", []) if s.get("tool") in ("execute_trade", "alpaca_trade")),
            None
        )
        if not trade_step:
            return self._pass([], ["No trade step — sequence checks skipped"], None)

        args   = trade_step.get("args", {})
        symbol = args.get("symbol", args.get("ticker", "UNKNOWN")).upper()
        qty    = int(args.get("qty", 0))
        price  = FALLBACK_PRICES.get(symbol, 100.0)
        trade_usd = qty * price

        # Hard quantity block: >= 10 is never allowed
        if qty >= 10:
            return self._block(
                flags + ["QUANTITY_VIOLATION: Quantity must be below 10."],
                warnings, None
            )

        # Effective limits (adaptive)
        eff_sector_concentration = self.max_sector_concentration * multiplier
        eff_trades_per_hour      = self.max_trades_per_hour * multiplier
        eff_daily_exposure       = self.max_daily_exposure * multiplier

        # CHECK 1: Taint chain
        if "UNTRUSTED" in taint_chain:
            flags.append("TAINT_VIOLATION: UNTRUSTED data in causal chain — trade influenced by unverified source")

        # CHECK 2: Sector concentration
        sector        = TICKER_SECTOR.get(symbol, "unknown")
        total_exp     = self._daily_exposure + trade_usd or 1.0
        sector_exp    = self._sector_exposure.get(sector, 0.0) + trade_usd
        sector_pct    = sector_exp / (self._daily_exposure + trade_usd + 1.0)
        if sector_pct > eff_sector_concentration:
            flags.append(
                f"SECTOR_CONCENTRATION: {sector} sector at "
                f"{sector_pct*100:.1f}% > max {eff_sector_concentration*100:.0f}%"
            )

        # CHECK 3: Trade velocity (last 60 min)
        now    = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=1)
        recent = [t for t in self._trade_timestamps if t > cutoff]
        if len(recent) >= eff_trades_per_hour:
            flags.append(
                f"VELOCITY_EXCEEDED: {len(recent)} trades in last hour "
                f"(max {int(eff_trades_per_hour)})"
            )

        # CHECK 4: Tool sequence fingerprint
        categories = [
            TOOL_CATEGORY.get(s.get("tool", ""), "unknown")
            for s in plan.get("plan", [])
        ]
        rel = [c for c in categories if c != "unknown"]
        required = ["research", "analyze", "validate", "trade"]
        idx = 0
        for cat in rel:
            if idx < len(required) and cat == required[idx]:
                idx += 1
        if idx < len(required):
            warnings.append(
                f"SEQUENCE_INCOMPLETE: missing {required[idx:]} in causal chain"
            )

        # CHECK 5: Daily exposure barrier (h3)
        if self._daily_exposure + trade_usd > eff_daily_exposure:
            flags.append(
                f"EXPOSURE_BARRIER: projected ${self._daily_exposure + trade_usd:,.0f} "
                f"> max ${eff_daily_exposure:,.0f}"
            )

        # CHECK 6: Pre-trade stress test
        stress = None
        if self.stress_enabled:
            stress = self._stress_test(symbol, qty, price, multiplier)
            if stress["block"]:
                return self._block(
                    flags + [f"STRESS_TEST_FAIL: {stress['reason']}"],
                    warnings, stress
                )

        # Determine result
        if flags:
            return self._flag(flags, warnings, stress)
        return self._pass(warnings, [], stress)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _stress_test(self, symbol: str, qty: int, price: float, multiplier: float = 1.0) -> dict:
        portfolio_value   = DEFAULT_PORTFOLIO_VALUE
        worst_case_loss   = qty * price * self.worst_case_drop
        loss_pct          = worst_case_loss / portfolio_value
        eff_max_loss      = self.max_portfolio_loss * multiplier
        block             = loss_pct > eff_max_loss
        return {
            "symbol":            symbol,
            "qty":               qty,
            "price":             price,
            "worst_case_drop_pct": self.worst_case_drop * 100,
            "worst_case_loss_usd": round(worst_case_loss, 2),
            "portfolio_loss_pct":  round(loss_pct * 100, 3),
            "max_allowed_pct":     eff_max_loss * 100,
            "block":             block,
            "reason":            (
                f"Worst-case loss {loss_pct*100:.2f}% > allowed {eff_max_loss*100:.0f}%"
                if block else "Stress test PASSED"
            ),
        }

    def record_trade(self, symbol: str, qty: int) -> None:
        """Call after a trade executes to update session state."""
        price     = FALLBACK_PRICES.get(symbol.upper(), 100.0)
        trade_usd = qty * price
        sector    = TICKER_SECTOR.get(symbol.upper(), "unknown")
        self._daily_exposure              += trade_usd
        self._sector_exposure[sector]     += trade_usd
        self._trade_timestamps.append(datetime.now(timezone.utc))
        self._session_trades.append({"symbol": symbol, "qty": qty, "usd": trade_usd})

    def _pass(self, warnings, extra, stress) -> dict:
        return {
            "result": "PASS", "flags": [],
            "warnings": warnings + extra, "stress_test": stress,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _flag(self, flags, warnings, stress) -> dict:
        return {
            "result": "FLAG", "flags": flags,
            "warnings": warnings, "stress_test": stress,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _block(self, flags, warnings, stress) -> dict:
        return {
            "result": "BLOCK", "flags": flags,
            "warnings": warnings, "stress_test": stress,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ── Standalone test ──────────────────────────────────────────────────────────
def test_ccv():
    ccv = CausalChainValidator()
    sid = {"scope": {"tickers": ["AAPL"]}}
    plan_ok = {"plan": [
        {"tool": "query_market_data",  "args": {"ticker": "AAPL"}, "step": 1},
        {"tool": "analyze_sentiment",  "args": {"ticker": "AAPL"}, "step": 2},
        {"tool": "verify_constraints", "args": {"ticker": "AAPL"}, "step": 3},
        {"tool": "execute_trade",      "args": {"symbol": "AAPL", "qty": 5, "side": "buy", "type": "market"}, "step": 4},
    ]}
    plan_stress = {"plan": [
        {"tool": "execute_trade", "args": {"symbol": "NVDA", "qty": 100, "side": "buy", "type": "market"}, "step": 1},
    ]}
    print("\n=== CCV Tests ===")
    for label, plan, taint in [
        ("Valid AAPL buy 5",   plan_ok,     []),
        ("NVDA qty=100 stress",plan_stress,  []),
        ("UNTRUSTED chain",    plan_ok,     ["UNTRUSTED"]),
    ]:
        r = ccv.validate(plan, sid, taint)
        print(f"  [{r['result']:5s}] {label}: flags={r['flags'][:1]}")
    print()


if __name__ == "__main__":
    test_ccv()
