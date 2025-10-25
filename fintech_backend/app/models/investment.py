"""
Investment management models for the fintech backend.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from enum import Enum

from ..models.base import BaseResponse, TimestampMixin


class AssetType(str, Enum):
    """Types of investment assets."""
    STOCK = "stock"
    ETF = "etf"
    MUTUAL_FUND = "mutual_fund"
    BOND = "bond"
    CRYPTO = "crypto"
    COMMODITY = "commodity"
    REIT = "reit"
    INDEX_FUND = "index_fund"


class OrderType(str, Enum):
    """Types of investment orders."""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class OrderSide(str, Enum):
    """Order sides for trading."""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    """Order execution statuses."""
    PENDING = "pending"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class PortfolioType(str, Enum):
    """Types of investment portfolios."""
    INDIVIDUAL = "individual"
    JOINT = "joint"
    IRA = "ira"
    ROTH_IRA = "roth_ira"
    TRADITIONAL_401K = "traditional_401k"
    ROTH_401K = "roth_401k"
    CUSTODIAL = "custodial"


class RiskTolerance(str, Enum):
    """Investment risk tolerance levels."""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    VERY_AGGRESSIVE = "very_aggressive"


class InvestmentGoal(str, Enum):
    """Investment goals."""
    RETIREMENT = "retirement"
    WEALTH_BUILDING = "wealth_building"
    INCOME_GENERATION = "income_generation"
    CAPITAL_PRESERVATION = "capital_preservation"
    TAX_MINIMIZATION = "tax_minimization"
    EDUCATION = "education"
    HOME_PURCHASE = "home_purchase"


class MarketData(BaseModel):
    """Market data for an asset."""
    symbol: str = Field(..., description="Asset symbol")
    name: str = Field(..., description="Asset name")
    asset_type: AssetType = Field(..., description="Type of asset")
    current_price: Decimal = Field(..., description="Current market price")
    previous_close: Decimal = Field(..., description="Previous day's closing price")
    day_change: Decimal = Field(..., description="Price change from previous close")
    day_change_percent: Decimal = Field(..., description="Percentage change from previous close")
    volume: int = Field(..., description="Trading volume")
    market_cap: Optional[Decimal] = Field(None, description="Market capitalization")
    pe_ratio: Optional[Decimal] = Field(None, description="Price-to-earnings ratio")
    dividend_yield: Optional[Decimal] = Field(None, description="Dividend yield percentage")
    week_52_high: Decimal = Field(..., description="52-week high price")
    week_52_low: Decimal = Field(..., description="52-week low price")
    beta: Optional[Decimal] = Field(None, description="Beta coefficient")
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class Holding(BaseModel, TimestampMixin):
    """Investment holding in a portfolio."""
    holding_id: str = Field(..., description="Unique holding identifier")
    portfolio_id: str = Field(..., description="Portfolio identifier")
    symbol: str = Field(..., description="Asset symbol")
    asset_type: AssetType = Field(..., description="Type of asset")
    
    # Quantity and cost
    quantity: Decimal = Field(..., description="Number of shares/units held")
    average_cost: Decimal = Field(..., description="Average cost per share/unit")
    total_cost: Decimal = Field(..., description="Total cost basis")
    
    # Current value
    current_price: Decimal = Field(..., description="Current market price")
    market_value: Decimal = Field(..., description="Current market value")
    
    # Performance metrics
    unrealized_gain_loss: Decimal = Field(..., description="Unrealized gain/loss")
    unrealized_gain_loss_percent: Decimal = Field(..., description="Unrealized gain/loss percentage")
    day_change: Decimal = Field(..., description="Day's change in value")
    day_change_percent: Decimal = Field(..., description="Day's change percentage")
    
    # Dividend information
    annual_dividend: Optional[Decimal] = Field(None, description="Annual dividend amount")
    dividend_yield: Optional[Decimal] = Field(None, description="Dividend yield percentage")
    last_dividend_date: Optional[date] = Field(None, description="Last dividend payment date")
    
    # Tax information
    cost_basis_lots: List[Dict[str, Any]] = Field(default_factory=list, description="Cost basis lots for tax purposes")
    
    @property
    def allocation_percentage(self) -> Optional[Decimal]:
        """Calculate allocation percentage (requires portfolio total value)."""
        return None  # Calculated at portfolio level
    
    @validator('market_value')
    def calculate_market_value(cls, v, values):
        if 'quantity' in values and 'current_price' in values:
            calculated = values['quantity'] * values['current_price']
            if abs(v - calculated) > Decimal("0.01"):
                return calculated
        return v


class Portfolio(BaseModel, TimestampMixin):
    """Investment portfolio."""
    portfolio_id: str = Field(..., description="Unique portfolio identifier")
    user_id: str = Field(..., description="Portfolio owner user ID")
    account_id: str = Field(..., description="Associated account ID")
    
    # Portfolio details
    name: str = Field(..., description="Portfolio name")
    description: Optional[str] = Field(None, description="Portfolio description")
    portfolio_type: PortfolioType = Field(..., description="Type of portfolio")
    
    # Investment profile
    risk_tolerance: RiskTolerance = Field(..., description="Risk tolerance level")
    investment_goals: List[InvestmentGoal] = Field(..., description="Investment goals")
    time_horizon: int = Field(..., description="Investment time horizon in years")
    
    # Financial information
    total_value: Decimal = Field(..., description="Total portfolio value")
    cash_balance: Decimal = Field(..., description="Available cash balance")
    invested_amount: Decimal = Field(..., description="Total invested amount")
    total_gain_loss: Decimal = Field(..., description="Total gain/loss")
    total_gain_loss_percent: Decimal = Field(..., description="Total gain/loss percentage")
    day_change: Decimal = Field(..., description="Day's change in value")
    day_change_percent: Decimal = Field(..., description="Day's change percentage")
    
    # Performance metrics
    ytd_return: Decimal = Field(..., description="Year-to-date return")
    one_year_return: Optional[Decimal] = Field(None, description="One year return")
    three_year_return: Optional[Decimal] = Field(None, description="Three year return")
    five_year_return: Optional[Decimal] = Field(None, description="Five year return")
    inception_return: Decimal = Field(..., description="Return since inception")
    
    # Asset allocation
    asset_allocation: Dict[str, Decimal] = Field(default_factory=dict, description="Asset allocation by type")
    sector_allocation: Dict[str, Decimal] = Field(default_factory=dict, description="Sector allocation")
    geographic_allocation: Dict[str, Decimal] = Field(default_factory=dict, description="Geographic allocation")
    
    # Settings
    auto_rebalancing: bool = Field(default=False, description="Enable automatic rebalancing")
    rebalancing_threshold: Decimal = Field(default=Decimal("5.0"), description="Rebalancing threshold percentage")
    dividend_reinvestment: bool = Field(default=True, description="Reinvest dividends automatically")
    
    # Status
    is_active: bool = Field(default=True, description="Portfolio active status")
    last_rebalanced: Optional[datetime] = Field(None, description="Last rebalancing date")


class Order(BaseModel, TimestampMixin):
    """Investment order."""
    order_id: str = Field(..., description="Unique order identifier")
    portfolio_id: str = Field(..., description="Portfolio identifier")
    user_id: str = Field(..., description="User identifier")
    
    # Order details
    symbol: str = Field(..., description="Asset symbol")
    asset_type: AssetType = Field(..., description="Type of asset")
    order_type: OrderType = Field(..., description="Type of order")
    order_side: OrderSide = Field(..., description="Buy or sell")
    
    # Quantity and pricing
    quantity: Decimal = Field(..., gt=0, description="Number of shares/units")
    price: Optional[Decimal] = Field(None, description="Limit price (for limit orders)")
    stop_price: Optional[Decimal] = Field(None, description="Stop price (for stop orders)")
    estimated_cost: Decimal = Field(..., description="Estimated total cost")
    
    # Execution details
    status: OrderStatus = Field(..., description="Order status")
    filled_quantity: Decimal = Field(default=Decimal("0"), description="Quantity filled")
    filled_price: Optional[Decimal] = Field(None, description="Average fill price")
    total_cost: Optional[Decimal] = Field(None, description="Total execution cost")
    
    # Timing
    expires_at: Optional[datetime] = Field(None, description="Order expiration time")
    executed_at: Optional[datetime] = Field(None, description="Execution timestamp")
    
    # Fees and commissions
    commission: Decimal = Field(default=Decimal("0"), description="Commission fee")
    regulatory_fees: Decimal = Field(default=Decimal("0"), description="Regulatory fees")
    other_fees: Decimal = Field(default=Decimal("0"), description="Other fees")
    
    # Order metadata
    external_order_id: Optional[str] = Field(None, description="External broker order ID")
    notes: Optional[str] = Field(None, description="Order notes")
    
    @property
    def remaining_quantity(self) -> Decimal:
        """Calculate remaining unfilled quantity."""
        return self.quantity - self.filled_quantity
    
    @property
    def fill_percentage(self) -> Decimal:
        """Calculate fill percentage."""
        if self.quantity > 0:
            return (self.filled_quantity / self.quantity) * 100
        return Decimal("0")


class Watchlist(BaseModel, TimestampMixin):
    """Investment watchlist."""
    watchlist_id: str = Field(..., description="Unique watchlist identifier")
    user_id: str = Field(..., description="User identifier")
    name: str = Field(..., description="Watchlist name")
    description: Optional[str] = Field(None, description="Watchlist description")
    symbols: List[str] = Field(..., description="List of watched symbols")
    is_default: bool = Field(default=False, description="Default watchlist")
    color: Optional[str] = Field(None, description="Watchlist color for UI")


class DividendPayment(BaseModel):
    """Dividend payment record."""
    dividend_id: str = Field(..., description="Unique dividend identifier")
    portfolio_id: str = Field(..., description="Portfolio identifier")
    symbol: str = Field(..., description="Asset symbol")
    payment_date: date = Field(..., description="Dividend payment date")
    ex_dividend_date: date = Field(..., description="Ex-dividend date")
    amount_per_share: Decimal = Field(..., description="Dividend amount per share")
    shares_held: Decimal = Field(..., description="Number of shares held")
    total_amount: Decimal = Field(..., description="Total dividend amount")
    tax_withheld: Decimal = Field(default=Decimal("0"), description="Tax withheld")
    net_amount: Decimal = Field(..., description="Net dividend amount")
    reinvested: bool = Field(default=False, description="Whether dividend was reinvested")


# Request models
class PortfolioCreateRequest(BaseModel):
    """Request model for creating a portfolio."""
    name: str = Field(..., min_length=1, max_length=100, description="Portfolio name")
    description: Optional[str] = Field(None, max_length=500, description="Portfolio description")
    portfolio_type: PortfolioType = Field(..., description="Type of portfolio")
    account_id: str = Field(..., description="Associated account ID")
    risk_tolerance: RiskTolerance = Field(..., description="Risk tolerance level")
    investment_goals: List[InvestmentGoal] = Field(..., min_items=1, description="Investment goals")
    time_horizon: int = Field(..., ge=1, le=50, description="Investment time horizon in years")
    initial_deposit: Optional[Decimal] = Field(None, gt=0, description="Initial deposit amount")
    auto_rebalancing: bool = Field(default=False, description="Enable automatic rebalancing")
    dividend_reinvestment: bool = Field(default=True, description="Reinvest dividends automatically")


class PortfolioUpdateRequest(BaseModel):
    """Request model for updating portfolio settings."""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Portfolio name")
    description: Optional[str] = Field(None, max_length=500, description="Portfolio description")
    risk_tolerance: Optional[RiskTolerance] = Field(None, description="Risk tolerance level")
    investment_goals: Optional[List[InvestmentGoal]] = Field(None, description="Investment goals")
    time_horizon: Optional[int] = Field(None, ge=1, le=50, description="Investment time horizon")
    auto_rebalancing: Optional[bool] = Field(None, description="Enable automatic rebalancing")
    rebalancing_threshold: Optional[Decimal] = Field(None, ge=0, le=100, description="Rebalancing threshold")
    dividend_reinvestment: Optional[bool] = Field(None, description="Reinvest dividends automatically")


class OrderCreateRequest(BaseModel):
    """Request model for creating investment orders."""
    portfolio_id: str = Field(..., description="Portfolio identifier")
    symbol: str = Field(..., description="Asset symbol")
    order_type: OrderType = Field(..., description="Type of order")
    order_side: OrderSide = Field(..., description="Buy or sell")
    quantity: Decimal = Field(..., gt=0, description="Number of shares/units")
    price: Optional[Decimal] = Field(None, gt=0, description="Limit price (for limit orders)")
    stop_price: Optional[Decimal] = Field(None, gt=0, description="Stop price (for stop orders)")
    time_in_force: str = Field(default="GTC", description="Time in force (GTC, DAY, IOC, FOK)")
    notes: Optional[str] = Field(None, max_length=200, description="Order notes")


class WatchlistCreateRequest(BaseModel):
    """Request model for creating watchlists."""
    name: str = Field(..., min_length=1, max_length=50, description="Watchlist name")
    description: Optional[str] = Field(None, max_length=200, description="Watchlist description")
    symbols: List[str] = Field(default_factory=list, description="Initial symbols to watch")
    color: Optional[str] = Field(None, description="Watchlist color")


class WatchlistUpdateRequest(BaseModel):
    """Request model for updating watchlists."""
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="Watchlist name")
    description: Optional[str] = Field(None, max_length=200, description="Watchlist description")
    color: Optional[str] = Field(None, description="Watchlist color")


class PortfolioAnalysisRequest(BaseModel):
    """Request model for portfolio analysis."""
    portfolio_id: str = Field(..., description="Portfolio identifier")
    analysis_type: str = Field(default="comprehensive", description="Type of analysis")
    benchmark: Optional[str] = Field("SPY", description="Benchmark symbol for comparison")
    period: str = Field(default="1Y", description="Analysis period (1M, 3M, 6M, 1Y, 3Y, 5Y)")


class RebalanceRequest(BaseModel):
    """Request model for portfolio rebalancing."""
    portfolio_id: str = Field(..., description="Portfolio identifier")
    target_allocation: Dict[str, Decimal] = Field(..., description="Target asset allocation percentages")
    rebalance_method: str = Field(default="tax_efficient", description="Rebalancing method")
    dry_run: bool = Field(default=True, description="Perform dry run without executing")


# Response models
class MarketDataResponse(BaseResponse):
    """Response model for market data."""
    market_data: MarketData = Field(..., description="Market data")


class MarketDataListResponse(BaseResponse):
    """Response model for multiple market data."""
    market_data: List[MarketData] = Field(..., description="List of market data")
    total_count: int = Field(..., description="Total number of assets")


class HoldingResponse(BaseResponse):
    """Response model for holding operations."""
    holding: Holding = Field(..., description="Holding details")


class HoldingListResponse(BaseResponse):
    """Response model for holding listings."""
    holdings: List[Holding] = Field(..., description="List of holdings")
    total_count: int = Field(..., description="Total number of holdings")
    total_value: Decimal = Field(..., description="Total portfolio value")
    total_gain_loss: Decimal = Field(..., description="Total gain/loss")
    top_performers: List[Holding] = Field(..., description="Top performing holdings")
    bottom_performers: List[Holding] = Field(..., description="Bottom performing holdings")


class PortfolioResponse(BaseResponse):
    """Response model for portfolio operations."""
    portfolio: Portfolio = Field(..., description="Portfolio details")


class PortfolioListResponse(BaseResponse):
    """Response model for portfolio listings."""
    portfolios: List[Portfolio] = Field(..., description="List of portfolios")
    total_count: int = Field(..., description="Total number of portfolios")
    total_value: Decimal = Field(..., description="Total value across all portfolios")
    best_performer: Optional[Portfolio] = Field(None, description="Best performing portfolio")


class OrderResponse(BaseResponse):
    """Response model for order operations."""
    order: Order = Field(..., description="Order details")


class OrderListResponse(BaseResponse):
    """Response model for order listings."""
    orders: List[Order] = Field(..., description="List of orders")
    total_count: int = Field(..., description="Total number of orders")
    pending_orders: int = Field(..., description="Number of pending orders")
    filled_orders: int = Field(..., description="Number of filled orders")


class WatchlistResponse(BaseResponse):
    """Response model for watchlist operations."""
    watchlist: Watchlist = Field(..., description="Watchlist details")


class WatchlistListResponse(BaseResponse):
    """Response model for watchlist listings."""
    watchlists: List[Watchlist] = Field(..., description="List of watchlists")
    total_count: int = Field(..., description="Total number of watchlists")


class PortfolioAnalysisResponse(BaseResponse):
    """Response model for portfolio analysis."""
    portfolio_id: str = Field(..., description="Portfolio identifier")
    analysis_date: datetime = Field(..., description="Analysis timestamp")
    total_return: Decimal = Field(..., description="Total return percentage")
    annual_return: Decimal = Field(..., description="Annualized return percentage")
    volatility: Decimal = Field(..., description="Portfolio volatility")
    sharpe_ratio: Decimal = Field(..., description="Sharpe ratio")
    beta: Decimal = Field(..., description="Portfolio beta")
    max_drawdown: Decimal = Field(..., description="Maximum drawdown percentage")
    correlation_to_benchmark: Decimal = Field(..., description="Correlation to benchmark")
    asset_allocation: Dict[str, Decimal] = Field(..., description="Current asset allocation")
    performance_attribution: Dict[str, Decimal] = Field(..., description="Performance attribution by holding")
    risk_metrics: Dict[str, Any] = Field(..., description="Additional risk metrics")


class DividendHistoryResponse(BaseResponse):
    """Response model for dividend history."""
    dividends: List[DividendPayment] = Field(..., description="List of dividend payments")
    total_count: int = Field(..., description="Total number of dividend payments")
    total_amount: Decimal = Field(..., description="Total dividend amount")
    annual_yield: Decimal = Field(..., description="Estimated annual dividend yield")


class InvestmentSummaryResponse(BaseResponse):
    """Response model for investment summary."""
    total_portfolios: int = Field(..., description="Number of portfolios")
    total_value: Decimal = Field(..., description="Total investment value")
    total_gain_loss: Decimal = Field(..., description="Total gain/loss")
    total_gain_loss_percent: Decimal = Field(..., description="Total gain/loss percentage")
    day_change: Decimal = Field(..., description="Day's change in value")
    day_change_percent: Decimal = Field(..., description="Day's change percentage")
    cash_available: Decimal = Field(..., description="Available cash across portfolios")
    pending_orders: int = Field(..., description="Number of pending orders")
    recent_dividend_amount: Decimal = Field(..., description="Recent dividend payments (30 days)")
    top_holdings: List[Dict[str, Any]] = Field(..., description="Top holdings across portfolios")


class RebalanceAnalysisResponse(BaseResponse):
    """Response model for rebalancing analysis."""
    portfolio_id: str = Field(..., description="Portfolio identifier")
    current_allocation: Dict[str, Decimal] = Field(..., description="Current allocation percentages")
    target_allocation: Dict[str, Decimal] = Field(..., description="Target allocation percentages")
    rebalancing_actions: List[Dict[str, Any]] = Field(..., description="Required rebalancing actions")
    estimated_trades: List[Dict[str, Any]] = Field(..., description="Estimated trades needed")
    estimated_costs: Decimal = Field(..., description="Estimated rebalancing costs")
    tax_implications: Dict[str, Any] = Field(..., description="Tax implications of rebalancing")


class InvestmentResearchResponse(BaseResponse):
    """Response model for investment research."""
    symbol: str = Field(..., description="Asset symbol")
    research_data: Dict[str, Any] = Field(..., description="Research and analysis data")
    analyst_ratings: Dict[str, Any] = Field(..., description="Analyst ratings and price targets")
    financial_metrics: Dict[str, Any] = Field(..., description="Key financial metrics")
    news_sentiment: Dict[str, Any] = Field(..., description="News sentiment analysis")
    technical_indicators: Dict[str, Any] = Field(..., description="Technical analysis indicators")
