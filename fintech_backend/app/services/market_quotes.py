"""
Live prices for the crypto and ETF pages.

Crypto comes from Binance's public market data API. ETFs come from Alpaca's licensed
market data when Alpaca is set up, otherwise from Yahoo Finance's public chart API.
Orders always use a price fetched here on the server, never one sent by the browser.
"""

import asyncio
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional

import httpx

from . import alpaca

CRYPTO = [
    ("BTC", "Bitcoin"), ("ETH", "Ethereum"), ("SOL", "Solana"), ("BNB", "BNB"), ("XRP", "XRP"), ("ADA", "Cardano"),
    ("DOGE", "Dogecoin"), ("AVAX", "Avalanche"), ("LINK", "Chainlink"), ("DOT", "Polkadot"), ("TRX", "TRON"), ("LTC", "Litecoin"),
]
ETFS = [
    ("SPY", "SPDR S&P 500", "The 500 biggest US companies"),
    ("VOO", "Vanguard S&P 500", "The 500 biggest US companies, low fee"),
    ("QQQ", "Invesco QQQ", "The Nasdaq 100, mostly tech"),
    ("VTI", "Vanguard Total Stock Market", "Almost every US listed company"),
    ("IWM", "iShares Russell 2000", "2,000 smaller US companies"),
    ("DIA", "SPDR Dow Jones", "The 30 Dow Jones companies"),
    ("VXUS", "Vanguard Total International", "Companies outside the US"),
    ("EEM", "iShares Emerging Markets", "China, India, Brazil and more"),
    ("XLK", "Technology Select Sector", "US technology companies"),
    ("ARKK", "ARK Innovation", "Disruptive tech, actively managed"),
    ("GLD", "SPDR Gold Shares", "Tracks the price of gold"),
    ("TLT", "iShares 20+ Year Treasury", "Long-term US government bonds"),
]
CRYPTO_NAMES = dict(CRYPTO)
ETF_INFO = {symbol: (name, about) for symbol, name, about in ETFS}

BINANCE = "https://data-api.binance.vision/api/v3"
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart"
HEADERS = {"User-Agent": "Mozilla/5.0 (Hoardrun market data)"}
RANGES = {"1D": ("1d", "5m"), "1W": ("5d", "30m"), "1M": ("1mo", "1d"), "1Y": ("1y", "1wk")}

_etf_cache: Dict[str, tuple] = {}
ETF_TTL = 20


class QuoteUnavailable(Exception):
    pass


async def crypto_prices(symbols: List[str]) -> Dict[str, Decimal]:
    pairs = ",".join(f'"{symbol}USDT"' for symbol in symbols)
    try:
        async with httpx.AsyncClient(timeout=8, headers=HEADERS) as client:
            response = await client.get(f"{BINANCE}/ticker/price", params={"symbols": f"[{pairs}]"})
            response.raise_for_status()
    except httpx.HTTPError as error:
        raise QuoteUnavailable("Crypto prices are unavailable right now") from error
    return {row["symbol"].removesuffix("USDT"): Decimal(row["price"]) for row in response.json()}


async def _etf_chart(client: httpx.AsyncClient, symbol: str, span: str, interval: str) -> dict:
    response = await client.get(f"{YAHOO}/{symbol}", params={"range": span, "interval": interval})
    response.raise_for_status()
    result = response.json()["chart"]["result"][0]
    return result


def _quote_from_chart(symbol: str, result: dict) -> dict:
    meta = result["meta"]
    closes = [value for value in (result.get("indicators", {}).get("quote", [{}])[0].get("close") or []) if value is not None]
    price = Decimal(str(meta["regularMarketPrice"]))
    previous = Decimal(str(meta.get("chartPreviousClose") or meta.get("previousClose") or price))
    period = (meta.get("currentTradingPeriod") or {}).get("regular") or {}
    now = time.time()
    step = max(1, len(closes) // 40)
    name, about = ETF_INFO[symbol]
    return {
        "symbol": symbol,
        "name": name,
        "about": about,
        "price": float(price),
        "previous_close": float(previous),
        "change_percent": float((price - previous) / previous * 100) if previous else 0.0,
        "market_open": bool(period) and period.get("start", 0) <= now < period.get("end", 0),
        "updated_at": datetime.fromtimestamp(meta.get("regularMarketTime", now), timezone.utc).isoformat(),
        "spark": [round(value, 4) for value in closes[::step]],
    }


def _quote_from_snapshot(symbol: str, snap: dict) -> dict:
    trade, today, before = snap.get("latestTrade") or {}, snap.get("dailyBar") or {}, snap.get("prevDailyBar") or {}
    price = Decimal(str(trade.get("p") or today.get("c")))
    previous = Decimal(str(before.get("c") or price))
    stamp = trade.get("t") or today.get("t")
    traded = datetime.fromisoformat(stamp.replace("Z", "+00:00")) if stamp else datetime.now(timezone.utc)
    name, about = ETF_INFO[symbol]
    return {
        "symbol": symbol, "name": name, "about": about, "price": float(price), "previous_close": float(previous),
        "change_percent": float((price - previous) / previous * 100) if previous else 0.0,
        # A trade in the last ten minutes means the market is open
        "market_open": (datetime.now(timezone.utc) - traded).total_seconds() < 600,
        "updated_at": traded.isoformat(),
        "spark": [round(float(value), 4) for value in (before.get("c"), today.get("o"), today.get("h"), today.get("l"), price) if value is not None],
    }


async def _alpaca_quotes(symbols: List[str]) -> Dict[str, dict]:
    try:
        snaps = await asyncio.to_thread(alpaca.get_broker().snapshots, symbols)
    except alpaca.AlpacaError as error:
        raise QuoteUnavailable("ETF prices are unavailable right now") from error
    return {symbol: _quote_from_snapshot(symbol, snap) for symbol, snap in (snaps or {}).items() if symbol in ETF_INFO and snap}


async def etf_quotes(force: bool = False) -> List[dict]:
    now = time.time()
    if alpaca.configured():
        fresh = {symbol: quote for symbol, (stamp, quote) in _etf_cache.items() if now - stamp < ETF_TTL and not force}
        missing = [symbol for symbol, *_ in ETFS if symbol not in fresh]
        if missing:
            for symbol, quote in (await _alpaca_quotes(missing)).items():
                _etf_cache[symbol] = (now, quote)
                fresh[symbol] = quote
        if not fresh:
            raise QuoteUnavailable("ETF prices are unavailable right now")
        return [fresh[symbol] for symbol, *_ in ETFS if symbol in fresh]
    fresh = {symbol: quote for symbol, (stamp, quote) in _etf_cache.items() if now - stamp < ETF_TTL}
    missing = [symbol for symbol, *_ in ETFS if force or symbol not in fresh]
    if missing:
        async with httpx.AsyncClient(timeout=8, headers=HEADERS) as client:
            results = await asyncio.gather(*(_etf_chart(client, symbol, "1d", "5m") for symbol in missing), return_exceptions=True)
        for symbol, result in zip(missing, results):
            if isinstance(result, Exception):
                continue
            quote = _quote_from_chart(symbol, result)
            _etf_cache[symbol] = (now, quote)
            fresh[symbol] = quote
    if not fresh:
        raise QuoteUnavailable("ETF prices are unavailable right now")
    return [fresh[symbol] for symbol, *_ in ETFS if symbol in fresh]


async def etf_price(symbol: str) -> Decimal:
    if alpaca.configured():
        quote = (await _alpaca_quotes([symbol])).get(symbol)
        if quote is None:
            raise QuoteUnavailable(f"{symbol} isn't available right now")
        _etf_cache[symbol] = (time.time(), quote)
        return Decimal(str(quote["price"]))
    async with httpx.AsyncClient(timeout=8, headers=HEADERS) as client:
        try:
            result = await _etf_chart(client, symbol, "1d", "5m")
        except (httpx.HTTPError, KeyError, IndexError) as error:
            raise QuoteUnavailable(f"{symbol} isn't available right now") from error
    quote = _quote_from_chart(symbol, result)
    _etf_cache[symbol] = (time.time(), quote)
    return Decimal(str(quote["price"]))


async def etf_history(symbol: str, span: str) -> List[List[float]]:
    if alpaca.configured():
        try:
            bars = await asyncio.to_thread(alpaca.get_broker().bars, symbol, span)
        except alpaca.AlpacaError as error:
            raise QuoteUnavailable(f"{symbol} history isn't available right now") from error
        return [[datetime.fromisoformat(bar["t"].replace("Z", "+00:00")).timestamp() * 1000, round(float(bar["c"]), 4)] for bar in bars]
    yahoo_range, interval = RANGES.get(span, RANGES["1M"])
    async with httpx.AsyncClient(timeout=8, headers=HEADERS) as client:
        try:
            result = await _etf_chart(client, symbol, yahoo_range, interval)
        except (httpx.HTTPError, KeyError, IndexError) as error:
            raise QuoteUnavailable(f"{symbol} history isn't available right now") from error
    closes = result.get("indicators", {}).get("quote", [{}])[0].get("close") or []
    return [[stamp * 1000, round(close, 4)] for stamp, close in zip(result.get("timestamp") or [], closes) if close is not None]


async def price_for(asset_type: str, symbol: str) -> Decimal:
    if asset_type == "crypto":
        prices = await crypto_prices([symbol])
        if symbol not in prices:
            raise QuoteUnavailable(f"{symbol} isn't available right now")
        return prices[symbol]
    return await etf_price(symbol)


async def prices_for(holdings: List[tuple]) -> Dict[tuple, Optional[Decimal]]:
    """Current prices for (asset_type, symbol) pairs; a missing price comes back as None."""
    found: Dict[tuple, Optional[Decimal]] = {}
    crypto = [symbol for kind, symbol in holdings if kind == "crypto"]
    if crypto:
        try:
            for symbol, price in (await crypto_prices(crypto)).items():
                found[("crypto", symbol)] = price
        except QuoteUnavailable:
            pass
    if any(kind == "etf" for kind, _ in holdings):
        try:
            for quote in await etf_quotes():
                found[("etf", quote["symbol"])] = Decimal(str(quote["price"]))
        except QuoteUnavailable:
            pass
    return {key: found.get(key) for key in holdings}
