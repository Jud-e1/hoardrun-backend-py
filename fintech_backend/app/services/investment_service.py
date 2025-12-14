"""
Investment management service for the fintech backend.
"""

import asyncio
import uuid
import random
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import List, Optional, Dict, Any

from ..models.investment import (
    Portfolio, Holding, Order, Watchlist, MarketData, DividendPayment,
    AssetType, OrderType, OrderSide, OrderStatus, PortfolioType,
    RiskTolerance, InvestmentGoal, PortfolioCreateRequest,
    PortfolioUpdateRequest, OrderCreateRequest, WatchlistCreateRequest,
    WatchlistUpdateRequest, PortfolioAnalysisRequest, RebalanceRequest
)
from ..models.base import PaginationRequest
from ..core.exceptions import NotFoundError, ValidationError, BusinessLogicError


class InvestmentService:
    """Service for handling investment management operations."""
    
    def __init__(self):
        # Mock data storage - replace with actual database
        self.portfolios: Dict[str, Portfolio] = {}
        self.holdings: Dict[str, List[Holding]] = {}  # portfolio_id -> holdings
        self.orders: Dict[str, Order] = {}
        self.watchlists: Dict[str, List[Watchlist]] = {}  # user_id -> watchlists
        self.market_data: Dict[str, MarketData] = {}
        self.dividend_payments: Dict[str, List[DividendPayment]] = {}  # portfolio_id -> dividends
        
        # Initialize with mock data
        self._initialize_mock_data()
    
    def _initialize_mock_data(self):
        """Initialize with mock investment data."""
        # Mock market data
        mock_stocks = [
            ("AAPL", "Apple Inc.", AssetType.STOCK, Decimal("175.50"), Decimal("174.20")),
            ("GOOGL", "Alphabet Inc.", AssetType.STOCK, Decimal("2650.75"), Decimal("2640.30")),
            ("TSLA", "Tesla Inc.", AssetType.STOCK, Decimal("245.80"), Decimal("250.15")),
            ("SPY", "SPDR S&P 500 ETF", AssetType.ETF, Decimal("445.20"), Decimal("444.80")),
            ("VTI", "Vanguard Total Stock Market ETF", AssetType.ETF, Decimal("235.60"), Decimal("234.90"))
        ]
        
        for symbol, name, asset_type, current, previous in mock_stocks:
            day_change = current - previous
            day_change_percent = (day_change / previous) * 100
            
            self.market_data[symbol] = MarketData(
                symbol=symbol,
                name=name,
                asset_type=asset_type,
                current_price=current,
                previous_close=previous,
                day_change=day_change,
                day_change_percent=day_change_percent,
                volume=random.randint(1000000, 50000000),
                market_cap=Decimal(str(random.uniform(50, 3000))) * Decimal("1000000000") if asset_type == AssetType.STOCK else None,
                pe_ratio=Decimal(str(random.uniform(15, 35))) if asset_type == AssetType.STOCK else None,
                dividend_yield=Decimal(str(random.uniform(0.5, 4.0))),
                week_52_high=current * Decimal("1.15"),
                week_52_low=current * Decimal("0.85"),
                beta=Decimal(str(random.uniform(0.8, 1.5)))
            )
        
        # Mock portfolio for user_123
        mock_portfolio = Portfolio(
            portfolio_id="port_123_001",
            user_id="user_123",
            account_id="acc_123_002",
            name="Growth Portfolio",
            description="Long-term growth focused portfolio",
            portfolio_type=PortfolioType.INDIVIDUAL,
            risk_tolerance=RiskTolerance.MODERATE,
            investment_goals=[InvestmentGoal.WEALTH_BUILDING, InvestmentGoal.RETIREMENT],
            time_horizon=20,
            total_value=Decimal("25750.00"),
            cash_balance=Decimal("1250.00"),
            invested_amount=Decimal("24500.00"),
            total_gain_loss=Decimal("2750.00"),
            total_gain_loss_percent=Decimal("12.62"),
            day_change=Decimal("125.50"),
            day_change_percent=Decimal("0.49"),
            ytd_return=Decimal("18.45"),
            inception_return=Decimal("12.62"),
            asset_allocation={
                "stocks": Decimal("75.0"),
                "etfs": Decimal("20.0"),
                "cash": Decimal("5.0")
            }
        )
        self.portfolios["port_123_001"] = mock_portfolio
        
        # Mock holdings
        mock_holdings = [
            Holding(
                holding_id="hold_001",
                portfolio_id="port_123_001",
                symbol="AAPL",
                asset_type=AssetType.STOCK,
                quantity=Decimal("50"),
                average_cost=Decimal("165.00"),
                total_cost=Decimal("8250.00"),
                current_price=Decimal("175.50"),
                market_value=Decimal("8775.00"),
                unrealized_gain_loss=Decimal("525.00"),
                unrealized_gain_loss_percent=Decimal("6.36"),
                day_change=Decimal("65.00"),
                day_change_percent=Decimal("0.74"),
                annual_dividend=Decimal("23.00"),
                dividend_yield=Decimal("0.53")
            ),
            Holding(
                holding_id="hold_002",
                portfolio_id="port_123_001",
                symbol="SPY",
                asset_type=AssetType.ETF,
                quantity=Decimal("35"),
                average_cost=Decimal("420.00"),
                total_cost=Decimal("14700.00"),
                current_price=Decimal("445.20"),
                market_value=Decimal("15582.00"),
                unrealized_gain_loss=Decimal("882.00"),
                unrealized_gain_loss_percent=Decimal("6.00"),
                day_change=Decimal("14.00"),
                day_change_percent=Decimal("0.09"),
                annual_dividend=Decimal("21.50"),
                dividend_yield=Decimal("1.38")
            )
        ]
        self.holdings["port_123_001"] = mock_holdings
        
        # Mock watchlist
        mock_watchlist = Watchlist(
            watchlist_id="watch_001",
            user_id="user_123",
            name="Tech Stocks",
            description="Technology sector watchlist",
            symbols=["AAPL", "GOOGL", "MSFT", "TSLA", "NVDA"],
            is_default=True,
            color="#3B82F6"
        )
        self.watchlists["user_123"] = [mock_watchlist]
    
    async def create_portfolio(self, user_id: str, request: PortfolioCreateRequest) -> Portfolio:
        """Create a new investment portfolio."""
        await asyncio.sleep(0.2)
        
        # Validate account ownership (mock validation)
        if not request.account_id.startswith(f"acc_{user_id}"):
            raise ValidationError("Account does not belong to user")
        
        # Create portfolio
        portfolio = Portfolio(
            portfolio_id=f"port_{user_id}_{uuid.uuid4().hex[:8]}",
            user_id=user_id,
            account_id=request.account_id,
            name=request.name,
            description=request.description,
            portfolio_type=request.portfolio_type,
            risk_tolerance=request.risk_tolerance,
            investment_goals=request.investment_goals,
            time_horizon=request.time_horizon,
            total_value=request.initial_deposit or Decimal("0"),
            cash_balance=request.initial_deposit or Decimal("0"),
            invested_amount=Decimal("0"),
            total_gain_loss=Decimal("0"),
            total_gain_loss_percent=Decimal("0"),
            day_change=Decimal("0"),
            day_change_percent=Decimal("0"),
            ytd_return=Decimal("0"),
            inception_return=Decimal("0"),
            auto_rebalancing=request.auto_rebalancing,
            dividend_reinvestment=request.dividend_reinvestment
        )
        
        self.portfolios[portfolio.portfolio_id] = portfolio
        self.holdings[portfolio.portfolio_id] = []
        
        return portfolio
    
    async def get_portfolios(self, user_id: str, pagination: PaginationRequest) -> Dict[str, Any]:
        """Get portfolios for a user."""
        await asyncio.sleep(0.1)
        
        user_portfolios = [p for p in self.portfolios.values() if p.user_id == user_id]
        user_portfolios.sort(key=lambda x: x.created_at, reverse=True)
        
        # Apply pagination
        total_count = len(user_portfolios)
        start_idx = (pagination.page - 1) * pagination.page_size
        end_idx = start_idx + pagination.page_size
        portfolios = user_portfolios[start_idx:end_idx]
        
        # Calculate totals
        total_value = sum(p.total_value for p in user_portfolios)
        best_performer = max(user_portfolios, key=lambda x: x.total_gain_loss_percent) if user_portfolios else None
        
        return {
            "portfolios": portfolios,
            "total_count": total_count,
            "total_value": total_value,
            "best_performer": best_performer
        }
    
    async def get_portfolio(self, user_id: str, portfolio_id: str) -> Portfolio:
        """Get a specific portfolio."""
        await asyncio.sleep(0.1)
        
        portfolio = self.portfolios.get(portfolio_id)
        if not portfolio or portfolio.user_id != user_id:
            raise NotFoundError("Portfolio not found")
        
        return portfolio
    
    async def update_portfolio(self, user_id: str, portfolio_id: str, 
                             request: PortfolioUpdateRequest) -> Portfolio:
        """Update portfolio settings."""
        await asyncio.sleep(0.1)
        
        portfolio = await self.get_portfolio(user_id, portfolio_id)
        
        # Update fields if provided
        if request.name is not None:
            portfolio.name = request.name
        if request.description is not None:
            portfolio.description = request.description
        if request.risk_tolerance is not None:
            portfolio.risk_tolerance = request.risk_tolerance
        if request.investment_goals is not None:
            portfolio.investment_goals = request.investment_goals
        if request.time_horizon is not None:
            portfolio.time_horizon = request.time_horizon
        if request.auto_rebalancing is not None:
            portfolio.auto_rebalancing = request.auto_rebalancing
        if request.rebalancing_threshold is not None:
            portfolio.rebalancing_threshold = request.rebalancing_threshold
        if request.dividend_reinvestment is not None:
            portfolio.dividend_reinvestment = request.dividend_reinvestment
        
        portfolio.updated_at = datetime.utcnow()
        
        return portfolio
    
    async def get_holdings(self, user_id: str, portfolio_id: str) -> Dict[str, Any]:
        """Get holdings for a portfolio."""
        await asyncio.sleep(0.1)
        
        # Verify portfolio ownership
        await self.get_portfolio(user_id, portfolio_id)
        
        holdings = self.holdings.get(portfolio_id, [])
        
        # Update current prices and calculations
        for holding in holdings:
            market_data = self.market_data.get(holding.symbol)
            if market_data:
                holding.current_price = market_data.current_price
                holding.market_value = holding.quantity * holding.current_price
                holding.unrealized_gain_loss = holding.market_value - holding.total_cost
                holding.unrealized_gain_loss_percent = (holding.unrealized_gain_loss / holding.total_cost) * 100
                holding.day_change = holding.quantity * market_data.day_change
                holding.day_change_percent = market_data.day_change_percent
        
        # Calculate metrics
        total_value = sum(h.market_value for h in holdings)
        total_gain_loss = sum(h.unrealized_gain_loss for h in holdings)
        
        # Top and bottom performers
        holdings_sorted = sorted(holdings, key=lambda x: x.unrealized_gain_loss_percent, reverse=True)
        top_performers = holdings_sorted[:3]
        bottom_performers = holdings_sorted[-3:] if len(holdings_sorted) > 3 else []
        
        return {
            "holdings": holdings,
            "total_count": len(holdings),
            "total_value": total_value,
            "total_gain_loss": total_gain_loss,
            "top_performers": top_performers,
            "bottom_performers": bottom_performers
        }
    
    async def create_order(self, user_id: str, request: OrderCreateRequest) -> Order:
        """Create a new investment order."""
        await asyncio.sleep(0.2)
        
        # Verify portfolio ownership
        portfolio = await self.get_portfolio(user_id, request.portfolio_id)
        
        # Get current market data
        market_data = self.market_data.get(request.symbol)
        if not market_data:
            raise ValidationError(f"Symbol {request.symbol} not found")
        
        # Calculate estimated cost
        if request.order_type == OrderType.MARKET:
            estimated_price = market_data.current_price
        elif request.price:
            estimated_price = request.price
        else:
            raise ValidationError("Price required for limit orders")
        
        estimated_cost = request.quantity * estimated_price
        
        # Validate sufficient funds for buy orders
        if request.order_side == OrderSide.BUY:
            if portfolio.cash_balance < estimated_cost:
                raise BusinessLogicError("Insufficient cash balance")
        
        # Validate sufficient holdings for sell orders
        if request.order_side == OrderSide.SELL:
            holdings = self.holdings.get(request.portfolio_id, [])
            existing_holding = next((h for h in holdings if h.symbol == request.symbol), None)
            if not existing_holding or existing_holding.quantity < request.quantity:
                raise BusinessLogicError("Insufficient shares to sell")
        
        # Create order
        order = Order(
            order_id=f"order_{uuid.uuid4().hex[:8]}",
            portfolio_id=request.portfolio_id,
            user_id=user_id,
            symbol=request.symbol,
            asset_type=market_data.asset_type,
            order_type=request.order_type,
            order_side=request.order_side,
            quantity=request.quantity,
            price=request.price,
            stop_price=request.stop_price,
            estimated_cost=estimated_cost,
            status=OrderStatus.PENDING,
            expires_at=datetime.utcnow() + timedelta(days=90) if request.order_type != OrderType.MARKET else None,
            commission=self._calculate_commission(estimated_cost),
            notes=request.notes
        )
        
        self.orders[order.order_id] = order
        
        # Simulate order processing
        asyncio.create_task(self._process_order(order.order_id))
        
        return order
    
    async def get_orders(self, user_id: str, portfolio_id: Optional[str] = None,
                        status: Optional[OrderStatus] = None,
                        pagination: Optional[PaginationRequest] = None) -> Dict[str, Any]:
        """Get investment orders."""
        await asyncio.sleep(0.1)
        
        # Filter orders by user and optionally by portfolio
        user_orders = [o for o in self.orders.values() if o.user_id == user_id]
        
        if portfolio_id:
            await self.get_portfolio(user_id, portfolio_id)  # Verify ownership
            user_orders = [o for o in user_orders if o.portfolio_id == portfolio_id]
        
        if status:
            user_orders = [o for o in user_orders if o.status == status]
        
        # Sort by created date descending
        user_orders.sort(key=lambda x: x.created_at, reverse=True)
        
        # Apply pagination if provided
        total_count = len(user_orders)
        if pagination:
            start_idx = (pagination.page - 1) * pagination.page_size
            end_idx = start_idx + pagination.page_size
            user_orders = user_orders[start_idx:end_idx]
        
        # Calculate counts
        pending_orders = len([o for o in self.orders.values() 
                             if o.user_id == user_id and o.status == OrderStatus.PENDING])
        filled_orders = len([o for o in self.orders.values() 
                            if o.user_id == user_id and o.status == OrderStatus.FILLED])
        
        return {
            "orders": user_orders,
            "total_count": total_count,
            "pending_orders": pending_orders,
            "filled_orders": filled_orders
        }
    
    async def get_order(self, user_id: str, order_id: str) -> Order:
        """Get a specific order."""
        await asyncio.sleep(0.1)
        
        order = self.orders.get(order_id)
        if not order or order.user_id != user_id:
            raise NotFoundError("Order not found")
        
        return order
    
    async def cancel_order(self, user_id: str, order_id: str) -> Order:
        """Cancel an order."""
        await asyncio.sleep(0.1)
        
        order = await self.get_order(user_id, order_id)
        
        if order.status not in [OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED]:
            raise BusinessLogicError("Order cannot be cancelled in current status")
        
        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.utcnow()
        
        return order
    
    async def get_market_data(self, symbols: List[str]) -> List[MarketData]:
        """Get market data for symbols."""
        await asyncio.sleep(0.1)
        
        market_data = []
        for symbol in symbols:
            data = self.market_data.get(symbol.upper())
            if data:
                market_data.append(data)
        
        return market_data
    
    async def search_assets(self, query: str, asset_types: Optional[List[AssetType]] = None,
                           limit: int = 20) -> List[MarketData]:
        """Search for investment assets."""
        await asyncio.sleep(0.1)
        
        query_upper = query.upper()
        results = []
        
        for market_data in self.market_data.values():
            if (query_upper in market_data.symbol or 
                query_upper in market_data.name.upper()):
                
                if not asset_types or market_data.asset_type in asset_types:
                    results.append(market_data)
        
        # Sort by relevance (exact symbol match first)
        results.sort(key=lambda x: (x.symbol != query_upper, x.symbol))
        
        return results[:limit]
    
    async def create_watchlist(self, user_id: str, request: WatchlistCreateRequest) -> Watchlist:
        """Create a new watchlist."""
        await asyncio.sleep(0.1)
        
        # Check if user already has a watchlist with this name
        user_watchlists = self.watchlists.get(user_id, [])
        if any(w.name.lower() == request.name.lower() for w in user_watchlists):
            raise ValidationError("Watchlist with this name already exists")
        
        watchlist = Watchlist(
            watchlist_id=f"watch_{uuid.uuid4().hex[:8]}",
            user_id=user_id,
            name=request.name,
            description=request.description,
            symbols=request.symbols,
            is_default=len(user_watchlists) == 0,  # First watchlist is default
            color=request.color
        )
        
        if user_id not in self.watchlists:
            self.watchlists[user_id] = []
        self.watchlists[user_id].append(watchlist)
        
        return watchlist
    
    async def get_watchlists(self, user_id: str) -> List[Watchlist]:
        """Get watchlists for a user."""
        await asyncio.sleep(0.1)
        
        watchlists = self.watchlists.get(user_id, [])
        watchlists.sort(key=lambda x: (not x.is_default, x.created_at))
        
        return watchlists
    
    async def get_watchlist(self, user_id: str, watchlist_id: str) -> Watchlist:
        """Get a specific watchlist."""
        await asyncio.sleep(0.1)
        
        user_watchlists = self.watchlists.get(user_id, [])
        watchlist = next((w for w in user_watchlists if w.watchlist_id == watchlist_id), None)
        
        if not watchlist:
            raise NotFoundError("Watchlist not found")
        
        return watchlist
    
    async def update_watchlist(self, user_id: str, watchlist_id: str,
                              request: WatchlistUpdateRequest) -> Watchlist:
        """Update watchlist settings."""
        await asyncio.sleep(0.1)
        
        watchlist = await self.get_watchlist(user_id, watchlist_id)
        
        if request.name is not None:
            # Check for name conflicts
            user_watchlists = self.watchlists.get(user_id, [])
            if any(w.name.lower() == request.name.lower() and w.watchlist_id != watchlist_id 
                   for w in user_watchlists):
                raise ValidationError("Watchlist with this name already exists")
            watchlist.name = request.name
        
        if request.description is not None:
            watchlist.description = request.description
        if request.color is not None:
            watchlist.color = request.color
        
        watchlist.updated_at = datetime.utcnow()
        
        return watchlist
    
    async def add_to_watchlist(self, user_id: str, watchlist_id: str, symbol: str) -> Watchlist:
        """Add symbol to watchlist."""
        await asyncio.sleep(0.1)
        
        watchlist = await self.get_watchlist(user_id, watchlist_id)
        
        symbol_upper = symbol.upper()
        if symbol_upper not in watchlist.symbols:
            # Verify symbol exists
            if symbol_upper not in self.market_data:
                raise ValidationError(f"Symbol {symbol_upper} not found")
            
            watchlist.symbols.append(symbol_upper)
            watchlist.updated_at = datetime.utcnow()
        
        return watchlist
    
    async def remove_from_watchlist(self, user_id: str, watchlist_id: str, symbol: str) -> Watchlist:
        """Remove symbol from watchlist."""
        await asyncio.sleep(0.1)
        
        watchlist = await self.get_watchlist(user_id, watchlist_id)
        
        symbol_upper = symbol.upper()
        if symbol_upper in watchlist.symbols:
            watchlist.symbols.remove(symbol_upper)
            watchlist.updated_at = datetime.utcnow()
        
        return watchlist
    
    async def get_portfolio_analysis(self, user_id: str, request: PortfolioAnalysisRequest) -> Dict[str, Any]:
        """Get comprehensive portfolio analysis."""
        await asyncio.sleep(0.3)
        
        portfolio = await self.get_portfolio(user_id, request.portfolio_id)
        
        # Mock sophisticated analysis
        return {
            "portfolio_id": portfolio.portfolio_id,
            "analysis_date": datetime.utcnow(),
            "total_return": portfolio.total_gain_loss_percent,
            "annual_return": Decimal("12.5"),
            "volatility": Decimal("18.2"),
            "sharpe_ratio": Decimal("0.85"),
            "beta": Decimal("1.15"),
            "max_drawdown": Decimal("-8.5"),
            "correlation_to_benchmark": Decimal("0.92"),
            "asset_allocation": portfolio.asset_allocation,
            "performance_attribution": {
                "AAPL": Decimal("35.2"),
                "SPY": Decimal("28.8"),
                "cash": Decimal("0.0")
            },
            "risk_metrics": {
                "value_at_risk_95": Decimal("1250.00"),
                "expected_shortfall": Decimal("1850.00"),
                "sortino_ratio": Decimal("1.12")
            }
        }
    
    async def analyze_rebalancing(self, user_id: str, request: RebalanceRequest) -> Dict[str, Any]:
        """Analyze portfolio rebalancing requirements."""
        await asyncio.sleep(0.2)
        
        portfolio = await self.get_portfolio(user_id, request.portfolio_id)
        holdings = self.holdings.get(request.portfolio_id, [])
        
        # Calculate current allocation
        total_value = sum(h.market_value for h in holdings)
        current_allocation = {}
        for holding in holdings:
            allocation_pct = (holding.market_value / total_value * 100) if total_value > 0 else Decimal("0")
            current_allocation[holding.symbol] = allocation_pct
        
        # Calculate rebalancing actions
        rebalancing_actions = []
        estimated_trades = []
        
        for symbol, target_pct in request.target_allocation.items():
            current_pct = current_allocation.get(symbol, Decimal("0"))
            diff = target_pct - current_pct
            
            if abs(diff) > portfolio.rebalancing_threshold:
                action = "BUY" if diff > 0 else "SELL"
                target_value = (target_pct / 100) * total_value
                current_value = current_allocation.get(symbol, Decimal("0")) / 100 * total_value
                trade_value = abs(target_value - current_value)
                
                rebalancing_actions.append({
                    "symbol": symbol,
                    "action": action,
                    "current_allocation": current_pct,
                    "target_allocation": target_pct,
                    "difference": diff,
                    "trade_value": trade_value
                })
                
                if symbol in self.market_data:
                    shares = trade_value / self.market_data[symbol].current_price
                    estimated_trades.append({
                        "symbol": symbol,
                        "side": action.lower(),
                        "quantity": shares,
                        "estimated_price": self.market_data[symbol].current_price,
                        "estimated_value": trade_value
                    })
        
        estimated_costs = sum(trade["estimated_value"] for trade in estimated_trades) * Decimal("0.001")  # 0.1% commission
        
        return {
            "portfolio_id": request.portfolio_id,
            "current_allocation": current_allocation,
            "target_allocation": request.target_allocation,
            "rebalancing_actions": rebalancing_actions,
            "estimated_trades": estimated_trades,
            "estimated_costs": estimated_costs,
            "tax_implications": {
                "estimated_capital_gains": Decimal("150.00"),
                "estimated_tax_liability": Decimal("37.50")
            }
        }
    
    async def get_dividend_history(self, user_id: str, portfolio_id: str,
                                  start_date: Optional[date] = None,
                                  end_date: Optional[date] = None) -> Dict[str, Any]:
        """Get dividend payment history."""
        await asyncio.sleep(0.1)
        
        # Verify portfolio ownership
        await self.get_portfolio(user_id, portfolio_id)
        
        dividends = self.dividend_payments.get(portfolio_id, [])
        
        # Apply date filters
        if start_date:
            dividends = [d for d in dividends if d.payment_date >= start_date]
        if end_date:
            dividends = [d for d in dividends if d.payment_date <= end_date]
        
        # Sort by payment date descending
        dividends.sort(key=lambda x: x.payment_date, reverse=True)
        
        total_amount = sum(d.net_amount for d in dividends)
        annual_yield = Decimal("2.5")  # Mock calculation
        
        return {
            "dividends": dividends,
            "total_count": len(dividends),
            "total_amount": total_amount,
            "annual_yield": annual_yield
        }
    
    async def get_investment_summary(self, user_id: str) -> Dict[str, Any]:
        """Get investment summary across all portfolios."""
        await asyncio.sleep(0.2)
        
        user_portfolios = [p for p in self.portfolios.values() if p.user_id == user_id]
        
        # Calculate totals
        total_value = sum(p.total_value for p in user_portfolios)
        total_gain_loss = sum(p.total_gain_loss for p in user_portfolios)
        total_gain_loss_percent = (total_gain_loss / (total_value - total_gain_loss) * 100) if total_value > total_gain_loss else Decimal("0")
        day_change = sum(p.day_change for p in user_portfolios)
        day_change_percent = (day_change / (total_value - day_change) * 100) if total_value > day_change else Decimal("0")
        cash_available = sum(p.cash_balance for p in user_portfolios)
        
        # Get pending orders count
        pending_orders = len([o for o in self.orders.values() 
                             if o.user_id == user_id and o.status == OrderStatus.PENDING])
        
        # Mock recent dividends
        recent_dividend_amount = Decimal("85.50")
        
        # Top holdings across all portfolios
        all_holdings = []
        for portfolio_id in [p.portfolio_id for p in user_portfolios]:
            all_holdings.extend(self.holdings.get(portfolio_id, []))
        
        all_holdings.sort(key=lambda x: x.market_value, reverse=True)
        top_holdings = [
            {
                "symbol": h.symbol,
                "market_value": h.market_value,
                "gain_loss_percent": h.unrealized_gain_loss_percent
            } 
            for h in all_holdings[:5]
        ]
        
        return {
            "total_portfolios": len(user_portfolios),
            "total_value": total_value,
            "total_gain_loss": total_gain_loss,
            "total_gain_loss_percent": total_gain_loss_percent,
            "day_change": day_change,
            "day_change_percent": day_change_percent,
            "cash_available": cash_available,
            "pending_orders": pending_orders,
            "recent_dividend_amount": recent_dividend_amount,
            "top_holdings": top_holdings
        }
    
    async def get_investment_research(self, symbol: str) -> Dict[str, Any]:
        """Get investment research and analysis for a symbol."""
        await asyncio.sleep(0.3)
        
        market_data = self.market_data.get(symbol.upper())
        if not market_data:
            raise NotFoundError(f"Symbol {symbol} not found")
        
        # Mock comprehensive research data
        return {
            "symbol": symbol.upper(),
            "research_data": {
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "employees": 154000,
                "headquarters": "Cupertino, CA",
                "founded": 1976,
                "description": "Technology company focusing on consumer electronics and services"
            },
            "analyst_ratings": {
                "consensus_rating": "BUY",
                "strong_buy": 8,
                "buy": 12,
                "hold": 5,
                "sell": 1,
                "strong_sell": 0,
                "average_price_target": Decimal("195.50"),
                "high_price_target": Decimal("220.00"),
                "low_price_target": Decimal("170.00")
            },
            "financial_metrics": {
                "revenue_ttm": Decimal("394.3"),  # Billions
                "net_income_ttm": Decimal("97.0"),
                "free_cash_flow": Decimal("111.4"),
                "debt_to_equity": Decimal("1.73"),
                "roe": Decimal("160.5"),
                "profit_margin": Decimal("24.6")
            },
            "news_sentiment": {
                "sentiment_score": 0.65,
                "positive_articles": 12,
                "neutral_articles": 8,
                "negative_articles": 3,
                "recent_news_count": 23
            },
            "technical_indicators": {
                "rsi": Decimal("58.2"),
                "macd": Decimal("2.15"),
                "moving_avg_50": Decimal("172.30"),
                "moving_avg_200": Decimal("165.80"),
                "bollinger_upper": Decimal("180.25"),
                "bollinger_lower": Decimal("170.75")
            }
        }
    
    def _calculate_commission(self, trade_value: Decimal) -> Decimal:
        """Calculate trading commission."""
        # Mock commission structure
        if trade_value <= Decimal("1000"):
            return Decimal("0")  # Free for small trades
        else:
            return min(Decimal("9.95"), trade_value * Decimal("0.001"))  # Max $9.95 or 0.1%
    
    async def _process_order(self, order_id: str):
        """Simulate order processing and execution."""
        await asyncio.sleep(random.uniform(1, 5))  # Simulate processing delay
        
        order = self.orders.get(order_id)
        if not order or order.status != OrderStatus.PENDING:
            return
        
        # Simulate execution (90% success rate)
        if random.random() > 0.1:
            # Successful execution
            market_data = self.market_data.get(order.symbol)
            if market_data:
                # Simulate price execution with slippage
                if order.order_type == OrderType.MARKET:
                    fill_price = market_data.current_price * (1 + random.uniform(-0.005, 0.005))
                else:
                    fill_price = order.price or market_data.current_price
                
                order.status = OrderStatus.FILLED
                order.filled_quantity = order.quantity
                order.filled_price = fill_price
                order.total_cost = order.quantity * fill_price + order.commission
                order.executed_at = datetime.utcnow()
                
                # Update portfolio holdings
                await self._update_holdings_after_execution(order)
        else:
            # Order rejection
            order.status = OrderStatus.REJECTED
            order.updated_at = datetime.utcnow()
    
    async def _update_holdings_after_execution(self, order: Order):
        """Update portfolio holdings after order execution."""
        portfolio_holdings = self.holdings.get(order.portfolio_id, [])
        
        if order.order_side == OrderSide.BUY:
            # Find existing holding or create new one
            existing_holding = next((h for h in portfolio_holdings if h.symbol == order.symbol), None)
            
            if existing_holding:
                # Update existing holding
                total_shares = existing_holding.quantity + order.filled_quantity
                total_cost = existing_holding.total_cost + order.total_cost
                existing_holding.quantity = total_shares
                existing_holding.average_cost = total_cost / total_shares
                existing_holding.total_cost = total_cost
            else:
                # Create new holding
                market_data = self.market_data.get(order.symbol)
                new_holding = Holding(
                    holding_id=f"hold_{uuid.uuid4().hex[:8]}",
                    portfolio_id=order.portfolio_id,
                    symbol=order.symbol,
                    asset_type=order.asset_type,
                    quantity=order.filled_quantity,
                    average_cost=order.filled_price,
                    total_cost=order.total_cost,
                    current_price=market_data.current_price,
                    market_value=order.filled_quantity * market_data.current_price,
                    unrealized_gain_loss=Decimal("0"),
                    unrealized_gain_loss_percent=Decimal("0"),
                    day_change=Decimal("0"),
                    day_change_percent=Decimal("0")
                )
                portfolio_holdings.append(new_holding)
                
        elif order.order_side == OrderSide.SELL:
            # Update existing holding
            existing_holding = next((h for h in portfolio_holdings if h.symbol == order.symbol), None)
            if existing_holding:
                existing_holding.quantity -= order.filled_quantity
                if existing_holding.quantity <= 0:
                    portfolio_holdings.remove(existing_holding)
                else:
                    # Recalculate market value
                    market_data = self.market_data.get(order.symbol)
                    if market_data:
                        existing_holding.market_value = existing_holding.quantity * market_data.current_price
        
        # Update portfolio cash balance
        portfolio = self.portfolios.get(order.portfolio_id)
        if portfolio:
            if order.order_side == OrderSide.BUY:
                portfolio.cash_balance -= order.total_cost
            else:
                portfolio.cash_balance += order.total_cost - order.commission
    
    async def get_service_health(self) -> Dict[str, Any]:
        """Get investment service health status."""
        return {
            "status": "healthy",
            "total_portfolios": len(self.portfolios),
            "total_orders": len(self.orders),
            "total_watchlists": sum(len(watchlists) for watchlists in self.watchlists.values()),
            "market_data_symbols": len(self.market_data),
            "timestamp": datetime.utcnow()
        }
