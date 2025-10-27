"""
Investment management API endpoints for the fintech backend.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer
from typing import Optional, List
from datetime import date, datetime

from ..services.investment_service import InvestmentService
from ..models.investment import (
    PortfolioCreateRequest, PortfolioUpdateRequest, OrderCreateRequest,
    WatchlistCreateRequest, WatchlistUpdateRequest, PortfolioAnalysisRequest,
    RebalanceRequest, PortfolioResponse, PortfolioListResponse,
    HoldingResponse, HoldingListResponse, OrderResponse, OrderListResponse,
    WatchlistResponse, WatchlistListResponse, MarketDataResponse,
    MarketDataListResponse, PortfolioAnalysisResponse, DividendHistoryResponse,
    InvestmentSummaryResponse, RebalanceAnalysisResponse, InvestmentResearchResponse,
    AssetType, OrderStatus, OrderType, OrderSide
)
from ..models.base import PaginationRequest, BaseResponse
from ..core.auth import get_current_user

router = APIRouter(prefix="/investments", tags=["Investments"])
security = HTTPBearer()

# Initialize service
investment_service = InvestmentService()


@router.get("/health", response_model=BaseResponse)
async def get_investment_health():
    """Get investment service health status."""
    health_data = await investment_service.get_service_health()
    return BaseResponse(
        success=True,
        message="Investment service is healthy",
        data=health_data
    )


# Portfolio Management Endpoints
@router.post("/portfolios", response_model=PortfolioResponse)
async def create_portfolio(
    request: PortfolioCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create a new investment portfolio."""
    try:
        portfolio = await investment_service.create_portfolio(current_user["user_id"], request)
        return PortfolioResponse(
            success=True,
            message="Portfolio created successfully",
            data={"portfolio": portfolio}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create portfolio: {str(e)}"
        )


@router.get("/portfolios", response_model=PortfolioListResponse)
async def get_portfolios(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(get_current_user)
):
    """Get portfolios for the authenticated user."""
    try:
        pagination = PaginationRequest(page=page, page_size=limit)
        result = await investment_service.get_portfolios(current_user["user_id"], pagination)
        
        return PortfolioListResponse(
            success=True,
            message="Portfolios retrieved successfully",
            **result
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve portfolios: {str(e)}"
        )


@router.get("/portfolios/{portfolio_id}", response_model=PortfolioResponse)
async def get_portfolio(
    portfolio_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific portfolio."""
    try:
        portfolio = await investment_service.get_portfolio(current_user["user_id"], portfolio_id)
        return PortfolioResponse(
            success=True,
            message="Portfolio retrieved successfully",
            data={"portfolio": portfolio}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Portfolio not found: {str(e)}"
        )


@router.patch("/portfolios/{portfolio_id}", response_model=PortfolioResponse)
async def update_portfolio(
    portfolio_id: str,
    request: PortfolioUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update portfolio settings."""
    try:
        portfolio = await investment_service.update_portfolio(
            current_user["user_id"], portfolio_id, request
        )
        return PortfolioResponse(
            success=True,
            message="Portfolio updated successfully",
            data={"portfolio": portfolio}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update portfolio: {str(e)}"
        )


# Holdings Endpoints
@router.get("/portfolios/{portfolio_id}/holdings", response_model=HoldingListResponse)
async def get_holdings(
    portfolio_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get holdings for a portfolio."""
    try:
        result = await investment_service.get_holdings(current_user["user_id"], portfolio_id)
        return HoldingListResponse(
            success=True,
            message="Holdings retrieved successfully",
            data=result
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Failed to retrieve holdings: {str(e)}"
        )


# Order Management Endpoints
@router.post("/orders", response_model=OrderResponse)
async def create_order(
    request: OrderCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create a new investment order."""
    try:
        order = await investment_service.create_order(current_user["user_id"], request)
        return OrderResponse(
            success=True,
            message="Order created successfully",
            data={"order": order}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create order: {str(e)}"
        )


@router.get("/orders", response_model=OrderListResponse)
async def get_orders(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    portfolio_id: Optional[str] = Query(None, description="Filter by portfolio"),
    status: Optional[OrderStatus] = Query(None, description="Filter by status"),
    current_user: dict = Depends(get_current_user)
):
    """Get investment orders for the authenticated user."""
    try:
        pagination = PaginationRequest(page=page, page_size=limit)
        result = await investment_service.get_orders(
            current_user["user_id"], portfolio_id, status, pagination
        )
        
        return OrderListResponse(
            success=True,
            message="Orders retrieved successfully",
            data=result
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve orders: {str(e)}"
        )


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific order."""
    try:
        order = await investment_service.get_order(current_user["user_id"], order_id)
        return OrderResponse(
            success=True,
            message="Order retrieved successfully",
            data={"order": order}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order not found: {str(e)}"
        )


@router.patch("/orders/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    order_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Cancel an order."""
    try:
        order = await investment_service.cancel_order(current_user["user_id"], order_id)
        return OrderResponse(
            success=True,
            message="Order cancelled successfully",
            data={"order": order}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to cancel order: {str(e)}"
        )


# Market Data Endpoints
@router.get("/market-data", response_model=MarketDataListResponse)
async def get_market_data(
    symbols: List[str] = Query(..., description="List of symbols to get data for"),
    current_user: dict = Depends(get_current_user)
):
    """Get market data for specific symbols."""
    try:
        market_data = await investment_service.get_market_data(symbols)
        return MarketDataListResponse(
            success=True,
            message="Market data retrieved successfully",
            data={
                "market_data": market_data,
                "total_count": len(market_data)
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve market data: {str(e)}"
        )


@router.get("/search", response_model=MarketDataListResponse)
async def search_assets(
    query: str = Query(..., min_length=1, description="Search query"),
    asset_types: Optional[List[AssetType]] = Query(None, description="Filter by asset types"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    current_user: dict = Depends(get_current_user)
):
    """Search for investment assets."""
    try:
        results = await investment_service.search_assets(query, asset_types, limit)
        return MarketDataListResponse(
            success=True,
            message="Asset search completed successfully",
            data={
                "market_data": results,
                "total_count": len(results)
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search assets: {str(e)}"
        )


@router.get("/research/{symbol}", response_model=InvestmentResearchResponse)
async def get_investment_research(
    symbol: str,
    current_user: dict = Depends(get_current_user)
):
    """Get comprehensive investment research for a symbol."""
    try:
        research = await investment_service.get_investment_research(symbol)
        return InvestmentResearchResponse(
            success=True,
            message="Investment research retrieved successfully",
            data=research
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research not found: {str(e)}"
        )


# Watchlist Endpoints
@router.post("/watchlists", response_model=WatchlistResponse)
async def create_watchlist(
    request: WatchlistCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create a new watchlist."""
    try:
        watchlist = await investment_service.create_watchlist(current_user["user_id"], request)
        return WatchlistResponse(
            success=True,
            message="Watchlist created successfully",
            data={"watchlist": watchlist}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create watchlist: {str(e)}"
        )


@router.get("/watchlists", response_model=WatchlistListResponse)
async def get_watchlists(
    current_user: dict = Depends(get_current_user)
):
    """Get watchlists for the authenticated user."""
    try:
        watchlists = await investment_service.get_watchlists(current_user["user_id"])
        return WatchlistListResponse(
            success=True,
            message="Watchlists retrieved successfully",
            data={
                "watchlists": watchlists,
                "total_count": len(watchlists)
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve watchlists: {str(e)}"
        )


@router.get("/watchlists/{watchlist_id}", response_model=WatchlistResponse)
async def get_watchlist(
    watchlist_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific watchlist."""
    try:
        watchlist = await investment_service.get_watchlist(current_user["user_id"], watchlist_id)
        return WatchlistResponse(
            success=True,
            message="Watchlist retrieved successfully",
            data={"watchlist": watchlist}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Watchlist not found: {str(e)}"
        )


@router.patch("/watchlists/{watchlist_id}", response_model=WatchlistResponse)
async def update_watchlist(
    watchlist_id: str,
    request: WatchlistUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update watchlist settings."""
    try:
        watchlist = await investment_service.update_watchlist(
            current_user["user_id"], watchlist_id, request
        )
        return WatchlistResponse(
            success=True,
            message="Watchlist updated successfully",
            data={"watchlist": watchlist}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update watchlist: {str(e)}"
        )


@router.post("/watchlists/{watchlist_id}/symbols/{symbol}", response_model=WatchlistResponse)
async def add_to_watchlist(
    watchlist_id: str,
    symbol: str,
    current_user: dict = Depends(get_current_user)
):
    """Add symbol to watchlist."""
    try:
        watchlist = await investment_service.add_to_watchlist(
            current_user["user_id"], watchlist_id, symbol
        )
        return WatchlistResponse(
            success=True,
            message="Symbol added to watchlist successfully",
            data={"watchlist": watchlist}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to add symbol to watchlist: {str(e)}"
        )


@router.delete("/watchlists/{watchlist_id}/symbols/{symbol}", response_model=WatchlistResponse)
async def remove_from_watchlist(
    watchlist_id: str,
    symbol: str,
    current_user: dict = Depends(get_current_user)
):
    """Remove symbol from watchlist."""
    try:
        watchlist = await investment_service.remove_from_watchlist(
            current_user["user_id"], watchlist_id, symbol
        )
        return WatchlistResponse(
            success=True,
            message="Symbol removed from watchlist successfully",
            data={"watchlist": watchlist}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to remove symbol from watchlist: {str(e)}"
        )


# Analysis Endpoints
@router.post("/portfolios/{portfolio_id}/analysis", response_model=PortfolioAnalysisResponse)
async def get_portfolio_analysis(
    portfolio_id: str,
    analysis_type: str = Query("comprehensive", description="Type of analysis"),
    benchmark: str = Query("SPY", description="Benchmark symbol"),
    period: str = Query("1Y", description="Analysis period"),
    current_user: dict = Depends(get_current_user)
):
    """Get comprehensive portfolio analysis."""
    try:
        analysis_request = PortfolioAnalysisRequest(
            portfolio_id=portfolio_id,
            analysis_type=analysis_type,
            benchmark=benchmark,
            period=period
        )
        
        analysis = await investment_service.get_portfolio_analysis(
            current_user["user_id"], analysis_request
        )
        
        return PortfolioAnalysisResponse(
            success=True,
            message="Portfolio analysis completed successfully",
            data=analysis
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Failed to analyze portfolio: {str(e)}"
        )


@router.post("/portfolios/{portfolio_id}/rebalance-analysis", response_model=RebalanceAnalysisResponse)
async def analyze_rebalancing(
    portfolio_id: str,
    request: RebalanceRequest,
    current_user: dict = Depends(get_current_user)
):
    """Analyze portfolio rebalancing requirements."""
    try:
        # Set portfolio_id from URL
        request.portfolio_id = portfolio_id
        
        analysis = await investment_service.analyze_rebalancing(current_user["user_id"], request)
        return RebalanceAnalysisResponse(
            success=True,
            message="Rebalancing analysis completed successfully",
            data=analysis
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to analyze rebalancing: {str(e)}"
        )


@router.get("/portfolios/{portfolio_id}/dividends", response_model=DividendHistoryResponse)
async def get_dividend_history(
    portfolio_id: str,
    start_date: Optional[date] = Query(None, description="Start date for dividend history"),
    end_date: Optional[date] = Query(None, description="End date for dividend history"),
    current_user: dict = Depends(get_current_user)
):
    """Get dividend payment history for a portfolio."""
    try:
        result = await investment_service.get_dividend_history(
            current_user["user_id"], portfolio_id, start_date, end_date
        )
        
        return DividendHistoryResponse(
            success=True,
            message="Dividend history retrieved successfully",
            data=result
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Failed to retrieve dividend history: {str(e)}"
        )


# Summary and Dashboard Endpoints
@router.get("/summary", response_model=InvestmentSummaryResponse)
async def get_investment_summary(
    current_user: dict = Depends(get_current_user)
):
    """Get investment summary across all portfolios."""
    try:
        summary = await investment_service.get_investment_summary(current_user["user_id"])
        return InvestmentSummaryResponse(
            success=True,
            message="Investment summary retrieved successfully",
            **summary
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve investment summary: {str(e)}"
        )


@router.get("/trending", response_model=BaseResponse)
async def get_trending_assets(
    asset_type: Optional[AssetType] = Query(None, description="Filter by asset type"),
    limit: int = Query(10, ge=1, le=50, description="Number of trending assets"),
    current_user: dict = Depends(get_current_user)
):
    """Get trending assets based on volume and price movement."""
    try:
        # Mock trending assets
        all_market_data = list(investment_service.market_data.values())
        
        if asset_type:
            all_market_data = [md for md in all_market_data if md.asset_type == asset_type]
        
        # Sort by day change percentage and volume
        trending = sorted(
            all_market_data,
            key=lambda x: (abs(x.day_change_percent), x.volume),
            reverse=True
        )[:limit]
        
        trending_data = [
            {
                "symbol": md.symbol,
                "name": md.name,
                "current_price": md.current_price,
                "day_change_percent": md.day_change_percent,
                "volume": md.volume,
                "asset_type": md.asset_type
            }
            for md in trending
        ]
        
        return BaseResponse(
            success=True,
            message="Trending assets retrieved successfully",
            data={"trending_assets": trending_data}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve trending assets: {str(e)}"
        )


@router.get("/movers", response_model=BaseResponse)
async def get_market_movers(
    direction: str = Query("gainers", description="Direction: gainers, losers, most_active"),
    asset_type: Optional[AssetType] = Query(None, description="Filter by asset type"),
    limit: int = Query(10, ge=1, le=50, description="Number of movers"),
    current_user: dict = Depends(get_current_user)
):
    """Get market movers (gainers, losers, most active)."""
    try:
        all_market_data = list(investment_service.market_data.values())
        
        if asset_type:
            all_market_data = [md for md in all_market_data if md.asset_type == asset_type]
        
        if direction == "gainers":
            movers = sorted(all_market_data, key=lambda x: x.day_change_percent, reverse=True)
        elif direction == "losers":
            movers = sorted(all_market_data, key=lambda x: x.day_change_percent)
        elif direction == "most_active":
            movers = sorted(all_market_data, key=lambda x: x.volume, reverse=True)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid direction. Use 'gainers', 'losers', or 'most_active'"
            )
        
        movers = movers[:limit]
        
        movers_data = [
            {
                "symbol": md.symbol,
                "name": md.name,
                "current_price": md.current_price,
                "day_change": md.day_change,
                "day_change_percent": md.day_change_percent,
                "volume": md.volume,
                "asset_type": md.asset_type
            }
            for md in movers
        ]
        
        return BaseResponse(
            success=True,
            message=f"Market {direction} retrieved successfully",
            data={f"{direction}": movers_data}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve market movers: {str(e)}"
        )


@router.get("/performance-summary", response_model=BaseResponse)
async def get_performance_summary(
    period: str = Query("1M", description="Performance period (1M, 3M, 6M, 1Y, 3Y, 5Y)"),
    current_user: dict = Depends(get_current_user)
):
    """Get investment performance summary across all portfolios."""
    try:
        user_portfolios = [p for p in investment_service.portfolios.values() 
                          if p.user_id == current_user["user_id"]]
        
        if not user_portfolios:
            return BaseResponse(
                success=True,
                message="No portfolios found",
                data={"performance_data": {}}
            )
        
        # Calculate performance metrics based on period
        total_value = sum(p.total_value for p in user_portfolios)
        total_gain_loss = sum(p.total_gain_loss for p in user_portfolios)
        
        # Mock period-specific returns
        period_returns = {
            "1M": Decimal("2.15"),
            "3M": Decimal("7.45"),
            "6M": Decimal("12.30"),
            "1Y": Decimal("18.75"),
            "3Y": Decimal("45.20"),
            "5Y": Decimal("95.80")
        }
        
        performance_data = {
            "period": period,
            "total_value": total_value,
            "total_gain_loss": total_gain_loss,
            "period_return": period_returns.get(period, Decimal("0")),
            "best_performing_portfolio": max(user_portfolios, key=lambda x: x.total_gain_loss_percent).name if user_portfolios else None,
            "worst_performing_portfolio": min(user_portfolios, key=lambda x: x.total_gain_loss_percent).name if user_portfolios else None,
            "portfolio_count": len(user_portfolios)
        }
        
        return BaseResponse(
            success=True,
            message="Performance summary retrieved successfully",
            data={"performance_data": performance_data}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve performance summary: {str(e)}"
        )


# Quick Actions
@router.get("/quick-buy-suggestions", response_model=BaseResponse)
async def get_quick_buy_suggestions(
    risk_level: Optional[str] = Query("moderate", description="Risk level for suggestions"),
    amount: Optional[float] = Query(1000, description="Investment amount for suggestions"),
    current_user: dict = Depends(get_current_user)
):
    """Get quick buy suggestions based on user profile."""
    try:
        # Mock suggestions based on risk level
        suggestions_map = {
            "conservative": ["SPY", "VTI", "BND"],
            "moderate": ["AAPL", "GOOGL", "SPY"],
            "aggressive": ["TSLA", "NVDA", "QQQ"]
        }
        
        suggested_symbols = suggestions_map.get(risk_level, suggestions_map["moderate"])
        suggested_assets = []
        
        for symbol in suggested_symbols:
            market_data = investment_service.market_data.get(symbol)
            if market_data:
                shares_can_buy = int(Decimal(str(amount)) / market_data.current_price)
                suggested_assets.append({
                    "symbol": symbol,
                    "name": market_data.name,
                    "current_price": market_data.current_price,
                    "day_change_percent": market_data.day_change_percent,
                    "suggested_shares": shares_can_buy,
                    "estimated_cost": shares_can_buy * market_data.current_price,
                    "reason": f"Suitable for {risk_level} risk tolerance"
                })
        
        return BaseResponse(
            success=True,
            message="Quick buy suggestions retrieved successfully",
            data={
                "suggestions": suggested_assets,
                "risk_level": risk_level,
                "target_amount": amount
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve buy suggestions: {str(e)}"
        )


@router.get("/pending-orders", response_model=BaseResponse)
async def get_pending_orders(
    current_user: dict = Depends(get_current_user)
):
    """Get pending orders across all portfolios."""
    try:
        result = await investment_service.get_orders(
            current_user["user_id"], None, OrderStatus.PENDING
        )
        
        return BaseResponse(
            success=True,
            message="Pending orders retrieved successfully",
            data={
                "pending_orders": result["orders"],
                "count": len(result["orders"])
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve pending orders: {str(e)}"
        )


@router.get("/allocation-overview", response_model=BaseResponse)
async def get_allocation_overview(
    current_user: dict = Depends(get_current_user)
):
    """Get asset allocation overview across all portfolios."""
    try:
        user_portfolios = [p for p in investment_service.portfolios.values() 
                          if p.user_id == current_user["user_id"]]
        
        if not user_portfolios:
            return BaseResponse(
                success=True,
                message="No portfolios found",
                data={"allocation": {}}
            )
        
        # Aggregate allocation across all portfolios
        total_value = sum(p.total_value for p in user_portfolios)
        aggregated_allocation = {}
        
        for portfolio in user_portfolios:
            portfolio_weight = portfolio.total_value / total_value if total_value > 0 else 0
            
            for asset_class, allocation_pct in portfolio.asset_allocation.items():
                weighted_allocation = allocation_pct * Decimal(str(portfolio_weight))
                if asset_class in aggregated_allocation:
                    aggregated_allocation[asset_class] += weighted_allocation
                else:
                    aggregated_allocation[asset_class] = weighted_allocation
        
        return BaseResponse(
            success=True,
            message="Allocation overview retrieved successfully",
            data={
                "allocation": aggregated_allocation,
                "total_value": total_value,
                "portfolio_count": len(user_portfolios)
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve allocation overview: {str(e)}"
        )
