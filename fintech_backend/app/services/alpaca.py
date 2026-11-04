"""
A thin wrapper over the Alpaca Broker API and Alpaca market data: plain dicts in and out.

Alpaca is the licensed broker. Each Hoardrun customer gets their own brokerage account;
cash moves between it and Hoardrun's firm account by journal (JNLC). Tests swap the whole
broker for a fake.

Requests are never logged with their bodies, because opening an account sends a tax ID.
"""

import base64
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

import httpx

from ..config.settings import get_settings

logger = logging.getLogger(__name__)

BROKER = {"sandbox": "https://broker-api.sandbox.alpaca.markets", "live": "https://broker-api.alpaca.markets"}
DATA = {"sandbox": "https://data.sandbox.alpaca.markets", "live": "https://data.alpaca.markets"}
BAR_RANGES = {"1D": ("5Min", timedelta(days=1)), "1W": ("30Min", timedelta(days=7)),
              "1M": ("1Day", timedelta(days=31)), "1Y": ("1Week", timedelta(days=366))}


class AlpacaError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def configured() -> bool:
    settings = get_settings()
    return bool(settings.alpaca_broker_key and settings.alpaca_broker_secret and settings.alpaca_firm_account_id)


def broker_symbol(asset_type: str, symbol: str) -> str:
    """Hoardrun's BTC is Alpaca's BTC/USD for orders."""
    return f"{symbol}/USD" if asset_type == "crypto" else symbol


def position_symbol(asset_type: str, symbol: str) -> str:
    """...and BTCUSD in positions."""
    return f"{symbol}USD" if asset_type == "crypto" else symbol


class Alpaca:
    def __init__(self):
        settings = get_settings()
        env = "live" if settings.alpaca_env == "live" else "sandbox"
        token = base64.b64encode(f"{settings.alpaca_broker_key}:{settings.alpaca_broker_secret}".encode()).decode()
        self.headers = {"Authorization": f"Basic {token}", "Accept": "application/json"}
        self.broker, self.data = BROKER[env], DATA[env]
        self.firm = settings.alpaca_firm_account_id

    def _call(self, method: str, url: str, body: Optional[dict] = None, params: Optional[dict] = None):
        try:
            response = httpx.request(method, url, json=body, params=params, headers=self.headers, timeout=20)
        except httpx.HTTPError as error:
            logger.warning("Alpaca unreachable: %s %s", method, url.split("?")[0])
            raise AlpacaError(503, "The broker didn't respond. Try again.") from error
        if response.status_code >= 400:
            try:
                message = response.json().get("message") or ""
            except ValueError:
                message = ""
            # Only the status and Alpaca's short message: never the request body
            logger.warning("Alpaca %s %s -> %s %s", method, url.split("?")[0].replace(self.broker, ""), response.status_code, message[:200])
            raise AlpacaError(response.status_code, message or "The broker didn't accept that.")
        return response.json() if response.content else {}

    # Accounts
    def create_account(self, payload: dict) -> dict:
        return self._call("POST", f"{self.broker}/v1/accounts", payload)

    def account(self, account_id: str) -> dict:
        return self._call("GET", f"{self.broker}/v1/accounts/{account_id}")

    def trading_account(self, account_id: str) -> dict:
        return self._call("GET", f"{self.broker}/v1/trading/accounts/{account_id}/account")

    # Cash
    def journal(self, from_account: str, to_account: str, amount: Decimal, description: str) -> dict:
        return self._call("POST", f"{self.broker}/v1/journals", {
            "from_account": from_account, "to_account": to_account, "entry_type": "JNLC",
            "amount": f"{amount:.2f}", "description": description[:100],
        })

    # Trading
    def order(self, account_id: str, *, asset_type: str, symbol: str, side: str, notional: Decimal, client_id: str) -> dict:
        return self._call("POST", f"{self.broker}/v1/trading/accounts/{account_id}/orders", {
            "symbol": broker_symbol(asset_type, symbol), "notional": f"{notional:.2f}", "side": side, "type": "market",
            "time_in_force": "gtc" if asset_type == "crypto" else "day", "client_order_id": client_id,
        })

    def close_position(self, account_id: str, *, asset_type: str, symbol: str) -> dict:
        return self._call("DELETE", f"{self.broker}/v1/trading/accounts/{account_id}/positions/{position_symbol(asset_type, symbol)}")

    def get_order(self, account_id: str, order_id: str) -> dict:
        return self._call("GET", f"{self.broker}/v1/trading/accounts/{account_id}/orders/{order_id}")

    def positions(self, account_id: str) -> list:
        return self._call("GET", f"{self.broker}/v1/trading/accounts/{account_id}/positions") or []

    # Market data (ETFs)
    def snapshots(self, symbols: list) -> dict:
        return self._call("GET", f"{self.data}/v2/stocks/snapshots", params={"symbols": ",".join(symbols)})

    def bars(self, symbol: str, span: str) -> list:
        timeframe, back = BAR_RANGES.get(span, BAR_RANGES["1M"])
        start = (datetime.now(timezone.utc) - back).strftime("%Y-%m-%dT%H:%M:%SZ")
        body = self._call("GET", f"{self.data}/v2/stocks/{symbol}/bars", params={"timeframe": timeframe, "start": start, "limit": 1000})
        return body.get("bars") or []


def get_broker() -> Alpaca:
    return Alpaca()
