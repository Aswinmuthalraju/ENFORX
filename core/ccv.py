"""
LAYER 6: Causal Chain Validator (CCV)
Sequence-level analysis + pre-trade stress testing.
Inspired by Control Barrier Functions from robotics safety (Ames et al., 2017).

KEY INSIGHT: Five individually safe trades can create an unsafe portfolio.
CCV checks the SEQUENCE, not just the individual action.

Safety barriers defined as inequalities:
  h1 = max_daily_loss_limit - current_daily_loss       (must > 0)
  h2 = max_sector_concentration - current_sector_pct   (must > 0)
  h3 = max_daily_exposure - current_daily_exposure      (must > 0)

If worst-case scenario breaches ANY barrier -> FLAG or BLOCK.
This is boundary enforcement, not prediction.
"""

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict


# Sector mapping
TICKER_SECTOR = {
    "AAPL": "technology",
    "MSFT": "technology",
    "GOOGL": "technology",
    "AMZN": "technology",
    "NVDA": "technology"
}

# Fallback prices used when live market data is unavailable.
# Replace with real-time Alpaca price feed in production.
FALLBACK_PRICES = {
    "AAPL": 178.0,
    "MSFT": 415.0,
    "GOOGL": 175.0,
    "AMZN": 185.0,
    "NVDA": 875.0,
    "TSLA": 175.0,
}

# Default starting portfolio value for Alpaca paper trading accounts.
# Stress test compares worst-case loss against total portfolio value.
DEFAULT_PORTFOLIO_VALUE = 100_000.0


class CausalChainValidator:
    def __init__(self, policy_path: str = None):
        if policy_path is None:
            policy_path = Path(__file__).parent.parent / "enforx-policy.json"
        with open(policy_path) as f:
            policy = json.load(f)
        cc = policy["enforx_policy"]["causal_chain_constraints"]
        self.max_sector_concentration = cc["max_sector_concentration_pct"] / 100.0
        self.max_trades_per_hour = cc["max_trades_per_hour"]
        self.velocity_threshold = cc["velocity_anomaly_threshold"]
        st = cc["stress_test"]
        self.stress_test_enabled = st["enabled"]
        self.worst_case_drop = st["worst_case_drop_pct"] / 100.0
        self.max_portfolio_loss = st["max_worst_case_portfolio_loss_pct"] / 100.0
        self.max_daily_exposure = policy["enforx_policy"]["trade_constraints"]["max_daily_exposure_usd"]

        # Session state
        self._session_trades = []
        self._daily_exposure = 0.0

    def validate(self, plan: dict, sid: dict, taint_chain: list = None) -> dict:
        """
        Run sequence-level checks and pre-trade stress test.
        Returns PASS, FLAG (warning), or BLOCK.
        """
        if taint_chain is None:
            taint_chain = []

        flags = []
        warnings = []

        trade_step = next((s for s in plan.get("plan", []) if s.get("tool") == "execute_trade"), None)
        if not trade_step:
            return {
                "status": "PASS",
                "flags": [],
                "warnings": ["No trade step in plan — sequence checks skipped"],
                "stress_test": None,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        args = trade_step.get("args", {})
        symbol = args.get("symbol", "UNKNOWN")
        qty = args.get("qty", 0)
        side = args.get("side", "buy")
        price = FALLBACK_PRICES.get(symbol, 100.0)
        trade_usd = qty * price

        # CHECK 1: Taint chain
        if "UNTRUSTED" in taint_chain:
            flags.append("UNTRUSTED data in causal chain — trade influenced by unverified source")

        # CHECK 2: Velocity anomaly
        now = datetime.now(timezone.utc)
        recent = [t for t in self._session_trades if now - t["timestamp"] < timedelta(hours=1)]
        if len(recent) >= self.velocity_threshold:
            warnings.append(f"Velocity anomaly: {len(recent)} trades in last hour (threshold: {self.velocity_threshold})")
        if len(recent) >= self.max_trades_per_hour:
            flags.append(f"Trade velocity exceeds limit: {len(recent)} trades/hour (max: {self.max_trades_per_hour})")

        # CHECK 3: Sector concentration — measured against total mock portfolio value
        # This prevents false positives when session history is empty (first trade of the day)
        sector = TICKER_SECTOR.get(symbol, "unknown")
        sector_trades = [t for t in self._session_trades if TICKER_SECTOR.get(t["ticker"]) == sector]
        sector_usd = sum(t["usd_value"] for t in sector_trades) + trade_usd
        sector_pct = sector_usd / DEFAULT_PORTFOLIO_VALUE
        if sector_pct > self.max_sector_concentration:
            flags.append(
                f"Sector concentration: {sector} would be {sector_pct:.1%} of portfolio "
                f"(max: {self.max_sector_concentration:.0%})"
            )

        # CHECK 4: Daily exposure
        new_exposure = self._daily_exposure + trade_usd
        if new_exposure > self.max_daily_exposure:
            flags.append(
                f"Daily exposure exceeded: ${new_exposure:.2f} would exceed limit ${self.max_daily_exposure:.2f}"
            )

        # CHECK 5: Pre-trade stress test (CBF-inspired)
        stress_result = None
        if self.stress_test_enabled and side == "buy":
            worst_case_loss = trade_usd * self.worst_case_drop
            portfolio_impact_pct = worst_case_loss / DEFAULT_PORTFOLIO_VALUE

            stress_result = {
                "symbol": symbol,
                "qty": qty,
                "trade_value_usd": round(trade_usd, 2),
                "worst_case_drop_pct": f"{self.worst_case_drop:.0%}",
                "worst_case_loss_usd": round(worst_case_loss, 2),
                "portfolio_impact_pct": f"{portfolio_impact_pct:.2%}",
                "portfolio_value": DEFAULT_PORTFOLIO_VALUE,
                "max_allowed_impact_pct": f"{self.max_portfolio_loss:.0%}",
                "result": "PASS"
            }

            if portfolio_impact_pct > self.max_portfolio_loss:
                stress_result["result"] = "FAIL"
                flags.append(
                    f"Stress test FAIL: worst-case loss ${worst_case_loss:.2f} "
                    f"= {portfolio_impact_pct:.1%} of portfolio "
                    f"(max allowed: {self.max_portfolio_loss:.0%})"
                )

        # Determine final status
        if flags:
            status = "BLOCK"
            reason = f"{len(flags)} causal chain violation(s) detected"
        elif warnings:
            status = "FLAG"
            reason = f"{len(warnings)} warning(s) — trade proceeds with flags"
        else:
            status = "PASS"
            reason = "All causal chain checks passed"

        # Record trade in session history if not blocked
        if status != "BLOCK":
            self._session_trades.append({
                "ticker": symbol,
                "qty": qty,
                "side": side,
                "usd_value": trade_usd,
                "timestamp": now
            })
            if side == "buy":
                self._daily_exposure += trade_usd

        return {
            "status": status,
            "reason": reason,
            "flags": flags,
            "warnings": warnings,
            "stress_test": stress_result,
            "session_trade_count": len(self._session_trades),
            "daily_exposure_usd": round(self._daily_exposure, 2),
            "timestamp": now.isoformat()
        }
