"""
Alpaca Paper Trading Client
All calls go through Layer 9 (enforxguard_output.py) before firing.
Uses alpaca-trade-api library with paper trading endpoint.
"""

from __future__ import annotations
import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

logger = logging.getLogger(__name__)

ALPACA_BASE_URL   = os.getenv("ALPACA_BASE_URL",   "https://paper-api.alpaca.markets")
ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY",    "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")

class AlpacaClient:
    def __init__(self):
        self._api = self._connect()

    def _connect(self):
        """Try alpaca-trade-api first, then alpaca-py. Returns None if unconfigured."""
        if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
            logger.warning("Alpaca credentials not set")
            return None

        # Try alpaca-trade-api (older, more common)
        try:
            import alpaca_trade_api as tradeapi
            api = tradeapi.REST(
                ALPACA_API_KEY,
                ALPACA_SECRET_KEY,
                ALPACA_BASE_URL,
                api_version="v2",
            )
            api.get_account()   # connectivity check
            logger.info("Connected via alpaca-trade-api")
            return api
        except ImportError:
            pass
        except Exception as exc:
            logger.warning("alpaca-trade-api connect failed: %s", exc)

        # Try alpaca-py (newer SDK)
        try:
            from alpaca.trading.client import TradingClient
            client = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)
            client.get_account()
            logger.info("Connected via alpaca-py")
            return ("alpaca-py", client)
        except ImportError:
            pass
        except Exception as exc:
            logger.warning("alpaca-py connect failed: %s", exc)

        return None

    # ── Public API ──────────────────────────────────────────────────────────

    def place_order(
        self,
        ticker:     str,
        qty:        int,
        side:       str,
        order_type: str = "market",
        limit_price: float | None = None,
    ) -> dict:
        """Place an order via Alpaca Paper Trading API."""
        if self._api is None:
            raise ConnectionError(
                "Cannot place order: Alpaca API not configured. "
                "Set ALPACA_API_KEY and ALPACA_SECRET_KEY in .env"
            )

        # alpaca-py tuple format
        if isinstance(self._api, tuple) and self._api[0] == "alpaca-py":
            return self._place_alpacapy(self._api[1], ticker, qty, side, order_type, limit_price)

        # alpaca-trade-api
        return self._place_tradeapi(self._api, ticker, qty, side, order_type, limit_price)

    def get_positions(self) -> list[dict]:
        if self._api is None:
            raise ConnectionError("Cannot get positions: Alpaca API not configured.")
        try:
            if isinstance(self._api, tuple):
                positions = self._api[1].get_all_positions()
                return [{"symbol": p.symbol, "qty": float(p.qty), "market_value": float(p.market_value)}
                        for p in positions]
            positions = self._api.list_positions()
            return [{"symbol": p.symbol, "qty": float(p.qty), "market_value": float(p.market_value)}
                    for p in positions]
        except Exception as exc:
            return [{"error": str(exc)}]

    def get_account(self) -> dict:
        if self._api is None:
            raise ConnectionError("Cannot get account: Alpaca API not configured.")
        try:
            if isinstance(self._api, tuple):
                acc = self._api[1].get_account()
            else:
                acc = self._api.get_account()
            return {
                "cash":            float(acc.cash),
                "portfolio_value": float(acc.portfolio_value),
                "buying_power":    float(acc.buying_power),
                "status":          acc.status,
            }
        except Exception as exc:
            return {"error": str(exc)}

    def cancel_all_orders(self) -> dict:
        if self._api is None:
            raise ConnectionError("Cannot cancel orders: Alpaca API not configured.")
        try:
            if isinstance(self._api, tuple):
                self._api[1].cancel_orders()
            else:
                self._api.cancel_all_orders()
            return {"status": "OK", "cancelled": "all"}
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    # ── Private helpers ──────────────────────────────────────────────────────

    def _place_tradeapi(self, api, ticker, qty, side, order_type, limit_price) -> dict:
        try:
            kwargs = {
                "symbol":        ticker.upper(),
                "qty":           str(qty),
                "side":          side,
                "type":          order_type,
                "time_in_force": "day",
            }
            if order_type == "limit" and limit_price:
                kwargs["limit_price"] = str(limit_price)
            order = api.submit_order(**kwargs)
            return {
                "status":      "SUBMITTED",
                "order_id":    order.id,
                "symbol":      order.symbol,
                "qty":         float(order.qty),
                "side":        order.side,
                "type":        order.type,
                "filled_qty":  float(order.filled_qty or 0),
                "timestamp":   datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            logger.error("Alpaca order failed: %s", exc)
            return {"status": "ERROR", "error": str(exc)}

    def _place_alpacapy(self, client, ticker, qty, side, order_type, limit_price) -> dict:
        try:
            from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce
            side_enum = OrderSide.BUY if side == "buy" else OrderSide.SELL
            if order_type == "limit" and limit_price:
                req   = LimitOrderRequest(symbol=ticker.upper(), qty=qty,
                                          side=side_enum, time_in_force=TimeInForce.DAY,
                                          limit_price=limit_price)
            else:
                req   = MarketOrderRequest(symbol=ticker.upper(), qty=qty,
                                           side=side_enum, time_in_force=TimeInForce.DAY)
            order = client.submit_order(req)
            return {
                "status": "SUBMITTED", "order_id": str(order.id),
                "symbol": order.symbol, "qty": float(order.qty),
                "side": str(order.side), "type": str(order.order_type),
                "filled_qty": float(order.filled_qty or 0),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            logger.error("alpaca-py order failed: %s", exc)
            return {"status": "ERROR", "error": str(exc)}
