from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
import uuid
import random
from decimal import Decimal
from ..models.analytics import (
    AnalyticsRequest, BudgetRequest, SpendingAnalysisRequest, FinancialGoalRequest,
    SpendingByCategory, MonthlySpending, SpendingTrend, BudgetProfile, BudgetSummary,
    FinancialInsight, CashFlowAnalysis, FinancialHealthScore, ExpenseReport,
    FinancialGoalProfile, FinancialAlert,
    BudgetDB, FinancialGoalDB, FinancialAlertDB, TransactionAnalyticsDB,
    AnalyticsPeriod, TransactionCategory, BudgetStatus, TrendDirection, AlertType
)
from ..core.exceptions import NotFoundError, ValidationError, BusinessLogicError

class AnalyticsService:
    def __init__(self):
        # Mock data storage
        self.budgets: Dict[str, BudgetDB] = {}
        self.financial_goals: Dict[str, FinancialGoalDB] = {}
        self.financial_alerts: Dict[str, FinancialAlertDB] = {}
        self.transactions: Dict[str, TransactionAnalyticsDB] = {}
        self._initialize_mock_data()
    
    def _initialize_mock_data(self):
        """Initialize with sample analytics data"""
        user_id = "user_123"
        
        # Sample budgets
        budget_data = [
            {
                "name": "Monthly Groceries",
                "category": TransactionCategory.GROCERIES,
                "amount": Decimal("300000"),  # 300k UGX
                "period": AnalyticsPeriod.MONTHLY,
                "start_date": date(2024, 1, 1),
                "currency": "UGX"
            },
            {
                "name": "Transportation Budget",
                "category": TransactionCategory.TRANSPORTATION,
                "amount": Decimal("150000"),  # 150k UGX
                "period": AnalyticsPeriod.MONTHLY,
                "start_date": date(2024, 1, 1),
                "currency": "UGX"
            },
            {
                "name": "Entertainment",
                "category": TransactionCategory.ENTERTAINMENT,
                "amount": Decimal("100000"),  # 100k UGX
                "period": AnalyticsPeriod.MONTHLY,
                "start_date": date(2024, 1, 1),
                "currency": "UGX"
            }
        ]
        
        for budget_info in budget_data:
            budget_id = str(uuid.uuid4())
            self.budgets[budget_id] = BudgetDB(
                id=budget_id,
                user_id=user_id,
                is_active=True,
                created_at=datetime.utcnow() - timedelta(days=30),
                updated_at=datetime.utcnow(),
                **budget_info
            )
        
        # Sample financial goals
        goal_data = [
            {
                "name": "Emergency Fund",
                "target_amount": Decimal("2000000"),  # 2M UGX
                "current_amount": Decimal("750000"),  # 750k UGX
                "target_date": date(2024, 12, 31),
                "category": TransactionCategory.SAVINGS,
                "currency": "UGX",
                "description": "Build emergency fund for 6 months expenses"
            },
            {
                "name": "New Car",
                "target_amount": Decimal("15000000"),  # 15M UGX
                "current_amount": Decimal("3500000"),  # 3.5M UGX
                "target_date": date(2025, 6, 30),
                "category": TransactionCategory.TRANSPORTATION,
                "currency": "UGX",
                "description": "Save for a reliable car"
            }
        ]
        
        for goal_info in goal_data:
            goal_id = str(uuid.uuid4())
            self.financial_goals[goal_id] = FinancialGoalDB(
                id=goal_id,
                user_id=user_id,
                is_completed=False,
                created_at=datetime.utcnow() - timedelta(days=60),
                updated_at=datetime.utcnow(),
                **goal_info
            )
        
        # Sample financial alerts
        alert_data = [
            {
                "alert_type": AlertType.BUDGET_EXCEEDED,
                "title": "Budget Alert: Entertainment",
                "message": "You've exceeded your entertainment budget by 15% this month.",
                "severity": "warning",
                "category": TransactionCategory.ENTERTAINMENT,
                "amount": Decimal("115000"),
                "threshold": Decimal("100000")
            },
            {
                "alert_type": AlertType.LARGE_TRANSACTION,
                "title": "Large Transaction Detected",
                "message": "A large transaction of UGX 500,000 was detected in your account.",
                "severity": "info",
                "amount": Decimal("500000")
            }
        ]
        
        for alert_info in alert_data:
            alert_id = str(uuid.uuid4())
            self.financial_alerts[alert_id] = FinancialAlertDB(
                id=alert_id,
                user_id=user_id,
                is_read=False,
                created_at=datetime.utcnow() - timedelta(hours=random.randint(1, 48)),
                expires_at=datetime.utcnow() + timedelta(days=7),
                **alert_info
            )
        
        # Sample transactions for analytics
        self._generate_sample_transactions(user_id)
    
    def _generate_sample_transactions(self, user_id: str):
        """Generate sample transaction data for analytics"""
        categories = list(TransactionCategory)
        merchants = [
            "Shoprite", "Game Stores", "Shell", "MTN", "Airtel", "UMEME",
            "Cafe Javas", "KFC", "Uber", "Boda Boda", "Nakumatt", "Capital Shoppers"
        ]
        
        # Generate transactions for the last 6 months
        start_date = date.today() - timedelta(days=180)
        current_date = start_date
        
        while current_date <= date.today():
            # Generate 1-5 transactions per day
            num_transactions = random.randint(1, 5)
            
            for _ in range(num_transactions):
                transaction_id = str(uuid.uuid4())
                category = random.choice(categories)
                
                # Generate realistic amounts based on category
                amount_ranges = {
                    TransactionCategory.GROCERIES: (10000, 150000),
                    TransactionCategory.TRANSPORTATION: (2000, 50000),
                    TransactionCategory.FOOD_DINING: (5000, 80000),
                    TransactionCategory.ENTERTAINMENT: (10000, 100000),
                    TransactionCategory.BILLS_UTILITIES: (50000, 300000),
                    TransactionCategory.FUEL: (30000, 120000),
                    TransactionCategory.SHOPPING: (20000, 200000),
                    TransactionCategory.HEALTHCARE: (15000, 500000),
                    TransactionCategory.EDUCATION: (100000, 1000000),
                    TransactionCategory.INCOME: (500000, 2000000)
                }
                
                min_amount, max_amount = amount_ranges.get(category, (5000, 100000))
                amount = Decimal(str(random.randint(min_amount, max_amount)))
                
                # Income transactions are positive, expenses are negative for analytics
                is_income = category == TransactionCategory.INCOME
                if not is_income:
                    amount = -amount
                
                self.transactions[transaction_id] = TransactionAnalyticsDB(
                    id=transaction_id,
                    user_id=user_id,
                    transaction_id=f"txn_{transaction_id[:8]}",
                    amount=amount,
                    category=category,
                    merchant=random.choice(merchants) if not is_income else "Salary",
                    description=f"{category.value.replace('_', ' ').title()} transaction",
                    transaction_date=current_date,
                    currency="UGX",
                    is_income=is_income,
                    created_at=datetime.combine(current_date, datetime.min.time())
                )
            
            current_date += timedelta(days=1)
    
    async def get_spending_analysis(
        self, 
        user_id: str, 
        request: SpendingAnalysisRequest
    ) -> List[SpendingByCategory]:
        """Get spending analysis by category"""
        # Filter user transactions
        user_transactions = [
            t for t in self.transactions.values() 
            if t.user_id == user_id and not t.is_income
        ]
        
        # Apply date filters
        if request.start_date:
            user_transactions = [t for t in user_transactions if t.transaction_date >= request.start_date]
        if request.end_date:
            user_transactions = [t for t in user_transactions if t.transaction_date <= request.end_date]
        
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
            
            # Determine trend (mock calculation)
            trend = random.choice(list(TrendDirection))
            
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
    
    async def get_cash_flow_analysis(
        self, 
        user_id: str, 
        request: AnalyticsRequest
    ) -> CashFlowAnalysis:
        """Get cash flow analysis for a period"""
        # Filter user transactions
        user_transactions = [
            t for t in self.transactions.values() 
            if t.user_id == user_id
        ]
        
        # Apply date filters
        if request.start_date:
            user_transactions = [t for t in user_transactions if t.transaction_date >= request.start_date]
        if request.end_date:
            user_transactions = [t for t in user_transactions if t.transaction_date <= request.end_date]
        
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
        if net_cash_flow > total_income * Decimal('0.1'):
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
        """Create a new budget"""
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
        
        self.budgets[budget_id] = budget
        
        # Calculate current spending for this budget
        spent_amount = await self._calculate_budget_spending(user_id, budget)
        
        return self._build_budget_profile(budget, spent_amount)
    
    async def get_user_budgets(self, user_id: str) -> List[BudgetProfile]:
        """Get all budgets for a user"""
        user_budgets = [b for b in self.budgets.values() if b.user_id == user_id]
        budget_profiles = []
        
        for budget in user_budgets:
            spent_amount = await self._calculate_budget_spending(user_id, budget)
            profile = self._build_budget_profile(budget, spent_amount)
            budget_profiles.append(profile)
        
        return budget_profiles
    
    async def get_budget_summary(self, user_id: str) -> BudgetSummary:
        """Get budget summary for user"""
        user_budgets = [b for b in self.budgets.values() if b.user_id == user_id and b.is_active]
        
        total_budgets = len(user_budgets)
        active_budgets = len([b for b in user_budgets if b.is_active])
        total_budgeted = sum(b.amount for b in user_budgets)
        
        # Calculate total spent across all budgets
        total_spent = Decimal('0')
        budgets_over_limit = 0
        budgets_on_track = 0
        budgets_under_budget = 0
        
        for budget in user_budgets:
            spent_amount = await self._calculate_budget_spending(user_id, budget)
            total_spent += spent_amount
            
            percentage_used = float(spent_amount / budget.amount * 100) if budget.amount > 0 else 0
            
            if percentage_used > 100:
                budgets_over_limit += 1
            elif percentage_used > 80:
                budgets_on_track += 1
            else:
                budgets_under_budget += 1
        
        total_remaining = total_budgeted - total_spent
        overall_percentage_used = float(total_spent / total_budgeted * 100) if total_budgeted > 0 else 0
        
        return BudgetSummary(
            total_budgets=total_budgets,
            active_budgets=active_budgets,
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
        """Create a new financial goal"""
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
        
        self.financial_goals[goal_id] = goal
        
        return self._build_financial_goal_profile(goal)
    
    async def get_user_financial_goals(self, user_id: str) -> List[FinancialGoalProfile]:
        """Get all financial goals for a user"""
        user_goals = [g for g in self.financial_goals.values() if g.user_id == user_id]
        return [self._build_financial_goal_profile(goal) for goal in user_goals]
    
    async def get_financial_health_score(self, user_id: str) -> FinancialHealthScore:
        """Calculate financial health score"""
        # Get user data
        user_transactions = [t for t in self.transactions.values() if t.user_id == user_id]
        user_budgets = [b for b in self.budgets.values() if b.user_id == user_id and b.is_active]
        user_goals = [g for g in self.financial_goals.values() if g.user_id == user_id]
        
        # Calculate component scores
        spending_score = await self._calculate_spending_score(user_transactions, user_budgets)
        savings_score = await self._calculate_savings_score(user_goals, user_transactions)
        budget_adherence_score = await self._calculate_budget_adherence_score(user_id, user_budgets)
        debt_management_score = random.randint(70, 90)  # Mock score
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
        """Generate financial insights for user"""
        insights = []
        
        # Analyze spending patterns
        user_transactions = [
            t for t in self.transactions.values() 
            if t.user_id == user_id and not t.is_income
        ]
        
        # Recent transactions (last 30 days)
        recent_date = date.today() - timedelta(days=30)
        recent_transactions = [
            t for t in user_transactions 
            if t.transaction_date >= recent_date
        ]
        
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
        """Get financial alerts for user"""
        user_alerts = [a for a in self.financial_alerts.values() if a.user_id == user_id]
        
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
        """Calculate current spending for a budget"""
        # Get transactions for the budget period and category
        user_transactions = [
            t for t in self.transactions.values()
            if (t.user_id == user_id and 
                t.category == budget.category and 
                not t.is_income and
                t.transaction_date >= budget.start_date)
        ]
        
        # Apply end date filter if specified
        if budget.end_date:
            user_transactions = [
                t for t in user_transactions 
                if t.transaction_date <= budget.end_date
            ]
        
        return sum(abs(t.amount) for t in user_transactions)
    
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
            if days_remaining > 0:
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
        days_remaining = (goal.target_date - date.today()).days
        
        # Calculate monthly target
        months_remaining = max(days_remaining / 30, 1)
        monthly_target = remaining_amount / Decimal(str(months_remaining))
        
        # Determine if on track
        expected_progress = 100 - (days_remaining / 365 * 100)  # Simplified calculation
        on_track = progress_percentage >= expected_progress * 0.8  # 80% of expected progress
        
        return FinancialGoalProfile(
            id=goal.id,
            name=goal.name,
            target_amount=goal.target_amount,
            current_amount=goal.current_amount,
            remaining_amount=remaining_amount,
            target_date=goal.target_date,
            days_remaining=max(days_remaining, 0),
            progress_percentage=round(progress_percentage, 2),
            monthly_target=monthly_target,
            on_track=on_track,
            category=goal.category,
            currency=goal.currency,
            description=goal.description,
            created_at=goal.created_at,
            updated_at=goal.updated_at
        )
    
    async def _calculate_spending_score(self, transactions: List[TransactionAnalyticsDB], budgets: List[BudgetDB]) -> int:
        """Calculate spending efficiency score"""
        if not transactions:
            return 50
        
        # Calculate spending variance and trends
        recent_transactions = [
            t for t in transactions 
            if t.transaction_date >= date.today() - timedelta(days=30) and not t.is_income
        ]
        
        if not recent_transactions:
            return 70
        
        # Mock calculation based on spending patterns
        total_spending = sum(abs(t.amount) for t in recent_transactions)
        avg_transaction = total_spending / len(recent_transactions)
        
        # Higher scores for lower average transactions and consistent spending
        if avg_transaction < Decimal('50000'):  # Small transactions
            base_score = 85
        elif avg_transaction < Decimal('100000'):  # Medium transactions
            base_score = 75
        else:  # Large transactions
            base_score = 65
        
        # Adjust based on budget adherence
        if budgets:
            budget_adherence_bonus = random.randint(-10, 15)
            base_score += budget_adherence_bonus
        
        return max(30, min(100, base_score))
    
    async def _calculate_savings_score(self, goals: List[FinancialGoalDB], transactions: List[TransactionAnalyticsDB]) -> int:
        """Calculate savings rate score"""
        if not goals:
            return 40
        
        # Calculate progress on goals
        total_progress = 0
        for goal in goals:
            progress = float(goal.current_amount / goal.target_amount * 100) if goal.target_amount > 0 else 0
            total_progress += min(progress, 100)
        
        avg_progress = total_progress / len(goals)
        
        # Calculate savings rate from transactions
        income_transactions = [t for t in transactions if t.is_income]
        savings_transactions = [t for t in transactions if t.category == TransactionCategory.SAVINGS]
        
        if income_transactions and savings_transactions:
            total_income = sum(t.amount for t in income_transactions)
            total_savings = sum(abs(t.amount) for t in savings_transactions)
            savings_rate = float(total_savings / total_income * 100) if total_income > 0 else 0
            
            # Combine goal progress and savings rate
            score = int((avg_progress * 0.6) + (min(savings_rate, 30) * 2))  # Cap savings rate impact
        else:
            score = int(avg_progress * 0.8)
        
        return max(20, min(100, score))
    
    async def _calculate_budget_adherence_score(self, user_id: str, budgets: List[BudgetDB]) -> int:
        """Calculate budget adherence score"""
        if not budgets:
            return 60
        
        adherence_scores = []
        for budget in budgets:
            spent_amount = await self._calculate_budget_spending(user_id, budget)
            percentage_used = float(spent_amount / budget.amount * 100) if budget.amount > 0 else 0
            
            if percentage_used <= 80:
                adherence_scores.append(100)
            elif percentage_used <= 100:
                adherence_scores.append(80)
            elif percentage_used <= 120:
                adherence_scores.append(60)
            else:
                adherence_scores.append(30)
        
        return int(sum(adherence_scores) / len(adherence_scores))
    
    async def _calculate_emergency_fund_score(self, goals: List[FinancialGoalDB]) -> int:
        """Calculate emergency fund score"""
        emergency_goals = [g for g in goals if 'emergency' in g.name.lower() or g.category == TransactionCategory.SAVINGS]
        
        if not emergency_goals:
            return 20
        
        # Find the largest emergency fund goal
        largest_goal = max(emergency_goals, key=lambda g: g.target_amount)
        progress = float(largest_goal.current_amount / largest_goal.target_amount * 100) if largest_goal.target_amount > 0 else 0
        
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
