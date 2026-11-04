from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum
from decimal import Decimal

class MarketDataType(str, Enum):
    STOCK = "stock"
    FOREX = "forex"
    CRYPTO = "crypto"
    COMMODITY = "commodity"
    INDEX = "index"

class MarketStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    PRE_MARKET = "pre_market"
    AFTER_HOURS = "after_hours"
    HOLIDAY = "holiday"

class TimeInterval(str, Enum):
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    FOUR_HOURS = "4h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"
    ONE_MONTH = "1M"

class TrendDirection(str, Enum):
    UP = "up"
    DOWN = "down"
    SIDEWAYS = "sideways"

# Request Models
class MarketDataRequest(BaseModel):
    symbols: List[str] = Field(..., min_items=1, max_items=50)
    data_type: MarketDataType = MarketDataType.STOCK
    
    @validator('symbols')
    def validate_symbols(cls, v):
        # Remove duplicates and convert to uppercase
        symbols = list(set([symbol.upper().strip() for symbol in v if symbol.strip()]))
        if not symbols:
            raise ValueError('At least one valid symbol must be provided')
        return symbols

class HistoricalDataRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    data_type: MarketDataType = MarketDataType.STOCK
    interval: TimeInterval = TimeInterval.ONE_DAY
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = Field(100, ge=1, le=1000)
    
    @validator('symbol')
    def validate_symbol(cls, v):
        return v.upper().strip()
    
    @validator('end_date')
    def validate_dates(cls, v, values):
        if 'start_date' in values and values['start_date'] and v:
            if v <= values['start_date']:
                raise ValueError('End date must be after start date')
        return v

class WatchlistRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    symbols: List[str] = Field(..., min_items=1, max_items=100)
    data_type: MarketDataType = MarketDataType.STOCK
    
    @validator('symbols')
    def validate_symbols(cls, v):
        symbols = list(set([symbol.upper().strip() for symbol in v if symbol.strip()]))
        if not symbols:
            raise ValueError('At least one valid symbol must be provided')
        return symbols

class MarketAlertRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    data_type: MarketDataType = MarketDataType.STOCK
    alert_type: str = Field(..., pattern=r'^(price_above|price_below|volume_above|change_above|change_below)$')
    threshold_value: Decimal = Field(..., gt=0)
    is_active: bool = True
    
    @validator('symbol')
    def validate_symbol(cls, v):
        return v.upper().strip()

# Response Models
class MarketQuote(BaseModel):
    symbol: str
    name: str
    data_type: MarketDataType
    current_price: Decimal
    previous_close: Decimal
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    volume: int
    market_cap: Optional[Decimal] = None
    change_amount: Decimal
    change_percent: Decimal
    currency: str = "USD"
    last_updated: datetime
    market_status: MarketStatus
    
    @property
    def is_gaining(self) -> bool:
        return self.change_amount > 0
    
    @property
    def is_losing(self) -> bool:
        return self.change_amount < 0

class HistoricalDataPoint(BaseModel):
    timestamp: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: int
    adjusted_close: Optional[Decimal] = None

class HistoricalData(BaseModel):
    symbol: str
    data_type: MarketDataType
    interval: TimeInterval
    data_points: List[HistoricalDataPoint]
    total_points: int
    start_date: datetime
    end_date: datetime

class MarketSummary(BaseModel):
    market_status: MarketStatus
    total_symbols_tracked: int
    active_alerts: int
    watchlists_count: int
    top_gainers: List[MarketQuote]
    top_losers: List[MarketQuote]
    most_active: List[MarketQuote]
    market_indices: Dict[str, MarketQuote]
    last_updated: datetime

class WatchlistProfile(BaseModel):
    id: str
    name: str
    symbols: List[str]
    data_type: MarketDataType
    quotes: List[MarketQuote]
    total_value: Decimal
    total_change: Decimal
    total_change_percent: Decimal
    created_at: datetime
    updated_at: datetime

class MarketAlert(BaseModel):
    id: str
    symbol: str
    data_type: MarketDataType
    alert_type: str
    threshold_value: Decimal
    current_value: Decimal
    is_triggered: bool
    is_active: bool
    created_at: datetime
    triggered_at: Optional[datetime] = None
    last_checked: datetime

class MarketAnalytics(BaseModel):
    symbol: str
    data_type: MarketDataType
    trend_direction: TrendDirection
    support_level: Optional[Decimal] = None
    resistance_level: Optional[Decimal] = None
    rsi: Optional[float] = None  # Relative Strength Index
    moving_average_20: Optional[Decimal] = None
    moving_average_50: Optional[Decimal] = None
    moving_average_200: Optional[Decimal] = None
    volatility: float
    beta: Optional[float] = None
    recommendation: str  # buy, sell, hold
    confidence_score: float = Field(..., ge=0, le=1)
    analysis_date: datetime

class CurrencyExchangeRate(BaseModel):
    from_currency: str
    to_currency: str
    exchange_rate: Decimal
    inverse_rate: Decimal
    change_24h: Decimal
    change_24h_percent: Decimal
    last_updated: datetime
    
    @validator('from_currency', 'to_currency')
    def validate_currency_codes(cls, v):
        return v.upper().strip()

class MarketNews(BaseModel):
    id: str
    headline: str
    summary: str
    source: str
    url: str
    symbols_mentioned: List[str]
    sentiment: str  # positive, negative, neutral
    published_at: datetime
    relevance_score: float = Field(..., ge=0, le=1)

# Database Models
class WatchlistDB(BaseModel):
    id: str
    user_id: str
    name: str
    symbols: List[str]
    data_type: MarketDataType
    created_at: datetime
    updated_at: datetime

class MarketAlertDB(BaseModel):
    id: str
    user_id: str
    symbol: str
    data_type: MarketDataType
    alert_type: str
    threshold_value: Decimal
    is_triggered: bool
    is_active: bool
    created_at: datetime
    triggered_at: Optional[datetime] = None
    last_checked: datetime
    updated_at: datetime

class MarketDataCacheDB(BaseModel):
    symbol: str
    data_type: MarketDataType
    quote_data: Dict[str, Any]
    cached_at: datetime
    expires_at: datetime
