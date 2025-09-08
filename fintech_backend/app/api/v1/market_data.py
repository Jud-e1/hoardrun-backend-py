from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional, Dict, Any
from datetime import datetime

from ...core.auth import get_current_user
from ...models.market_data import (
    MarketDataRequest, HistoricalDataRequest, WatchlistRequest, MarketAlertRequest,
    MarketQuote, HistoricalData, MarketSummary, WatchlistProfile, MarketAlert,
    MarketAnalytics, CurrencyExchangeRate, MarketDataType, TimeInterval
)
from ...services.market_data_service import MarketDataService
from ...core.exceptions import NotFoundError, ValidationError, BusinessLogicError

router = APIRouter(prefix="/market", tags=["market_data"])
market_service = MarketDataService()

@router.post("/quotes", response_model=List[MarketQuote])
async def get_market_quotes(
    request: MarketDataRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Get real-time market quotes for specified symbols.
    
    - **symbols**: List of symbols to get quotes for (1-50 symbols)
    - **data_type**: Type of market data (stock, forex, crypto, commodity, index)
    
    Returns real-time price data including:
    - Current price, open, high, low, volume
    - Price change amount and percentage
    - Market cap (for stocks)
    - Market status (open, closed, pre-market, after-hours)
    """
    try:
        quotes = await market_service.get_market_quotes(request)
        return quotes
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve market quotes: {str(e)}"
        )

@router.get("/quotes/{symbol}", response_model=MarketQuote)
async def get_single_quote(
    symbol: str,
    data_type: MarketDataType = Query(MarketDataType.STOCK, description="Type of market data"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get real-time quote for a single symbol.
    
    - **symbol**: Symbol to get quote for (e.g., AAPL, EURUSD, BTCUSD)
    - **data_type**: Type of market data (stock, forex, crypto, commodity, index)
    """
    try:
        request = MarketDataRequest(symbols=[symbol], data_type=data_type)
        quotes = await market_service.get_market_quotes(request)
        
        if not quotes:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quote not found for symbol: {symbol}"
            )
        
        return quotes[0]
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve quote for {symbol}: {str(e)}"
        )

@router.post("/historical", response_model=HistoricalData)
async def get_historical_data(
    request: HistoricalDataRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Get historical market data for a symbol.
    
    - **symbol**: Symbol to get historical data for
    - **data_type**: Type of market data (stock, forex, crypto, commodity, index)
    - **interval**: Time interval (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w, 1M)
    - **start_date**: Start date for historical data (optional)
    - **end_date**: End date for historical data (optional)
    - **limit**: Maximum number of data points to return (1-1000)
    
    Returns OHLCV (Open, High, Low, Close, Volume) data points.
    """
    try:
        historical_data = await market_service.get_historical_data(request)
        return historical_data
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve historical data: {str(e)}"
        )

@router.get("/summary", response_model=MarketSummary)
async def get_market_summary(
    current_user: dict = Depends(get_current_user)
):
    """
    Get market summary with top movers and market indices.
    
    Returns:
    - Market status and statistics
    - Top gainers and losers
    - Most active stocks by volume
    - Major market indices (SPY, QQQ, DIA)
    - User's watchlist and alert counts
    """
    try:
        summary = await market_service.get_market_summary()
        return summary
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve market summary: {str(e)}"
        )

@router.post("/watchlists", response_model=WatchlistProfile, status_code=status.HTTP_201_CREATED)
async def create_watchlist(
    request: WatchlistRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new watchlist.
    
    - **name**: Name for the watchlist (1-100 characters)
    - **symbols**: List of symbols to include (1-100 symbols)
    - **data_type**: Type of market data for all symbols
    
    Returns the created watchlist with current quotes for all symbols.
    """
    try:
        watchlist = await market_service.create_watchlist(
            user_id=current_user["user_id"],
            request=request
        )
        return watchlist
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create watchlist: {str(e)}"
        )

@router.get("/watchlists", response_model=List[WatchlistProfile])
async def get_user_watchlists(
    current_user: dict = Depends(get_current_user)
):
    """
    Get all watchlists for the current user.
    
    Returns all user's watchlists with current quotes and performance metrics.
    """
    try:
        watchlists = await market_service.get_user_watchlists(
            user_id=current_user["user_id"]
        )
        return watchlists
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve watchlists: {str(e)}"
        )

@router.post("/alerts", response_model=MarketAlert, status_code=status.HTTP_201_CREATED)
async def create_market_alert(
    request: MarketAlertRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new market alert.
    
    - **symbol**: Symbol to monitor
    - **data_type**: Type of market data
    - **alert_type**: Type of alert (price_above, price_below, volume_above, change_above, change_below)
    - **threshold_value**: Threshold value that triggers the alert
    - **is_active**: Whether the alert is active
    
    The alert will trigger when the specified condition is met.
    """
    try:
        alert = await market_service.create_market_alert(
            user_id=current_user["user_id"],
            request=request
        )
        return alert
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create market alert: {str(e)}"
        )

@router.get("/alerts", response_model=List[MarketAlert])
async def get_user_alerts(
    current_user: dict = Depends(get_current_user)
):
    """
    Get all market alerts for the current user.
    
    Returns all user's alerts with current values and trigger status.
    """
    try:
        alerts = await market_service.get_user_alerts(
            user_id=current_user["user_id"]
        )
        return alerts
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve market alerts: {str(e)}"
        )

@router.get("/currency-rates", response_model=List[CurrencyExchangeRate])
async def get_currency_rates(
    base_currency: str = Query("USD", description="Base currency for exchange rates"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get currency exchange rates.
    
    - **base_currency**: Base currency to get rates for (default: USD)
    
    Returns exchange rates for major currency pairs including:
    - Current exchange rate and inverse rate
    - 24-hour change amount and percentage
    - Last updated timestamp
    """
    try:
        rates = await market_service.get_currency_rates(base_currency)
        return rates
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve currency rates: {str(e)}"
        )

@router.get("/analytics/{symbol}", response_model=MarketAnalytics)
async def get_market_analytics(
    symbol: str,
    data_type: MarketDataType = Query(MarketDataType.STOCK, description="Type of market data"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get market analytics and technical indicators for a symbol.
    
    - **symbol**: Symbol to analyze
    - **data_type**: Type of market data
    
    Returns comprehensive technical analysis including:
    - Trend direction and support/resistance levels
    - RSI (Relative Strength Index)
    - Moving averages (20, 50, 200-day)
    - Volatility and beta (for stocks)
    - Buy/sell/hold recommendation with confidence score
    """
    try:
        analytics = await market_service.get_market_analytics(symbol, data_type)
        return analytics
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve market analytics for {symbol}: {str(e)}"
        )

@router.get("/health", response_model=Dict[str, Any])
async def get_market_data_health():
    """
    Get market data service health status.
    
    Returns service health metrics including:
    - Total watchlists and alerts
    - Cache performance metrics
    - Data source status
    - Service version information
    """
    try:
        health_status = await market_service.get_health_status()
        return health_status
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve health status: {str(e)}"
        )
