"""
Alpaca Paper Trading API Integration.
All trades go to paper-api.alpaca.markets — no real money.

API keys loaded from environment variables:
  ALPACA_API_KEY
  ALPACA_SECRET_KEY
  ALPACA_BASE_URL (default: https://paper-api.alpaca.markets)
"""

import os
from datetime import datetime, timezone


class AlpacaTrader:
    def __init__(self):
        self._client = None
        self._setup()

    def _setup(self):
        """Initialize Alpaca client. Gracefully handles missing keys."""
        try:
            from alpaca.trading.client import TradingClient
            from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce

            api_key = os.getenv("ALPACA_API_KEY", "")
            secret_key = os.getenv("ALPACA_SECRET_KEY", "")

            if not api_key or not secret_key:
                return

            self._client = TradingClient(api_key, secret_key, paper=True)
            self._MarketOrderRequest = MarketOrderRequest
            self._LimitOrderRequest = LimitOrderRequest
            self._OrderSide = OrderSide
            self._TimeInForce = TimeInForce
        except (ImportError, Exception):
            pass

    def buy(self, symbol: str, qty: int, order_type: str = "market", limit_price: float = None) -> dict:
        """Place a buy order."""
        return self._place_order(symbol, qty, "buy", order_type, limit_price)

    def sell(self, symbol: str, qty: int, order_type: str = "market", limit_price: float = None) -> dict:
        """Place a sell order."""
        return self._place_order(symbol, qty, "sell", order_type, limit_price)

    def _place_order(self, symbol: str, qty: int, side: str, order_type: str, limit_price: float = None) -> dict:
        """Internal order placement with demo fallback."""
        if not self._client:
            return self._demo_order(symbol, qty, side, order_type)

        try:
            side_enum = self._OrderSide.BUY if side == "buy" else self._OrderSide.SELL
            if order_type == "market":
                request = self._MarketOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=side_enum,
                    time_in_force=self._TimeInForce.DAY
                )
            else:
                request = self._LimitOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=side_enum,
                    time_in_force=self._TimeInForce.DAY,
                    limit_price=limit_price or 0
                )
            order = self._client.submit_order(request)
            return {
                "status": "SUBMITTED",
                "order_id": str(order.id),
                "symbol": symbol,
                "qty": qty,
                "side": side,
                "type": order_type,
                "alpaca_status": str(order.status),
                "submitted_at": datetime.now(timezone.utc).isoformat(),
                "demo": False
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "error": str(e),
                "symbol": symbol,
                "qty": qty,
                "side": side,
                "demo": False
            }

    def get_positions(self) -> list:
        """Get all open positions."""
        if not self._client:
            return [{"demo": True, "note": "No API keys configured"}]
        try:
            positions = self._client.get_all_positions()
            return [
                {
                    "symbol": p.symbol,
                    "qty": float(p.qty),
                    "market_value": float(p.market_value),
                    "unrealized_pl": float(p.unrealized_pl)
                }
                for p in positions
            ]
        except Exception as e:
            return [{"error": str(e)}]

    def get_account(self) -> dict:
        """Get account info."""
        if not self._client:
            return {"demo": True, "portfolio_value": 100000.0, "cash": 100000.0}
        try:
            account = self._client.get_account()
            return {
                "portfolio_value": float(account.portfolio_value),
                "cash": float(account.cash),
                "buying_power": float(account.buying_power),
                "status": str(account.status)
            }
        except Exception as e:
            return {"error": str(e)}

    def cancel_all_orders(self) -> dict:
        """Cancel all open orders."""
        if not self._client:
            return {"demo": True, "cancelled": 0}
        try:
            self._client.cancel_orders()
            return {"status": "OK", "note": "All open orders cancelled"}
        except Exception as e:
            return {"error": str(e)}

    def _demo_order(self, symbol: str, qty: int, side: str, order_type: str) -> dict:
        """Return a demo order when no API keys are configured."""
        return {
            "status": "DEMO_SUBMITTED",
            "order_id": f"DEMO-{datetime.now(timezone.utc).strftime('%H%M%S')}",
            "symbol": symbol,
            "qty": qty,
            "side": side,
            "type": order_type,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "demo": True,
            "note": "Demo mode — set ALPACA_API_KEY and ALPACA_SECRET_KEY for real paper trading"
        }
