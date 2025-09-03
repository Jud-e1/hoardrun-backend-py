"""
Mock market data provider for investment quotes, trends, and financial data.
"""
import asyncio
import random
from decimal import Decimal
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Optional, Any

from ..config.logging import get_logger, log_external_service_call
from ..core.exceptions import ExternalServiceException

logger = get_logger("market_data")


class MockMarketDataProvider:
    """Mock market data provider for stock quotes and market information."""
    
    def __init__(self, base_url: str = "https://mock-market-data.com", timeout: int = 15):
        self.base_url = base_url
        self.timeout = timeout
        
        # Mock stock data
        self.stocks = {
            "AAPL": {
                "symbol": "AAPL",
                "company_name": "Apple Inc.",
                "sector": "Technology",
                "base_price": 182.50,
                "market_cap": 2800000000000,
                "pe_ratio": 28.5,
                "dividend_yield": 0.52,
                "beta": 1.25
            },
            "GOOGL": {
                "symbol": "GOOGL", 
                "company_name": "Alphabet Inc.",
                "sector": "Technology",
                "base_price": 142.80,
                "market_cap": 1800000000000,
                "pe_ratio": 25.8,
                "dividend_yield": 0.0,
                "beta": 1.15
            },
            "MSFT": {
                "symbol": "MSFT",
                "company_name": "Microsoft Corporation",
                "sector": "Technology", 
                "base_price": 378.85,
                "market_cap": 2800000000000,
                "pe_ratio": 32.1,
                "dividend_yield": 0.68,
                "beta": 0.95
            },
            "TSLA": {
                "symbol": "TSLA",
                "company_name": "Tesla Inc.",
                "sector": "Automotive",
                "base_price": 248.50,
                "market_cap": 790000000000,
                "pe_ratio": 75.2,
                "dividend_yield": 0.0,
                "beta": 2.05
            },
            "AMZN": {
                "symbol": "AMZN",
                "company_name": "Amazon.com Inc.",
                "sector": "E-commerce",
                "base_price": 145.30,
                "market_cap": 1500000000000,
                "pe_ratio": 52.4,
                "dividend_yield": 0.0,
                "beta": 1.35
            },
            "JPM": {
                "symbol": "JPM",
                "company_name": "JPMorgan Chase & Co.",
                "sector": "Financial",
                "base_price": 165.75,
                "market_cap": 485000000000,
                "pe_ratio": 12.8,
                "dividend_yield": 2.85,
                "beta": 1.18
            }
        }
    
    async def get_stock_quote(self, symbol: str) -> Dict[str, Any]:
        """Get real-time stock quote."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Simulate API delay
            await asyncio.sleep(random.uniform(0.2, 0.8))
            
            symbol = symbol.upper()
            
            if symbol not in self.stocks:
                raise ExternalServiceException("MarketData", "get_stock_quote", f"Symbol {symbol} not found")
            
            stock_info = self.stocks[symbol]
            base_price = stock_info["base_price"]
            
            # Simulate price movement (±5% from base price)
            price_variation = random.uniform(0.95, 1.05)
            current_price = Decimal(str(base_price * price_variation))
            
            # Calculate change from "previous close"
            previous_close = Decimal(str(base_price * random.uniform(0.98, 1.02)))
            change = current_price - previous_close
            change_percent = (change / previous_close * 100) if previous_close > 0 else Decimal("0")
            
            # Mock volume and other data
            volume = random.randint(1000000, 50000000)
            high_52week = Decimal(str(base_price * random.uniform(1.2, 1.8)))
            low_52week = Decimal(str(base_price * random.uniform(0.6, 0.9)))
            
            quote = {
                "symbol": symbol,
                "company_name": stock_info["company_name"],
                "price": float(current_price),
                "change": float(change),
                "change_percent": float(change_percent),
                "previous_close": float(previous_close),
                "volume": volume,
                "avg_volume": int(volume * random.uniform(0.8, 1.2)),
                "market_cap": stock_info["market_cap"],
                "pe_ratio": stock_info["pe_ratio"],
                "dividend_yield": stock_info["dividend_yield"],
                "beta": stock_info["beta"],
                "high_52week": float(high_52week),
                "low_52week": float(low_52week),
                "sector": stock_info["sector"],
                "last_updated": datetime.now(UTC).isoformat(),
                "market_status": random.choice(["open", "closed", "pre_market", "after_hours"])
            }
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="MarketData",
                operation="get_stock_quote",
                duration_ms=duration_ms,
                success=True
            )
            
            return quote
            
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="MarketData",
                operation="get_stock_quote",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            if isinstance(e, ExternalServiceException):
                raise
            raise ExternalServiceException("MarketData", "get_stock_quote", str(e))
    
    async def get_multiple_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """Get quotes for multiple stocks."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Simulate bulk API delay
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            quotes = []
            for symbol in symbols:
                try:
                    quote = await self.get_stock_quote(symbol)
                    quotes.append(quote)
                except ExternalServiceException:
                    # Skip unavailable quotes
                    continue
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="MarketData",
                operation="get_multiple_quotes",
                duration_ms=duration_ms,
                success=True
            )
            
            return quotes
            
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="MarketData",
                operation="get_multiple_quotes",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            raise ExternalServiceException("MarketData", "get_multiple_quotes", str(e))
    
    async def get_market_trends(self, period: str = "1d") -> Dict[str, Any]:
        """Get market trends and indices."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Simulate API delay
            await asyncio.sleep(random.uniform(0.8, 2.0))
            
            # Mock market indices
            indices = {
                "S&P 500": {
                    "value": 4500 + random.uniform(-100, 100),
                    "change": random.uniform(-50, 50),
                    "change_percent": random.uniform(-2, 2)
                },
                "NASDAQ": {
                    "value": 14000 + random.uniform(-300, 300),
                    "change": random.uniform(-150, 150),
                    "change_percent": random.uniform(-2.5, 2.5)
                },
                "Dow Jones": {
                    "value": 35000 + random.uniform(-500, 500),
                    "change": random.uniform(-200, 200),
                    "change_percent": random.uniform(-1.5, 1.5)
                }
            }
            
            # Mock sector performance
            sectors = [
                {"name": "Technology", "change_percent": random.uniform(-3, 3)},
                {"name": "Healthcare", "change_percent": random.uniform(-2, 2)},
                {"name": "Financial", "change_percent": random.uniform(-2.5, 2.5)},
                {"name": "Energy", "change_percent": random.uniform(-4, 4)},
                {"name": "Consumer Goods", "change_percent": random.uniform(-1.5, 1.5)}
            ]
            
            # Mock market news headlines
            news_headlines = [
                "Federal Reserve signals potential rate changes",
                "Tech stocks show strong quarterly earnings",
                "Market volatility increases amid global events",
                "Energy sector rebounds on supply concerns",
                "Consumer spending data shows mixed signals"
            ]
            
            trends = {
                "period": period,
                "indices": indices,
                "sector_performance": sectors,
                "market_sentiment": random.choice(["bullish", "bearish", "neutral"]),
                "volatility_index": round(random.uniform(15, 35), 2),
                "news_headlines": random.sample(news_headlines, 3),
                "last_updated": datetime.now(UTC).isoformat(),
                "market_status": random.choice(["open", "closed", "pre_market", "after_hours"])
            }
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="MarketData",
                operation="get_market_trends",
                duration_ms=duration_ms,
                success=True
            )
            
            return trends
            
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="MarketData",
                operation="get_market_trends",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            raise ExternalServiceException("MarketData", "get_market_trends", str(e))
    
    async def search_stocks(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for stocks by symbol or company name."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Simulate search delay
            await asyncio.sleep(random.uniform(0.3, 1.0))
            
            query_lower = query.lower()
            results = []
            
            for symbol, info in self.stocks.items():
                if (query_lower in symbol.lower() or 
                    query_lower in info["company_name"].lower()):
                    
                    # Get current quote
                    quote = await self.get_stock_quote(symbol)
                    
                    results.append({
                        "symbol": symbol,
                        "company_name": info["company_name"],
                        "sector": info["sector"],
                        "current_price": quote["price"],
                        "change_percent": quote["change_percent"],
                        "market_cap": info["market_cap"],
                        "relevance_score": random.uniform(0.7, 1.0)
                    })
            
            # Sort by relevance score
            results.sort(key=lambda x: x["relevance_score"], reverse=True)
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="MarketData",
                operation="search_stocks",
                duration_ms=duration_ms,
                success=True
            )
            
            return results[:limit]
            
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="MarketData",
                operation="search_stocks",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            raise ExternalServiceException("MarketData", "search_stocks", str(e))
    
    async def get_historical_data(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d"
    ) -> Dict[str, Any]:
        """Get historical price data for a stock."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Simulate API delay
            await asyncio.sleep(random.uniform(1.0, 2.5))
            
            symbol = symbol.upper()
            
            if symbol not in self.stocks:
                raise ExternalServiceException("MarketData", "get_historical_data", f"Symbol {symbol} not found")
            
            stock_info = self.stocks[symbol]
            base_price = stock_info["base_price"]
            
            # Generate mock historical data
            periods = {"1d": 1, "1w": 7, "1m": 30, "3m": 90, "1y": 365}
            days = periods.get(period, 30)
            
            historical_data = []
            current_price = base_price
            
            for i in range(days):
                date = datetime.now(UTC) - timedelta(days=days - i)
                
                # Simulate price movement (random walk)
                change_percent = random.uniform(-0.05, 0.05)  # ±5% daily change
                current_price = current_price * (1 + change_percent)
                
                # Ensure price doesn't go negative
                current_price = max(current_price, base_price * 0.1)
                
                # Generate OHLCV data
                open_price = current_price * random.uniform(0.98, 1.02)
                high_price = max(open_price, current_price) * random.uniform(1.0, 1.03)
                low_price = min(open_price, current_price) * random.uniform(0.97, 1.0)
                volume = random.randint(500000, 20000000)
                
                historical_data.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "open": round(open_price, 2),
                    "high": round(high_price, 2),
                    "low": round(low_price, 2),
                    "close": round(current_price, 2),
                    "volume": volume
                })
            
            result = {
                "symbol": symbol,
                "company_name": stock_info["company_name"],
                "period": period,
                "interval": interval,
                "data": historical_data,
                "data_points": len(historical_data),
                "last_updated": datetime.now(UTC).isoformat()
            }
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="MarketData",
                operation="get_historical_data",
                duration_ms=duration_ms,
                success=True
            )
            
            return result
            
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="MarketData",
                operation="get_historical_data",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            if isinstance(e, ExternalServiceException):
                raise
            raise ExternalServiceException("MarketData", "get_historical_data", str(e))
    
    async def get_market_news(self, category: str = "general", limit: int = 10) -> List[Dict[str, Any]]:
        """Get market news and analysis."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Simulate API delay
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Mock news articles
            news_templates = [
                {
                    "category": "earnings",
                    "headlines": [
                        "{company} reports {direction} quarterly earnings",
                        "{company} beats/misses earnings expectations",
                        "{company} announces strong/weak quarterly results"
                    ]
                },
                {
                    "category": "market",
                    "headlines": [
                        "Market {direction} amid {event}",
                        "Investors react to {event}",
                        "Trading volume {direction} on {event}"
                    ]
                },
                {
                    "category": "economic",
                    "headlines": [
                        "Federal Reserve {action} interest rates",
                        "Economic indicators show {trend}",
                        "Inflation data {direction} expectations"
                    ]
                }
            ]
            
            companies = list(self.stocks.keys())
            directions = ["rises", "falls", "surges", "drops"]
            events = ["policy changes", "global events", "earnings season", "market volatility"]
            actions = ["raises", "lowers", "holds", "considers"]
            trends = ["growth", "decline", "stability", "uncertainty"]
            
            news_articles = []
            for i in range(limit):
                template_cat = random.choice(news_templates)
                headline_template = random.choice(template_cat["headlines"])
                
                # Fill in template variables
                headline = headline_template.format(
                    company=random.choice(companies),
                    direction=random.choice(directions),
                    event=random.choice(events),
                    action=random.choice(actions),
                    trend=random.choice(trends)
                )
                
                article = {
                    "id": str(random.randint(100000, 999999)),
                    "headline": headline,
                    "summary": f"Market analysis shows {random.choice(['positive', 'negative', 'mixed'])} sentiment...",
                    "category": template_cat["category"],
                    "source": random.choice(["Reuters", "Bloomberg", "MarketWatch", "CNBC", "Financial Times"]),
                    "published_at": (datetime.now(UTC) - timedelta(hours=random.randint(1, 48))).isoformat(),
                    "url": f"{self.base_url}/news/{random.randint(100000, 999999)}",
                    "sentiment": random.choice(["positive", "negative", "neutral"]),
                    "impact_score": round(random.uniform(0.1, 1.0), 2)
                }
                
                news_articles.append(article)
            
            # Sort by published date (most recent first)
            news_articles.sort(key=lambda x: x["published_at"], reverse=True)
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="MarketData",
                operation="get_market_news",
                duration_ms=duration_ms,
                success=True
            )
            
            return news_articles
            
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="MarketData",
                operation="get_market_news",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            raise ExternalServiceException("MarketData", "get_market_news", str(e))
    
    async def get_economic_indicators(self) -> Dict[str, Any]:
        """Get current economic indicators."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Simulate API delay
            await asyncio.sleep(random.uniform(1.0, 2.0))
            
            indicators = {
                "federal_funds_rate": {
                    "value": round(random.uniform(4.5, 5.5), 2),
                    "change": round(random.uniform(-0.25, 0.25), 2),
                    "last_updated": datetime.now(UTC).isoformat()
                },
                "inflation_rate": {
                    "value": round(random.uniform(2.5, 4.5), 2),
                    "change": round(random.uniform(-0.5, 0.5), 2),
                    "last_updated": datetime.now(UTC).isoformat()
                },
                "unemployment_rate": {
                    "value": round(random.uniform(3.0, 6.0), 2),
                    "change": round(random.uniform(-0.3, 0.3), 2),
                    "last_updated": datetime.now(UTC).isoformat()
                },
                "gdp_growth": {
                    "value": round(random.uniform(1.5, 4.0), 2),
                    "change": round(random.uniform(-1.0, 1.0), 2),
                    "last_updated": datetime.now(UTC).isoformat()
                },
                "consumer_confidence": {
                    "value": round(random.uniform(80, 120), 1),
                    "change": round(random.uniform(-5, 5), 1),
                    "last_updated": datetime.now(UTC).isoformat()
                }
            }
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="MarketData",
                operation="get_economic_indicators",
                duration_ms=duration_ms,
                success=True
            )
            
            return indicators
            
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_external_service_call(
                logger=logger,
                service_name="MarketData",
                operation="get_economic_indicators",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            raise ExternalServiceException("MarketData", "get_economic_indicators", str(e))


# Global client instance
_market_data_client: Optional[MockMarketDataProvider] = None


def get_market_data_client() -> MockMarketDataProvider:
    """Get the global market data client instance."""
    global _market_data_client
    
    if _market_data_client is None:
        from ..config.settings import get_settings
        settings = get_settings()
        _market_data_client = MockMarketDataProvider(
            base_url=settings.market_data_url,
            timeout=settings.market_data_timeout
        )
    
    return _market_data_client
