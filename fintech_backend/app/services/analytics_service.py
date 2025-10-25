from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
import uuid
import random
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func, or_
from sqlalchemy.orm import selectinload

from ..models.analytics import (
    AnalyticsRequest, BudgetRequest, SpendingAnalysisRequest, FinancialGoalRequest,
    SpendingByCategory, MonthlySpending, SpendingTrend, BudgetProfile, BudgetSummary,
    FinancialInsight, CashFlowAnalysis, FinancialHealthScore, ExpenseReport,
    FinancialGoalProfile, FinancialAlert,
    BudgetDB, FinancialGoalDB, FinancialAlertDB, TransactionAnalyticsDB,
    AnalyticsPeriod, TransactionCategory, BudgetStatus, TrendDirection, AlertType
)
from ..models.transaction import Transaction, TransactionType, TransactionStatus, MerchantCategory
from ..core.exceptions import NotFoundError, ValidationError, BusinessLogicError

class AnalyticsService:
    def __init__(self, db_session: Session):
        """Initialize analytics service with database session"""
        self.db = db_session
    
    async def _sync_transaction_to_analytics(self, transaction: Transaction) -> TransactionAnalyticsDB:
        """Convert a regular transaction to analytics format"""
        
        # Map merchant categories to transaction categories
        category_mapping = {
            MerchantCategory.GROCERIES: TransactionCategory.GROCERIES,
            MerchantCategory.RESTAURANTS: TransactionCategory.FOOD_DINING,
            MerchantCategory.GAS_STATIONS: TransactionCategory.FUEL,
            MerchantCategory.RETAIL: TransactionCategory.SHOPPING,
            MerchantCategory.ENTERTAINMENT: TransactionCategory.ENTERTAINMENT,
            MerchantCategory.TRAVEL: TransactionCategory.TRAVEL,
            MerchantCategory.HEALTHCARE: TransactionCategory.HEALTHCARE,
            MerchantCategory.UTILITIES: TransactionCategory.BILLS_UTILITIES,
            MerchantCategory.EDUCATION: TransactionCategory.EDUCATION,
            MerchantCategory.AUTOMOTIVE: TransactionCategory.TRANSPORTATION,
            MerchantCategory.ONLINE_SERVICES: TransactionCategory.OTHER,
            MerchantCategory.SUBSCRIPTION: TransactionCategory.OTHER,
            MerchantCategory.TRANSFER: TransactionCategory.TRANSFERS,
            MerchantCategory.INVESTMENT_TRADE: TransactionCategory.INVESTMENTS,
        }
        
        analytics_category = category_mapping.get(
            MerchantCategory(transaction.merchant_category) if isinstance(transaction.merchant_category, str) else transaction.merchant_category,
            TransactionCategory.OTHER
        )
        
        # Determine if it's income based on transaction type and direction
        income_types = [TransactionType.SALARY, TransactionType.DEPOSIT, 
                       TransactionType.INTEREST, TransactionType.DIVIDEND, 
                       TransactionType.REFUND]
        is_income = (transaction.transaction_type in income_types or 
                    transaction.direction == "inbound" or 
                    transaction.amount > 0)
        
        # Get transaction date as date object
        trans_date = transaction.transaction_date
        if isinstance(trans_date, datetime):
            trans_date = trans_date.date()
        
        return TransactionAnalyticsDB(
            id=f"analytics_{transaction.transaction_id}",
            user_id=transaction.user_id,
            transaction_id=transaction.transaction_id,
            amount=abs(transaction.amount),
            category=analytics_category,
            merchant=transaction.merchant_name,
            description=transaction.description,
            transaction_date=trans_date,
            currency=transaction.currency,
            is_income=is_income,
            created_at=transaction.created_at if hasattr(transaction, 'created_at') else datetime.utcnow()
        )
    
    async def _get_user_transactions(
        self, 
        user_id: str, 
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        include_income: bool = True
    ) -> List[TransactionAnalyticsDB]:
        """Get user transactions from database and convert to analytics format"""
        
        # Query transactions from database
        query = select(Transaction).where(Transaction.user_id == user_id)
        
        # Apply date filters
        if start_date:
            query = query.where(Transaction.transaction_date >= start_date)
        if end_date:
            query = query.where(Transaction.transaction_date <= end_date)
        
        result = await self.db.execute(query)
        transactions = result.scalars().all()
        
        # Convert to analytics format
        analytics_transactions = []
        for transaction in transactions:
            try:
                analytics_trans = await self._sync_transaction_to_analytics(transaction)
                if include_income or not analytics_trans.is_income:
                    analytics_transactions.append(analytics_trans)
            except Exception as e:
                # Log error but continue processing other transactions
                print(f"Error converting transaction {transaction.transaction_id}: {e}")
                continue
        
        return analytics_transactions
    
    async def get_spending_analysis(
        self, 
        user_id: str, 
        request: SpendingAnalysisRequest
    ) -> List[SpendingByCategory]:
        """Get spending analysis by category from actual database data"""
        
        # Get user transactions (expenses only)
        user_transactions = await self._get_user_transactions(
            user_id,
            start_date=request.start_date,
            end_date=request.end_date,
            include_income=False
        )
        
        if not user_transactions:
            return []
        
        # Group by category
        category_spending = {}
        for transaction in user_transactions:
            category = transaction.category
            if category not in category_spending:
                category_spending[category] = {
                    'amount': Decimal('0'),
                    'count': 0,
                    'transactions': []
                }
            
            category_spending[category]['amount'] += abs(transaction.amount)
            category_spending[category]['count'] += 1
            category_spending[category]['transactions'].append(transaction)
        
        # Calculate totals
        total_spending = sum(data['amount'] for data in category_spending.values())
        
        # Build response
        spending_by_category = []
        for category, data in category_spending.items():
            amount = data['amount']
            count = data['count']
            percentage = float(amount / total_spending * 100) if total_spending > 0 else 0
            average_transaction = amount / count if count > 0 else Decimal('0')
            
            # Determine trend (comparing to previous period)
            trend = await self._calculate_category_trend(
                user_id, category, request.start_date, request.end_date
            )
            
            spending_by_category.append(SpendingByCategory(
                category=category,
                amount=amount,
                percentage=round(percentage, 2),
                transaction_count=count,
                average_transaction=average_transaction,
                trend=trend
            ))
        
        # Sort by amount descending
        spending_by_category.sort(key=lambda x: x.amount, reverse=True)
        
        return spending_by_category
    
    async def _calculate_category_trend(
        self, 
        user_id: str, 
        category: TransactionCategory,
        start_date: Optional[date],
        end_date: Optional[date]
    ) -> TrendDirection:
        """Calculate spending trend for a category"""
        
        if not start_date or not end_date:
            return TrendDirection.STABLE
        
        # Calculate period length
        period_days = (end_date - start_date).days
        
        # Get previous period data
        previous_start = start_date - timedelta(days=period_days)
        previous_end = start_date - timedelta(days=1)
        
        # Get current period spending
        current_transactions = await self._get_user_transactions(
            user_id, start_date, end_date, include_income=False
        )
        current_spending = sum(
            abs(t.amount) for t in current_transactions if t.category == category
        )
        
        # Get previous period spending
        previous_transactions = await self._get_user_transactions(
            user_id, previous_start, previous_end, include_income=False
        )
        previous_spending = sum(
            abs(t.amount) for t in previous_transactions if t.category == category
        )
        
        # Determine trend
        if previous_spending == 0:
            return TrendDirection.STABLE if current_spending == 0 else TrendDirection.INCREASING
        
        change_percent = ((current_spending - previous_spending) / previous_spending) * 100
        
        if change_percent > 10:
            return TrendDirection.INCREASING
        elif change_percent < -10:
            return TrendDirection.DECREASING
        else:
            return TrendDirection.STABLE
    
    async def get_cash_flow_analysis(
        self, 
        user_id: str, 
        request: AnalyticsRequest
    ) -> CashFlowAnalysis:
        """Get cash flow analysis for a period from actual database data"""
        
        # Get all user transactions (income and expenses)
        user_transactions = await self._get_user_transactions(
            user_id,
            start_date=request.start_date,
            end_date=request.end_date,
            include_income=True
        )
        
        # Separate income and expenses
        income_transactions = [t for t in user_transactions if t.is_income]
        expense_transactions = [t for t in user_transactions if not t.is_income]
        
        # Calculate totals
        total_income = sum(t.amount for t in income_transactions)
        total_expenses = sum(abs(t.amount) for t in expense_transactions)
        net_cash_flow = total_income - total_expenses
        
        # Group income sources
        income_sources = {}
        for transaction in income_transactions:
            source = transaction.merchant or "Other Income"
            income_sources[source] = income_sources.get(source, Decimal('0')) + transaction.amount
        
        # Group expense categories
        expense_categories = {}
        for transaction in expense_transactions:
            category = transaction.category.value
            expense_categories[category] = expense_categories.get(category, Decimal('0')) + abs(transaction.amount)
        
        # Determine cash flow trend
        if total_income == 0:
            cash_flow_trend = TrendDirection.STABLE
        elif net_cash_flow > total_income * Decimal('0.1'):
            cash_flow_trend = TrendDirection.INCREASING
        elif net_cash_flow < -total_income * Decimal('0.1'):
            cash_flow_trend = TrendDirection.DECREASING
        else:
            cash_flow_trend = TrendDirection.STABLE
        
        period_str = f"{request.start_date or 'Beginning'} to {request.end_date or 'Now'}"
        
        return CashFlowAnalysis(
            period=period_str,
            total_income=total_income,
            total_expenses=total_expenses,
            net_cash_flow=net_cash_flow,
            income_sources=income_sources,
            expense_categories=expense_categories,
            cash_flow_trend=cash_flow_trend
        )
    
    async def create_budget(self, user_id: str, request: BudgetRequest) -> BudgetProfile:
        """Create a new budget in database"""
        budget_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        budget = BudgetDB(
            id=budget_id,
            user_id=user_id,
            name=request.name,
            category=request.category,
            amount=request.amount,
            period=request.period,
            start_date=request.start_date,
            end_date=request.end_date,
            currency=request.currency,
            is_active=request.is_active,
            created_at=now,
            updated_at=now
        )
        
        # Save to database (assuming you have a Budget ORM model)
        # self.db.add(budget)
        # await self.db.commit()
        
        # Calculate current spending for this budget
        spent_amount = await self._calculate_budget_spending(user_id, budget)
        
        return self._build_budget_profile(budget, spent_amount)
    
    async def get_user_budgets(self, user_id: str) -> List[BudgetProfile]:
        """Get all budgets for a user from database"""
        
        # Query budgets from database
        # query = select(Budget).where(Budget.user_id == user_id)
        # result = await self.db.execute(query)
        # user_budgets = result.scalars().all()
        
        # For now, return empty list since we need the Budget ORM model
        # You'll need to implement this once you have the Budget table
        user_budgets = []
        
        budget_profiles = []
        for budget in user_budgets:
            spent_amount = await self._calculate_budget_spending(user_id, budget)
            profile = self._build_budget_profile(budget, spent_amount)
            budget_profiles.append(profile)
        
        return budget_profiles
    
    async def get_budget_summary(self, user_id: str) -> BudgetSummary:
        """Get budget summary for user from database"""
        
        # Get user budgets
        user_budgets = await self.get_user_budgets(user_id)
        
        if not user_budgets:
            return BudgetSummary(
                total_budgets=0,
                active_budgets=0,
                total_budgeted=Decimal('0'),
                total_spent=Decimal('0'),
                total_remaining=Decimal('0'),
                overall_percentage_used=0,
                budgets_over_limit=0,
                budgets_on_track=0,
                budgets_under_budget=0
            )
        
        active_budgets = [b for b in user_budgets if b.is_active]
        total_budgets = len(user_budgets)
        active_count = len(active_budgets)
        total_budgeted = sum(b.budgeted_amount for b in active_budgets)
        total_spent = sum(b.spent_amount for b in active_budgets)
        
        budgets_over_limit = 0
        budgets_on_track = 0
        budgets_under_budget = 0
        
        for budget in active_budgets:
            if budget.percentage_used > 100:
                budgets_over_limit += 1
            elif budget.percentage_used > 80:
                budgets_on_track += 1
            else:
                budgets_under_budget += 1
        
        total_remaining = total_budgeted - total_spent
        overall_percentage_used = float(total_spent / total_budgeted * 100) if total_budgeted > 0 else 0
        
        return BudgetSummary(
            total_budgets=total_budgets,
            active_budgets=active_count,
            total_budgeted=total_budgeted,
            total_spent=total_spent,
            total_remaining=total_remaining,
            overall_percentage_used=round(overall_percentage_used, 2),
            budgets_over_limit=budgets_over_limit,
            budgets_on_track=budgets_on_track,
            budgets_under_budget=budgets_under_budget
        )
    
    async def create_financial_goal(
        self, 
        user_id: str, 
        request: FinancialGoalRequest
    ) -> FinancialGoalProfile:
        """Create a new financial goal in database"""
        goal_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        goal = FinancialGoalDB(
            id=goal_id,
            user_id=user_id,
            name=request.name,
            target_amount=request.target_amount,
            current_amount=Decimal('0'),
            target_date=request.target_date,
            category=request.category,
            currency=request.currency,
            description=request.description,
            is_completed=False,
            created_at=now,
            updated_at=now
        )
        
        # Save to database (assuming you have a FinancialGoal ORM model)
        # self.db.add(goal)
        # await self.db.commit()
        
        return self._build_financial_goal_profile(goal)
    
    async def get_user_financial_goals(self, user_id: str) -> List[FinancialGoalProfile]:
        """Get all financial goals for a user from database"""
        
        # Query goals from database
        # query = select(FinancialGoal).where(FinancialGoal.user_id == user_id)
        # result = await self.db.execute(query)
        # user_goals = result.scalars().all()
        
        # For now, return empty list
        user_goals = []
        
        return [self._build_financial_goal_profile(goal) for goal in user_goals]
    
    async def get_financial_health_score(self, user_id: str) -> FinancialHealthScore:
        """Calculate financial health score from actual user data"""
        
        # Get user data from database
        user_transactions = await self._get_user_transactions(
            user_id,
            start_date=date.today() - timedelta(days=90),
            include_income=True
        )
        user_budgets = await self.get_user_budgets(user_id)
        user_goals = await self.get_user_financial_goals(user_id)
        
        # Calculate component scores
        spending_score = await self._calculate_spending_score(user_transactions, user_budgets)
        savings_score = await self._calculate_savings_score(user_goals, user_transactions)
        budget_adherence_score = await self._calculate_budget_adherence_score(user_id, user_budgets)
        debt_management_score = 75  # Default score (implement based on debt data)
        emergency_fund_score = await self._calculate_emergency_fund_score(user_goals)
        
        # Calculate overall score (weighted average)
        overall_score = int(
            spending_score * 0.25 +
            savings_score * 0.25 +
            budget_adherence_score * 0.20 +
            debt_management_score * 0.15 +
            emergency_fund_score * 0.15
        )
        
        # Generate recommendations
        recommendations = []
        if spending_score < 70:
            recommendations.append("Consider reducing discretionary spending to improve your financial health")
        if savings_score < 60:
            recommendations.append("Increase your savings rate to build financial security")
        if budget_adherence_score < 70:
            recommendations.append("Stick to your budgets to better control your finances")
        if emergency_fund_score < 50:
            recommendations.append("Build an emergency fund covering 3-6 months of expenses")
        
        if not recommendations:
            recommendations.append("Great job! Keep maintaining your excellent financial habits")
        
        score_breakdown = {
            "spending_efficiency": spending_score,
            "savings_rate": savings_score,
            "budget_discipline": budget_adherence_score,
            "debt_management": debt_management_score,
            "emergency_preparedness": emergency_fund_score
        }
        
        return FinancialHealthScore(
            overall_score=overall_score,
            spending_score=spending_score,
            savings_score=savings_score,
            budget_adherence_score=budget_adherence_score,
            debt_management_score=debt_management_score,
            emergency_fund_score=emergency_fund_score,
            recommendations=recommendations,
            score_breakdown=score_breakdown,
            last_calculated=datetime.utcnow()
        )
    
    async def get_financial_insights(self, user_id: str) -> List[FinancialInsight]:
        """Generate financial insights for user from actual data"""
        insights = []
        
        # Get recent transactions (last 30 days)
        recent_date = date.today() - timedelta(days=30)
        recent_transactions = await self._get_user_transactions(
            user_id,
            start_date=recent_date,
            include_income=False
        )
        
        if recent_transactions:
            # High spending category insight
            category_spending = {}
            for transaction in recent_transactions:
                category = transaction.category
                category_spending[category] = category_spending.get(category, Decimal('0')) + abs(transaction.amount)
            
            if category_spending:
                top_category = max(category_spending.items(), key=lambda x: x[1])
                total_spending = sum(category_spending.values())
                percentage = float(top_category[1] / total_spending * 100)
                
                insights.append(FinancialInsight(
                    id=str(uuid.uuid4()),
                    title="Top Spending Category",
                    description=f"Your highest spending category this month is {top_category[0].value.replace('_', ' ').title()}, accounting for {percentage:.1f}% of your expenses.",
                    insight_type="spending_pattern",
                    category=top_category[0],
                    amount=top_category[1],
                    percentage=percentage,
                    action_recommended="Consider setting a budget for this category to better control spending",
                    priority="medium",
                    created_at=datetime.utcnow()
                ))
        
        return insights
    
    async def get_user_financial_alerts(self, user_id: str) -> List[FinancialAlert]:
        """Get financial alerts for user from database"""
        
        # Query alerts from database
        # query = select(Alert).where(Alert.user_id == user_id)
        # result = await self.db.execute(query)
        # user_alerts = result.scalars().all()
        
        # For now, return empty list
        user_alerts = []
        
        return [
            FinancialAlert(
                id=alert.id,
                alert_type=alert.alert_type,
                title=alert.title,
                message=alert.message,
                severity=alert.severity,
                category=alert.category,
                amount=alert.amount,
                threshold=alert.threshold,
                is_read=alert.is_read,
                created_at=alert.created_at,
                expires_at=alert.expires_at
            )
            for alert in user_alerts
        ]
    
    # Helper methods
    async def _calculate_budget_spending(self, user_id: str, budget: BudgetDB) -> Decimal:
        """Calculate current spending for a budget from actual transactions"""
        
        # Get transactions for the budget period and category
        user_transactions = await self._get_user_transactions(
            user_id,
            start_date=budget.start_date,
            end_date=budget.end_date,
            include_income=False
        )
        
        # Filter by category
        category_transactions = [
            t for t in user_transactions 
            if t.category == budget.category
        ]
        
        return sum(abs(t.amount) for t in category_transactions)
    
    def _build_budget_profile(self, budget: BudgetDB, spent_amount: Decimal) -> BudgetProfile:
        """Build budget profile from budget DB and spending data"""
        remaining_amount = budget.amount - spent_amount
        percentage_used = float(spent_amount / budget.amount * 100) if budget.amount > 0 else 0
        
        # Determine budget status
        if percentage_used > 100:
            status = BudgetStatus.EXCEEDED
        elif percentage_used > 90:
            status = BudgetStatus.OVER_BUDGET
        elif percentage_used > 70:
            status = BudgetStatus.ON_TRACK
        else:
            status = BudgetStatus.UNDER_BUDGET
        
        # Calculate days remaining
        days_remaining = None
        daily_budget_remaining = None
        if budget.end_date:
            days_remaining = (budget.end_date - date.today()).days
            if days_remaining > 0 and remaining_amount > 0:
                daily_budget_remaining = remaining_amount / days_remaining
        
        return BudgetProfile(
            id=budget.id,
            name=budget.name,
            category=budget.category,
            budgeted_amount=budget.amount,
            spent_amount=spent_amount,
            remaining_amount=remaining_amount,
            percentage_used=round(percentage_used, 2),
            status=status,
            period=budget.period,
            start_date=budget.start_date,
            end_date=budget.end_date,
            currency=budget.currency,
            is_active=budget.is_active,
            days_remaining=days_remaining,
            daily_budget_remaining=daily_budget_remaining,
            created_at=budget.created_at,
            updated_at=budget.updated_at
        )
    
    def _build_financial_goal_profile(self, goal: FinancialGoalDB) -> FinancialGoalProfile:
        """Build financial goal profile from goal DB"""
        remaining_amount = goal.target_amount - goal.current_amount
        progress_percentage = float(goal.current_amount / goal.target_amount * 100) if goal.target_amount > 0 else 0
        
        # Calculate days remaining
        days_remaining = max((goal.target_date - date.today()).days, 0)
        
        # Calculate monthly target
        months_remaining = max(days_remaining / 30, 1)
        monthly_target = remaining_amount / Decimal(str(months_remaining))
        
        # Determine if on track
        total_days = (goal.target_date - goal.created_at.date()).days
        days_elapsed = total_days - days_remaining
        expected_progress = (days_elapsed / total_days * 100) if total_days > 0 else 0
        on_track = progress_percentage >= expected_progress * 0.8
        
        return FinancialGoalProfile(
            id=goal.id,
            name=goal.name,
            target_amount=goal.target_amount,
            current_amount=goal.current_amount,
            remaining_amount=remaining_amount,
            target_date=goal.target_date,
            days_remaining=days_remaining,
            progress_percentage=round(progress_percentage, 2),
            monthly_target=monthly_target,
            on_track=on_track,
            category=goal.category,
            currency=goal.currency,
            description=goal.description,
            created_at=goal.created_at,
            updated_at=goal.updated_at
        )
    
    async def _calculate_spending_score(
        self, 
        transactions: List[TransactionAnalyticsDB], 
        budgets: List[BudgetProfile]
    ) -> int:
        """Calculate spending efficiency score"""
        if not transactions:
            return 50
        
        recent_transactions = [
            t for t in transactions 
            if not t.is_income
        ]
        
        if not recent_transactions:
            return 70
        
        total_spending = sum(abs(t.amount) for t in recent_transactions)
        avg_transaction = total_spending / len(recent_transactions)
        
        # Higher scores for lower average transactions
        if avg_transaction < Decimal('50000'):
            base_score = 85
        elif avg_transaction < Decimal('100000'):
            base_score = 75
        else:
            base_score = 65
        
        # Adjust based on budget adherence
        if budgets:
            over_budget_count = sum(1 for b in budgets if b.percentage_used > 100)
            if over_budget_count == 0:
                base_score += 10
            else:
                base_score -= (over_budget_count * 5)
        
        return max(30, min(100, base_score))
    
    async def _calculate_savings_score(
        self, 
        goals: List[FinancialGoalProfile], 
        transactions: List[TransactionAnalyticsDB]
    ) -> int:
        """Calculate savings rate score"""
        if not goals:
            return 40
        
        # Calculate progress on goals
        total_progress = sum(min(g.progress_percentage, 100) for g in goals)
        avg_progress = total_progress / len(goals)
        
        # Calculate savings rate from transactions
        income_transactions = [t for t in transactions if t.is_income]
        savings_transactions = [t for t in transactions if t.category == TransactionCategory.SAVINGS]
        
        if income_transactions:
            total_income = sum(t.amount for t in income_transactions)
            total_savings = sum(abs(t.amount) for t in savings_transactions)
            savings_rate = float(total_savings / total_income * 100) if total_income > 0 else 0
            
            score = int((avg_progress * 0.6) + (min(savings_rate, 30) * 2))
        else:
            score = int(avg_progress * 0.8)
        
        return max(20, min(100, score))
    
    async def _calculate_budget_adherence_score(
        self, 
        user_id: str, 
        budgets: List[BudgetProfile]
    ) -> int:
        """Calculate budget adherence score"""
        if not budgets:
            return 60
        
        adherence_scores = []
        for budget in budgets:
            percentage_used = budget.percentage_used
            
            if percentage_used <= 80:
                adherence_scores.append(100)
            elif percentage_used <= 100:
                adherence_scores.append(80)
            elif percentage_used <= 120:
                adherence_scores.append(60)
            else:
                adherence_scores.append(30)
        
        return int(sum(adherence_scores) / len(adherence_scores))
    
    async def _calculate_emergency_fund_score(self, goals: List[FinancialGoalProfile]) -> int:
        """Calculate emergency fund score"""
        emergency_goals = [
            g for g in goals 
            if 'emergency' in g.name.lower() or g.category == TransactionCategory.SAVINGS
        ]
        
        if not emergency_goals:
            return 20
        
        # Find the largest emergency fund goal
        largest_goal = max(emergency_goals, key=lambda g: g.target_amount)
        progress = largest_goal.progress_percentage
        
        return min(100, int(progress))
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get analytics service health status"""
        total_budgets = len(self.budgets)
        total_goals = len(self.financial_goals)
        total_alerts = len(self.financial_alerts)
        total_transactions = len(self.transactions)
        
        # Calculate processing metrics
        active_budgets = len([b for b in self.budgets.values() if b.is_active])
        unread_alerts = len([a for a in self.financial_alerts.values() if not a.is_read])
        
        return {
            "service": "analytics",
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {
                "total_budgets": total_budgets,
                "active_budgets": active_budgets,
                "total_financial_goals": total_goals,
                "total_alerts": total_alerts,
                "unread_alerts": unread_alerts,
                "total_transactions_analyzed": total_transactions
            },
            "features": {
                "spending_analysis": "active",
                "budget_tracking": "active",
                "financial_health_scoring": "active",
                "insights_generation": "active",
                "cash_flow_analysis": "active"
            },
            "version": "1.0.0"
        }
