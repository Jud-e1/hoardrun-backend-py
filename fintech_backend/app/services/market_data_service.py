from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import uuid
import random
from decimal import Decimal
from ..models.market_data import (
    MarketDataRequest, HistoricalDataRequest, WatchlistRequest, MarketAlertRequest,
    MarketQuote, HistoricalData, HistoricalDataPoint, MarketSummary, WatchlistProfile,
    MarketAlert, MarketAnalytics, CurrencyExchangeRate, MarketNews,
    WatchlistDB, MarketAlertDB, MarketDataCacheDB,
    MarketDataType, MarketStatus, TimeInterval, TrendDirection
)
from ..core.exceptions import NotFoundError, ValidationError, BusinessLogicError

class MarketDataService:
    def __init__(self):
        # Mock data storage
        self.watchlists: Dict[str, WatchlistDB] = {}
        self.alerts: Dict[str, MarketAlertDB] = {}
        self.cache: Dict[str, MarketDataCacheDB] = {}
        self._initialize_mock_data()
    
    def _initialize_mock_data(self):
        """Initialize with sample market data"""
        # Sample watchlist
        user_id = "user_123"
        watchlist_id = str(uuid.uuid4())
        self.watchlists[watchlist_id] = WatchlistDB(
            id=watchlist_id,
            user_id=user_id,
            name="Tech Stocks",
            symbols=["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"],
            data_type=MarketDataType.STOCK,
            created_at=datetime.utcnow() - timedelta(days=7),
            updated_at=datetime.utcnow()
        )
        
        # Sample alerts
        alert_data = [
            {
                "symbol": "AAPL",
                "alert_type": "price_above",
                "threshold_value": Decimal("200.00"),
                "is_triggered": False,
                "is_active": True
            },
            {
                "symbol": "TSLA",
                "alert_type": "price_below",
                "threshold_value": Decimal("150.00"),
                "is_triggered": True,
                "is_active": True,
                "triggered_at": datetime.utcnow() - timedelta(hours=2)
            }
        ]
        
        for alert_info in alert_data:
            alert_id = str(uuid.uuid4())
            self.alerts[alert_id] = MarketAlertDB(
                id=alert_id,
                user_id=user_id,
                data_type=MarketDataType.STOCK,
                created_at=datetime.utcnow() - timedelta(days=3),
                last_checked=datetime.utcnow() - timedelta(minutes=5),
                updated_at=datetime.utcnow(),
                **alert_info
            )
    
    def _generate_mock_quote(self, symbol: str, data_type: MarketDataType = MarketDataType.STOCK) -> MarketQuote:
        """Generate realistic mock market quote data"""
        # Base prices for different symbols
        base_prices = {
            "AAPL": 175.50, "GOOGL": 2800.00, "MSFT": 380.25, "TSLA": 245.80, "AMZN": 3200.00,
            "NVDA": 450.75, "META": 320.40, "NFLX": 425.60, "AMD": 105.30, "INTC": 45.20,
            "EURUSD": 1.0850, "GBPUSD": 1.2650, "USDJPY": 149.50, "USDCAD": 1.3580,
            "BTCUSD": 42500.00, "ETHUSD": 2650.00, "ADAUSD": 0.45, "SOLUSD": 95.50,
            "GOLD": 2050.00, "SILVER": 24.50, "OIL": 78.25, "SPY": 450.75, "QQQ": 375.20
        }
        
        base_price = base_prices.get(symbol, 100.00)
        
        # Generate realistic price movements
        change_percent = random.uniform(-5.0, 5.0)
        current_price = Decimal(str(round(base_price * (1 + change_percent / 100), 2)))
        previous_close = Decimal(str(base_price))
        change_amount = current_price - previous_close
        
        # Generate other price data
        high_price = current_price * Decimal(str(random.uniform(1.0, 1.05)))
        low_price = current_price * Decimal(str(random.uniform(0.95, 1.0)))
        open_price = previous_close * Decimal(str(random.uniform(0.98, 1.02)))
        volume = random.randint(1000000, 50000000)
        
        # Market cap calculation (for stocks)
        market_cap = None
        if data_type == MarketDataType.STOCK:
            shares_outstanding = random.randint(1000000000, 10000000000)
            market_cap = current_price * Decimal(str(shares_outstanding))
        
        # Determine market status
        current_hour = datetime.utcnow().hour
        if 9 <= current_hour <= 16:  # Simplified market hours
            market_status = MarketStatus.OPEN
        elif 4 <= current_hour < 9:
            market_status = MarketStatus.PRE_MARKET
        elif 16 < current_hour <= 20:
            market_status = MarketStatus.AFTER_HOURS
        else:
            market_status = MarketStatus.CLOSED
        
        # Company names mapping
        company_names = {
            "AAPL": "Apple Inc.", "GOOGL": "Alphabet Inc.", "MSFT": "Microsoft Corporation",
            "TSLA": "Tesla Inc.", "AMZN": "Amazon.com Inc.", "NVDA": "NVIDIA Corporation",
            "META": "Meta Platforms Inc.", "NFLX": "Netflix Inc.", "AMD": "Advanced Micro Devices",
            "INTC": "Intel Corporation", "EURUSD": "EUR/USD", "GBPUSD": "GBP/USD",
            "USDJPY": "USD/JPY", "USDCAD": "USD/CAD", "BTCUSD": "Bitcoin",
            "ETHUSD": "Ethereum", "ADAUSD": "Cardano", "SOLUSD": "Solana",
            "GOLD": "Gold Futures", "SILVER": "Silver Futures", "OIL": "Crude Oil",
            "SPY": "SPDR S&P 500 ETF", "QQQ": "Invesco QQQ Trust"
        }
        
        return MarketQuote(
            symbol=symbol,
            name=company_names.get(symbol, f"{symbol} Corp"),
            data_type=data_type,
            current_price=current_price,
            previous_close=previous_close,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            volume=volume,
            market_cap=market_cap,
            change_amount=change_amount,
            change_percent=round(float(change_percent), 2),
            currency="USD",
            last_updated=datetime.utcnow(),
            market_status=market_status
        )
    
    async def get_market_quotes(self, request: MarketDataRequest) -> List[MarketQuote]:
        """Get real-time market quotes for specified symbols"""
        quotes = []
        for symbol in request.symbols:
            # Check cache first
            cache_key = f"{symbol}_{request.data_type.value}"
            cached_data = self.cache.get(cache_key)
            
            if cached_data and cached_data.expires_at > datetime.utcnow():
                # Use cached data
                quote_data = cached_data.quote_data
                quotes.append(MarketQuote(**quote_data))
            else:
                # Generate new quote
                quote = self._generate_mock_quote(symbol, request.data_type)
                quotes.append(quote)
                
                # Cache the quote
                self.cache[cache_key] = MarketDataCacheDB(
                    symbol=symbol,
                    data_type=request.data_type,
                    quote_data=quote.dict(),
                    cached_at=datetime.utcnow(),
                    expires_at=datetime.utcnow() + timedelta(minutes=1)  # 1-minute cache
                )
        
        return quotes
    
    async def get_historical_data(self, request: HistoricalDataRequest) -> HistoricalData:
        """Get historical market data for a symbol"""
        # Generate mock historical data
        end_date = request.end_date or datetime.utcnow()
        start_date = request.start_date or (end_date - timedelta(days=30))
        
        # Calculate number of data points based on interval
        interval_minutes = {
            TimeInterval.ONE_MINUTE: 1,
            TimeInterval.FIVE_MINUTES: 5,
            TimeInterval.FIFTEEN_MINUTES: 15,
            TimeInterval.THIRTY_MINUTES: 30,
            TimeInterval.ONE_HOUR: 60,
            TimeInterval.FOUR_HOURS: 240,
            TimeInterval.ONE_DAY: 1440,
            TimeInterval.ONE_WEEK: 10080,
            TimeInterval.ONE_MONTH: 43200
        }
        
        interval_mins = interval_minutes[request.interval]
        total_minutes = int((end_date - start_date).total_seconds() / 60)
        num_points = min(total_minutes // interval_mins, request.limit)
        
        # Generate base price for the symbol
        current_quote = self._generate_mock_quote(request.symbol, request.data_type)
        base_price = float(current_quote.current_price)
        
        data_points = []
        current_time = start_date
        current_price = base_price * 0.95  # Start slightly lower
        
        for i in range(num_points):
            # Generate realistic price movement
            price_change = random.uniform(-0.03, 0.03)  # ±3% change
            current_price *= (1 + price_change)
            
            # Generate OHLC data
            open_price = Decimal(str(round(current_price, 2)))
            high_price = open_price * Decimal(str(random.uniform(1.0, 1.02)))
            low_price = open_price * Decimal(str(random.uniform(0.98, 1.0)))
            close_price = open_price * Decimal(str(random.uniform(0.99, 1.01)))
            volume = random.randint(100000, 10000000)
            
            data_points.append(HistoricalDataPoint(
                timestamp=current_time,
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
                close_price=close_price,
                volume=volume,
                adjusted_close=close_price
            ))
            
            current_time += timedelta(minutes=interval_mins)
            current_price = float(close_price)
        
        return HistoricalData(
            symbol=request.symbol,
            data_type=request.data_type,
            interval=request.interval,
            data_points=data_points,
            total_points=len(data_points),
            start_date=start_date,
            end_date=end_date
        )
    
    async def get_market_summary(self) -> MarketSummary:
        """Get market summary with top movers and indices"""
        # Generate quotes for popular symbols
        symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN", "NVDA", "META", "NFLX"]
        quotes = []
        for symbol in symbols:
            quote = self._generate_mock_quote(symbol, MarketDataType.STOCK)
            quotes.append(quote)
        
        # Sort for top gainers and losers
        sorted_by_change = sorted(quotes, key=lambda x: x.change_percent, reverse=True)
        top_gainers = sorted_by_change[:3]
        top_losers = sorted_by_change[-3:]
        
        # Sort by volume for most active
        sorted_by_volume = sorted(quotes, key=lambda x: x.volume, reverse=True)
        most_active = sorted_by_volume[:3]
        
        # Market indices
        indices_symbols = ["SPY", "QQQ", "DIA"]
        market_indices = {}
        for symbol in indices_symbols:
            quote = self._generate_mock_quote(symbol, MarketDataType.INDEX)
            market_indices[symbol] = quote
        
        return MarketSummary(
            market_status=MarketStatus.OPEN,
            total_symbols_tracked=len(self.cache),
            active_alerts=len([a for a in self.alerts.values() if a.is_active]),
            watchlists_count=len(self.watchlists),
            top_gainers=top_gainers,
            top_losers=top_losers,
            most_active=most_active,
            market_indices=market_indices,
            last_updated=datetime.utcnow()
        )
    
    async def create_watchlist(self, user_id: str, request: WatchlistRequest) -> WatchlistProfile:
        """Create a new watchlist"""
        watchlist_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        watchlist = WatchlistDB(
            id=watchlist_id,
            user_id=user_id,
            name=request.name,
            symbols=request.symbols,
            data_type=request.data_type,
            created_at=now,
            updated_at=now
        )
        
        self.watchlists[watchlist_id] = watchlist
        
        # Get quotes for the symbols
        quotes = []
        total_value = Decimal("0")
        total_change = Decimal("0")
        
        for symbol in request.symbols:
            quote = self._generate_mock_quote(symbol, request.data_type)
            quotes.append(quote)
            total_value += quote.current_price
            total_change += quote.change_amount
        
        total_change_percent = float(total_change / total_value * 100) if total_value > 0 else 0
        
        return WatchlistProfile(
            id=watchlist.id,
            name=watchlist.name,
            symbols=watchlist.symbols,
            data_type=watchlist.data_type,
            quotes=quotes,
            total_value=total_value,
            total_change=total_change,
            total_change_percent=round(total_change_percent, 2),
            created_at=watchlist.created_at,
            updated_at=watchlist.updated_at
        )
    
    async def get_user_watchlists(self, user_id: str) -> List[WatchlistProfile]:
        """Get all watchlists for a user"""
        user_watchlists = [w for w in self.watchlists.values() if w.user_id == user_id]
        profiles = []
        
        for watchlist in user_watchlists:
            quotes = []
            total_value = Decimal("0")
            total_change = Decimal("0")
            
            for symbol in watchlist.symbols:
                quote = self._generate_mock_quote(symbol, watchlist.data_type)
                quotes.append(quote)
                total_value += quote.current_price
                total_change += quote.change_amount
            
            total_change_percent = float(total_change / total_value * 100) if total_value > 0 else 0
            
            profiles.append(WatchlistProfile(
                id=watchlist.id,
                name=watchlist.name,
                symbols=watchlist.symbols,
                data_type=watchlist.data_type,
                quotes=quotes,
                total_value=total_value,
                total_change=total_change,
                total_change_percent=round(total_change_percent, 2),
                created_at=watchlist.created_at,
                updated_at=watchlist.updated_at
            ))
        
        return profiles
    
    async def create_market_alert(self, user_id: str, request: MarketAlertRequest) -> MarketAlert:
        """Create a new market alert"""
        alert_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        alert = MarketAlertDB(
            id=alert_id,
            user_id=user_id,
            symbol=request.symbol,
            data_type=request.data_type,
            alert_type=request.alert_type,
            threshold_value=request.threshold_value,
            is_triggered=False,
            is_active=request.is_active,
            created_at=now,
            last_checked=now,
            updated_at=now
        )
        
        self.alerts[alert_id] = alert
        
        # Get current value for the symbol
        current_quote = self._generate_mock_quote(request.symbol, request.data_type)
        current_value = current_quote.current_price
        
        return MarketAlert(
            id=alert.id,
            symbol=alert.symbol,
            data_type=alert.data_type,
            alert_type=alert.alert_type,
            threshold_value=alert.threshold_value,
            current_value=current_value,
            is_triggered=alert.is_triggered,
            is_active=alert.is_active,
            created_at=alert.created_at,
            triggered_at=alert.triggered_at,
            last_checked=alert.last_checked
        )
    
    async def get_user_alerts(self, user_id: str) -> List[MarketAlert]:
        """Get all market alerts for a user"""
        user_alerts = [a for a in self.alerts.values() if a.user_id == user_id]
        alert_profiles = []
        
        for alert in user_alerts:
            current_quote = self._generate_mock_quote(alert.symbol, alert.data_type)
            current_value = current_quote.current_price
            
            alert_profiles.append(MarketAlert(
                id=alert.id,
                symbol=alert.symbol,
                data_type=alert.data_type,
                alert_type=alert.alert_type,
                threshold_value=alert.threshold_value,
                current_value=current_value,
                is_triggered=alert.is_triggered,
                is_active=alert.is_active,
                created_at=alert.created_at,
                triggered_at=alert.triggered_at,
                last_checked=alert.last_checked
            ))
        
        return alert_profiles
    
    async def get_currency_rates(self, base_currency: str = "USD") -> List[CurrencyExchangeRate]:
        """Get currency exchange rates"""
        currency_pairs = [
            ("USD", "EUR"), ("USD", "GBP"), ("USD", "JPY"), ("USD", "CAD"),
            ("USD", "AUD"), ("USD", "CHF"), ("USD", "CNY"), ("EUR", "GBP")
        ]
        
        rates = []
        for from_curr, to_curr in currency_pairs:
            if base_currency.upper() not in [from_curr, to_curr]:
                continue
                
            # Generate mock exchange rate
            base_rates = {
                ("USD", "EUR"): 0.85, ("USD", "GBP"): 0.79, ("USD", "JPY"): 149.5,
                ("USD", "CAD"): 1.36, ("USD", "AUD"): 1.52, ("USD", "CHF"): 0.88,
                ("USD", "CNY"): 7.25, ("EUR", "GBP"): 0.93
            }
            
            base_rate = base_rates.get((from_curr, to_curr), 1.0)
            rate_change = random.uniform(-0.02, 0.02)
            current_rate = Decimal(str(round(base_rate * (1 + rate_change), 4)))
            
            change_24h = current_rate * Decimal(str(rate_change))
            change_24h_percent = round(rate_change * 100, 2)
            
            rates.append(CurrencyExchangeRate(
                from_currency=from_curr,
                to_currency=to_curr,
                exchange_rate=current_rate,
                inverse_rate=Decimal("1") / current_rate,
                change_24h=change_24h,
                change_24h_percent=change_24h_percent,
                last_updated=datetime.utcnow()
            ))
        
        return rates
    
    async def get_market_analytics(self, symbol: str, data_type: MarketDataType) -> MarketAnalytics:
        """Get market analytics and technical indicators for a symbol"""
        current_quote = self._generate_mock_quote(symbol, data_type)
        current_price = float(current_quote.current_price)
        
        # Generate mock technical indicators
        rsi = random.uniform(20, 80)
        volatility = random.uniform(0.15, 0.45)
        beta = random.uniform(0.5, 2.0) if data_type == MarketDataType.STOCK else None
        
        # Moving averages
        ma_20 = Decimal(str(round(current_price * random.uniform(0.95, 1.05), 2)))
        ma_50 = Decimal(str(round(current_price * random.uniform(0.90, 1.10), 2)))
        ma_200 = Decimal(str(round(current_price * random.uniform(0.85, 1.15), 2)))
        
        # Support and resistance levels
        support_level = Decimal(str(round(current_price * 0.95, 2)))
        resistance_level = Decimal(str(round(current_price * 1.05, 2)))
        
        # Determine trend direction
        if current_price > float(ma_20) > float(ma_50):
            trend = TrendDirection.UP
        elif current_price < float(ma_20) < float(ma_50):
            trend = TrendDirection.DOWN
        else:
            trend = TrendDirection.SIDEWAYS
        
        # Generate recommendation
        if rsi < 30 and trend == TrendDirection.UP:
            recommendation = "buy"
            confidence = 0.8
        elif rsi > 70 and trend == TrendDirection.DOWN:
            recommendation = "sell"
            confidence = 0.75
        else:
            recommendation = "hold"
            confidence = 0.6
        
        return MarketAnalytics(
            symbol=symbol,
            data_type=data_type,
            trend_direction=trend,
            support_level=support_level,
            resistance_level=resistance_level,
            rsi=round(rsi, 2),
            moving_average_20=ma_20,
            moving_average_50=ma_50,
            moving_average_200=ma_200,
            volatility=round(volatility, 3),
            beta=round(beta, 2) if beta else None,
            recommendation=recommendation,
            confidence_score=confidence,
            analysis_date=datetime.utcnow()
        )
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get market data service health status"""
        total_watchlists = len(self.watchlists)
        total_alerts = len(self.alerts)
        active_alerts = len([a for a in self.alerts.values() if a.is_active])
        cache_size = len(self.cache)
        
        # Calculate cache hit rate (mock)
        cache_hit_rate = random.uniform(85, 95)
        
        return {
            "service": "market_data",
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {
                "total_watchlists": total_watchlists,
                "total_alerts": total_alerts,
                "active_alerts": active_alerts,
                "cache_size": cache_size,
                "cache_hit_rate": round(cache_hit_rate, 2)
            },
            "data_sources": {
                "stocks": "active",
                "forex": "active",
                "crypto": "active",
                "commodities": "active"
            },
            "version": "1.0.0"
        }
