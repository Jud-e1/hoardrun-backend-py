"""
AI Financial Guidance Service
Provides personalized financial recommendations and investment readiness scoring
"""

import uuid
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any
from decimal import Decimal
from sqlalchemy.orm import Session

from ..models.ai_guidance import (
    AIGuidanceRequest, AIGuidanceResponse, PersonalizedRecommendation,
    InvestmentReadinessScore, MLInsight, FinancialPersonaProfile,
    AIGuidanceSettings, RecommendationType, RecommendationPriority,
    InvestmentReadinessLevel, RiskTolerance, FinancialPersona
)
from ..services.analytics_service import AnalyticsService
from ..services.savings_service import SavingsService
from ..services.smart_notification_service import SmartNotificationService


class AIGuidanceService:
    """Service for AI-powered financial guidance"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.analytics_service = AnalyticsService(db_session)
        self.savings_service = SavingsService(db_session)
        self.notification_service = SmartNotificationService(db_session)
        
        # In-memory cache for settings and recommendations
        self.settings_cache: Dict[str, AIGuidanceSettings] = {}
        self.recommendations_cache: Dict[str, List[PersonalizedRecommendation]] = {}
    
    async def get_ai_guidance(
        self, 
        user_id: str, 
        request: AIGuidanceRequest
    ) -> AIGuidanceResponse:
        """Get complete AI financial guidance for user"""
        
        # Get user settings
        settings = await self._get_user_settings(user_id)
        
        # Generate components based on request
        recommendations = []
        if request.include_recommendations:
            recommendations = await self.generate_recommendations(user_id, settings)
        
        investment_readiness = None
        if request.include_investment_readiness:
            investment_readiness = await self.calculate_investment_readiness(user_id, settings)
        
        ml_insights = []
        if request.include_insights and settings.enable_ml_insights:
            ml_insights = await self.generate_ml_insights(user_id, request.time_horizon_days)
        
        # Determine financial persona
        financial_persona = await self._determine_financial_persona(user_id)
        
        # Get overall financial health
        health_score = await self.analytics_service.get_financial_health_score(user_id)
        
        # Calculate next review date
        frequency_days = {"daily": 1, "weekly": 7, "monthly": 30}
        next_review = date.today() + timedelta(days=frequency_days.get(settings.recommendation_frequency, 7))
        
        return AIGuidanceResponse(
            user_id=user_id,
            recommendations=recommendations,
            investment_readiness=investment_readiness or await self.calculate_investment_readiness(user_id, settings),
            ml_insights=ml_insights,
            financial_persona=financial_persona,
            overall_financial_health=health_score.overall_score,
            next_review_date=next_review,
            generated_at=datetime.utcnow()
        )
    
    async def generate_recommendations(
        self, 
        user_id: str, 
        settings: AIGuidanceSettings
    ) -> List[PersonalizedRecommendation]:
        """Generate personalized financial recommendations"""
        recommendations = []
        
        # Get user financial data
        health_score = await self.analytics_service.get_financial_health_score(user_id)
        savings_insights = await self.savings_service.get_savings_insights(user_id)
        surplus_result = await self.notification_service._detect_surplus(user_id, Decimal("100"))
        
        # Get recent transactions for analysis
        recent_date = date.today() - timedelta(days=30)
        transactions = await self.analytics_service._get_user_transactions(
            user_id, start_date=recent_date, include_income=True
        )
        
        # 1. Emergency Fund Recommendation
        if health_score.emergency_fund_score < 50:
            recommendations.append(await self._create_emergency_fund_recommendation(
                user_id, health_score, transactions
            ))
        
        # 2. Savings Optimization
        if health_score.savings_score < 70:
            recommendations.append(await self._create_savings_recommendation(
                user_id, savings_insights, surplus_result
            ))
        
        # 3. Spending Reduction
        if health_score.spending_score < 70:
            recommendations.append(await self._create_spending_reduction_recommendation(
                user_id, transactions
            ))
        
        # 4. Investment Opportunity
        if surplus_result.has_surplus and surplus_result.surplus_amount >= 1000:
            recommendations.append(await self._create_investment_recommendation(
                user_id, surplus_result, settings.risk_tolerance
            ))
        
        # 5. Budget Optimization
        if health_score.budget_adherence_score < 70:
            recommendations.append(await self._create_budget_optimization_recommendation(
                user_id, health_score
            ))
        
        # Filter by priority and excluded types
        filtered_recommendations = [
            rec for rec in recommendations
            if rec.type not in settings.exclude_recommendation_types
            and self._priority_value(rec.priority) >= self._priority_value(settings.min_recommendation_priority)
        ]
        
        # Sort by priority and impact
        filtered_recommendations.sort(
            key=lambda x: (self._priority_value(x.priority), x.impact_score),
            reverse=True
        )
        
        # Cache recommendations
        self.recommendations_cache[user_id] = filtered_recommendations
        
        return filtered_recommendations[:10]  # Return top 10
    
    async def calculate_investment_readiness(
        self, 
        user_id: str, 
        settings: AIGuidanceSettings
    ) -> InvestmentReadinessScore:
        """Calculate investment readiness score"""
        
        # Get financial data
        health_score = await self.analytics_service.get_financial_health_score(user_id)
        savings_stats = await self.savings_service.get_savings_statistics(user_id)
        surplus_result = await self.notification_service._detect_surplus(user_id, Decimal("100"))
        
        # Get transactions for cash flow analysis
        recent_date = date.today() - timedelta(days=90)
        transactions = await self.analytics_service._get_user_transactions(
            user_id, start_date=recent_date, include_income=True
        )

        # Calculate component scores
        component_scores = {}

        # 1. Emergency Fund Score (0-100)
        component_scores["emergency_fund"] = health_score.emergency_fund_score

        # 2. Cash Flow Stability (0-100)
        cash_flow_stability = await self._calculate_cash_flow_stability(transactions)
        component_scores["cash_flow_stability"] = cash_flow_stability

        # 3. Debt Management (0-100)
        component_scores["debt_management"] = health_score.debt_management_score

        # 4. Savings Rate (0-100)
        component_scores["savings_rate"] = health_score.savings_score

        # 5. Financial Discipline (0-100)
        component_scores["financial_discipline"] = health_score.budget_adherence_score

        # Calculate overall score (weighted average)
        overall_score = int(
            component_scores["emergency_fund"] * 0.30 +
            component_scores["cash_flow_stability"] * 0.25 +
            component_scores["debt_management"] * 0.20 +
            component_scores["savings_rate"] * 0.15 +
            component_scores["financial_discipline"] * 0.10
        )

        # Determine readiness level
        if overall_score >= 81:
            readiness_level = InvestmentReadinessLevel.HIGHLY_READY
        elif overall_score >= 61:
            readiness_level = InvestmentReadinessLevel.READY
        elif overall_score >= 41:
            readiness_level = InvestmentReadinessLevel.GETTING_READY
        else:
            readiness_level = InvestmentReadinessLevel.NOT_READY

        # Identify strengths and weaknesses
        strengths = []
        weaknesses = []
        recommendations = []

        for component, score in component_scores.items():
            if score >= 75:
                strengths.append(f"Strong {component.replace('_', ' ')}")
            elif score < 50:
                weaknesses.append(f"Weak {component.replace('_', ' ')}")
                recommendations.append(f"Improve your {component.replace('_', ' ')} to increase investment readiness")

        # Determine emergency fund status
        if component_scores["emergency_fund"] >= 80:
            emergency_fund_status = "excellent"
        elif component_scores["emergency_fund"] >= 60:
            emergency_fund_status = "adequate"
        elif component_scores["emergency_fund"] >= 30:
            emergency_fund_status = "insufficient"
        else:
            emergency_fund_status = "none"

        # Calculate debt-to-income ratio (mock for now)
        total_income = sum(t.amount for t in transactions if t.is_income)
        debt_to_income_ratio = 0.15  # Mock 15% DTI

        # Recommended allocation based on risk tolerance and readiness
        recommended_allocation = self._calculate_recommended_allocation(
            settings.risk_tolerance, readiness_level, overall_score
        )

        # Minimum investment amount
        minimum_investment_amount = Decimal("500") if overall_score >= 60 else Decimal("1000")

        return InvestmentReadinessScore(
            overall_score=overall_score,
            readiness_level=readiness_level,
            component_scores=component_scores,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations,
            risk_tolerance=settings.risk_tolerance,
            recommended_allocation=recommended_allocation,
            minimum_investment_amount=minimum_investment_amount,
            emergency_fund_status=emergency_fund_status,
            debt_to_income_ratio=debt_to_income_ratio,
            cash_flow_stability=cash_flow_stability,
            last_calculated=datetime.utcnow()
        )

    async def generate_ml_insights(
        self,
        user_id: str,
        time_horizon_days: int = 90
    ) -> List[MLInsight]:
        """Generate ML-based financial insights"""
        insights = []

        # Get historical data
        start_date = date.today() - timedelta(days=time_horizon_days)
        transactions = await self.analytics_service._get_user_transactions(
            user_id, start_date=start_date, include_income=True
        )

        if not transactions:
            return insights

        # 1. Spending Pattern Analysis
        spending_insight = await self._analyze_spending_patterns(transactions)
        if spending_insight:
            insights.append(spending_insight)

        # 2. Income Trend Analysis
        income_insight = await self._analyze_income_trends(transactions)
        if income_insight:
            insights.append(income_insight)

        # 3. Savings Opportunity Detection
        savings_insight = await self._detect_savings_opportunities(transactions)
        if savings_insight:
            insights.append(savings_insight)

        # 4. Risk Alert Generation
        risk_insight = await self._generate_risk_alerts(transactions)
        if risk_insight:
            insights.append(risk_insight)

        return insights

    # Helper Methods

    async def _get_user_settings(self, user_id: str) -> AIGuidanceSettings:
        """Get or create user settings"""
        if user_id in self.settings_cache:
            return self.settings_cache[user_id]

        # Default settings
        settings = AIGuidanceSettings(
            user_id=user_id,
            enabled=True,
            recommendation_frequency="weekly",
            risk_tolerance=RiskTolerance.MODERATE,
            investment_goals=[],
            exclude_recommendation_types=[],
            min_recommendation_priority=RecommendationPriority.MEDIUM,
            enable_ml_insights=True,
            enable_behavioral_nudges=True,
            updated_at=datetime.utcnow()
        )

        self.settings_cache[user_id] = settings
        return settings

    async def _determine_financial_persona(self, user_id: str) -> FinancialPersonaProfile:
        """Determine user's financial persona based on behavior"""

        # Get user data
        savings_stats = await self.savings_service.get_savings_statistics(user_id)
        health_score = await self.analytics_service.get_financial_health_score(user_id)

        # Analyze behavior
        savings_rate = float(savings_stats.monthly_savings_rate)
        spending_score = health_score.spending_score

        # Determine persona
        if savings_rate > 500 and spending_score > 70:
            persona = FinancialPersona.SAVER
            characteristics = ["Disciplined saver", "Low spending", "Goal-oriented"]
        elif spending_score < 50 and savings_rate < 100:
            persona = FinancialPersona.SPENDER
            characteristics = ["High spending", "Low savings", "Needs budget discipline"]
        elif savings_stats.total_goals > 3 and savings_stats.completed_goals > 0:
            persona = FinancialPersona.BALANCED
            characteristics = ["Balanced approach", "Goal-focused", "Financially aware"]
        else:
            persona = FinancialPersona.BEGINNER
            characteristics = ["Learning financial management", "Building habits", "Growing awareness"]

        return FinancialPersonaProfile(
            persona=persona,
            confidence=0.75,
            characteristics=characteristics,
            spending_habits={"score": spending_score, "trend": "stable"},
            savings_habits={"monthly_rate": savings_rate, "consistency": "moderate"},
            investment_behavior={"active": False, "risk_level": "moderate"},
            financial_goals_alignment=int(savings_stats.average_progress),
            behavior_trends=["Consistent savings", "Improving budget adherence"],
            last_updated=datetime.utcnow()
        )

    async def _calculate_cash_flow_stability(self, transactions: List[Any]) -> int:
        """Calculate cash flow stability score (0-100)"""
        if not transactions:
            return 50

        # Calculate monthly income variance
        income_transactions = [t for t in transactions if t.is_income]
        if len(income_transactions) < 2:
            return 60  # Not enough data

        # Group by month
        monthly_income = {}
        for t in income_transactions:
            month_key = t.transaction_date.strftime("%Y-%m") if hasattr(t.transaction_date, 'strftime') else str(t.transaction_date)[:7]
            monthly_income[month_key] = monthly_income.get(month_key, Decimal("0")) + t.amount

        if len(monthly_income) < 2:
            return 65

        # Calculate coefficient of variation
        incomes = list(monthly_income.values())
        avg_income = sum(incomes) / len(incomes)
        variance = sum((x - avg_income) ** 2 for x in incomes) / len(incomes)
        std_dev = variance ** Decimal("0.5")

        if avg_income > 0:
            cv = float(std_dev / avg_income)
            # Lower CV = higher stability
            stability_score = max(0, min(100, int(100 - (cv * 100))))
        else:
            stability_score = 50

        return stability_score

    def _calculate_recommended_allocation(
        self,
        risk_tolerance: RiskTolerance,
        readiness_level: InvestmentReadinessLevel,
        overall_score: int
    ) -> Dict[str, float]:
        """Calculate recommended portfolio allocation"""

        # Base allocations by risk tolerance
        if risk_tolerance == RiskTolerance.CONSERVATIVE:
            base_allocation = {"stocks": 0.30, "bonds": 0.50, "cash": 0.20}
        elif risk_tolerance == RiskTolerance.AGGRESSIVE:
            base_allocation = {"stocks": 0.70, "bonds": 0.20, "cash": 0.10}
        else:  # MODERATE
            base_allocation = {"stocks": 0.50, "bonds": 0.35, "cash": 0.15}

        # Adjust based on readiness
        if readiness_level == InvestmentReadinessLevel.NOT_READY:
            # More conservative
            return {"stocks": 0.20, "bonds": 0.30, "cash": 0.50}
        elif readiness_level == InvestmentReadinessLevel.HIGHLY_READY:
            # Can be more aggressive
            base_allocation["stocks"] = min(0.80, base_allocation["stocks"] + 0.10)
            base_allocation["cash"] = max(0.05, base_allocation["cash"] - 0.10)

        return base_allocation

    def _priority_value(self, priority: RecommendationPriority) -> int:
        """Convert priority to numeric value for comparison"""
        priority_map = {
            RecommendationPriority.CRITICAL: 4,
            RecommendationPriority.HIGH: 3,
            RecommendationPriority.MEDIUM: 2,
            RecommendationPriority.LOW: 1
        }
        return priority_map.get(priority, 0)

    # Recommendation Creation Methods

    async def _create_emergency_fund_recommendation(
        self,
        user_id: str,
        health_score: Any,
        transactions: List[Any]
    ) -> PersonalizedRecommendation:
        """Create emergency fund recommendation"""

        # Calculate monthly expenses
        expenses = [t for t in transactions if not t.is_income]
        monthly_expenses = sum(t.amount for t in expenses) / 3 if expenses else Decimal("1000")
        target_emergency_fund = monthly_expenses * 6

        return PersonalizedRecommendation(
            id=str(uuid.uuid4()),
            type=RecommendationType.BUILD_EMERGENCY_FUND,
            title="Build Your Emergency Fund",
            description=f"Aim to save ${target_emergency_fund:.2f} (6 months of expenses) for financial security.",
            priority=RecommendationPriority.CRITICAL if health_score.emergency_fund_score < 30 else RecommendationPriority.HIGH,
            impact_score=90,
            effort_level="medium",
            estimated_savings=None,
            action_steps=[
                f"Set a goal to save ${target_emergency_fund:.2f}",
                f"Start with ${monthly_expenses:.2f} (1 month of expenses)",
                "Automate monthly contributions",
                "Keep funds in a high-yield savings account"
            ],
            reasoning=f"Your emergency fund score is {health_score.emergency_fund_score}/100. "
                     f"Building an emergency fund protects you from unexpected expenses.",
            amount=target_emergency_fund,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=30)
        )

    async def _create_savings_recommendation(
        self,
        user_id: str,
        savings_insights: Any,
        surplus_result: Any
    ) -> PersonalizedRecommendation:
        """Create savings optimization recommendation"""

        recommended_increase = Decimal(str(savings_insights.recommended_savings_rate)) - Decimal(str(savings_insights.current_savings_rate))

        return PersonalizedRecommendation(
            id=str(uuid.uuid4()),
            type=RecommendationType.SAVE_MORE,
            title="Increase Your Savings Rate",
            description=f"Boost your monthly savings by ${recommended_increase:.2f} to reach your goals faster.",
            priority=RecommendationPriority.HIGH,
            impact_score=75,
            effort_level="medium",
            estimated_savings=recommended_increase,
            action_steps=[
                f"Increase monthly savings to ${savings_insights.recommended_savings_rate:.2f}",
                "Set up automatic transfers on payday",
                "Review and reduce discretionary spending",
                "Track progress weekly"
            ],
            reasoning=f"Your current savings rate is ${savings_insights.current_savings_rate:.2f}/month. "
                     f"Increasing to ${savings_insights.recommended_savings_rate:.2f} will help you achieve your financial goals.",
            amount=recommended_increase,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=30)
        )

    async def _create_spending_reduction_recommendation(
        self,
        user_id: str,
        transactions: List[Any]
    ) -> PersonalizedRecommendation:
        """Create spending reduction recommendation"""

        # Find highest spending category
        category_spending = {}
        for t in transactions:
            if not t.is_income:
                category = t.category.value if hasattr(t.category, 'value') else str(t.category)
                category_spending[category] = category_spending.get(category, Decimal("0")) + t.amount

        if category_spending:
            top_category, top_amount = max(category_spending.items(), key=lambda x: x[1])
            reduction_target = top_amount * Decimal("0.20")  # 20% reduction
        else:
            top_category = "discretionary"
            reduction_target = Decimal("200")

        return PersonalizedRecommendation(
            id=str(uuid.uuid4()),
            type=RecommendationType.REDUCE_SPENDING,
            title=f"Reduce {top_category.replace('_', ' ').title()} Spending",
            description=f"Cut spending in {top_category} by ${reduction_target:.2f}/month to improve financial health.",
            priority=RecommendationPriority.MEDIUM,
            impact_score=65,
            effort_level="medium",
            estimated_savings=reduction_target,
            action_steps=[
                f"Review all {top_category} transactions",
                "Identify unnecessary expenses",
                f"Set a budget limit for {top_category}",
                "Find cheaper alternatives"
            ],
            reasoning=f"{top_category.replace('_', ' ').title()} is your highest spending category. "
                     f"Reducing by 20% can free up ${reduction_target:.2f} monthly.",
            category=top_category,
            amount=reduction_target,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=30)
        )

    async def _create_investment_recommendation(
        self,
        user_id: str,
        surplus_result: Any,
        risk_tolerance: RiskTolerance
    ) -> PersonalizedRecommendation:
        """Create investment opportunity recommendation"""

        investment_amount = surplus_result.surplus_amount * Decimal("0.30")  # 30% of surplus

        return PersonalizedRecommendation(
            id=str(uuid.uuid4()),
            type=RecommendationType.INVEST_NOW,
            title="Start Investing Your Surplus",
            description=f"You have ${surplus_result.surplus_amount:.2f} available. Consider investing ${investment_amount:.2f}.",
            priority=RecommendationPriority.MEDIUM,
            impact_score=70,
            effort_level="low",
            estimated_savings=None,
            action_steps=[
                "Review investment options",
                f"Start with ${investment_amount:.2f}",
                "Choose diversified funds based on your risk tolerance",
                "Set up automatic monthly investments"
            ],
            reasoning=f"With ${surplus_result.surplus_amount:.2f} surplus and {risk_tolerance.value} risk tolerance, "
                     f"investing can help grow your wealth over time.",
            amount=investment_amount,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=14)
        )

    async def _create_budget_optimization_recommendation(
        self,
        user_id: str,
        health_score: Any
    ) -> PersonalizedRecommendation:
        """Create budget optimization recommendation"""

        return PersonalizedRecommendation(
            id=str(uuid.uuid4()),
            type=RecommendationType.OPTIMIZE_BUDGET,
            title="Optimize Your Budget",
            description="Improve budget adherence to better control your finances.",
            priority=RecommendationPriority.MEDIUM,
            impact_score=60,
            effort_level="medium",
            estimated_savings=Decimal("150"),
            action_steps=[
                "Review current budget allocations",
                "Set realistic spending limits",
                "Track expenses daily",
                "Adjust budgets based on actual spending patterns"
            ],
            reasoning=f"Your budget adherence score is {health_score.budget_adherence_score}/100. "
                     f"Better budget management leads to improved financial control.",
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=30)
        )

    # ML Insights Methods

    async def _analyze_spending_patterns(self, transactions: List[Any]) -> Optional[MLInsight]:
        """Analyze spending patterns using ML-like logic"""

        expenses = [t for t in transactions if not t.is_income]
        if not expenses:
            return None

        # Group by category
        category_spending = {}
        for t in expenses:
            category = t.category.value if hasattr(t.category, 'value') else str(t.category)
            if category not in category_spending:
                category_spending[category] = []
            category_spending[category].append(float(t.amount))

        # Find category with highest variance (potential optimization target)
        max_variance = 0
        target_category = None
        for category, amounts in category_spending.items():
            if len(amounts) > 1:
                avg = sum(amounts) / len(amounts)
                variance = sum((x - avg) ** 2 for x in amounts) / len(amounts)
                if variance > max_variance:
                    max_variance = variance
                    target_category = category

        if not target_category:
            return None

        avg_spending = sum(category_spending[target_category]) / len(category_spending[target_category])

        return MLInsight(
            id=str(uuid.uuid4()),
            insight_type="spending_pattern",
            title=f"Irregular Spending in {target_category.replace('_', ' ').title()}",
            description=f"Your {target_category} spending varies significantly (avg: ${avg_spending:.2f}). "
                       f"This suggests potential for optimization.",
            confidence_score=0.75,
            data_points={
                "category": target_category,
                "average_amount": avg_spending,
                "variance": max_variance,
                "transaction_count": len(category_spending[target_category])
            },
            predicted_outcome="Stabilizing this category could save 10-15% monthly",
            recommendation=f"Set a consistent budget for {target_category} and track weekly",
            category=target_category,
            amount=Decimal(str(avg_spending)),
            trend="volatile",
            created_at=datetime.utcnow()
        )

    async def _analyze_income_trends(self, transactions: List[Any]) -> Optional[MLInsight]:
        """Analyze income trends"""

        income_transactions = [t for t in transactions if t.is_income]
        if len(income_transactions) < 3:
            return None

        # Sort by date
        sorted_income = sorted(income_transactions, key=lambda x: x.transaction_date)

        # Calculate trend
        amounts = [float(t.amount) for t in sorted_income]
        avg_income = sum(amounts) / len(amounts)

        # Simple trend detection
        first_half_avg = sum(amounts[:len(amounts)//2]) / (len(amounts)//2)
        second_half_avg = sum(amounts[len(amounts)//2:]) / (len(amounts) - len(amounts)//2)

        if second_half_avg > first_half_avg * 1.1:
            trend = "increasing"
            description = f"Your income is trending upward! Average increased from ${first_half_avg:.2f} to ${second_half_avg:.2f}."
        elif second_half_avg < first_half_avg * 0.9:
            trend = "decreasing"
            description = f"Your income is trending downward. Average decreased from ${first_half_avg:.2f} to ${second_half_avg:.2f}."
        else:
            trend = "stable"
            description = f"Your income is stable at around ${avg_income:.2f}."

        return MLInsight(
            id=str(uuid.uuid4()),
            insight_type="income_trend",
            title="Income Trend Analysis",
            description=description,
            confidence_score=0.70,
            data_points={
                "average_income": avg_income,
                "first_half_avg": first_half_avg,
                "second_half_avg": second_half_avg,
                "transaction_count": len(income_transactions)
            },
            predicted_outcome=f"Expected monthly income: ${avg_income:.2f}",
            recommendation="Maintain income stability and explore growth opportunities" if trend == "stable" else "Monitor income changes closely",
            amount=Decimal(str(avg_income)),
            trend=trend,
            created_at=datetime.utcnow()
        )

    async def _detect_savings_opportunities(self, transactions: List[Any]) -> Optional[MLInsight]:
        """Detect savings opportunities"""

        expenses = [t for t in transactions if not t.is_income]
        if not expenses:
            return None

        # Find recurring small expenses that add up
        merchant_spending = {}
        for t in expenses:
            merchant = t.merchant or "Unknown"
            if merchant not in merchant_spending:
                merchant_spending[merchant] = []
            merchant_spending[merchant].append(float(t.amount))

        # Find merchants with frequent small transactions
        opportunity_merchant = None
        opportunity_amount = 0
        for merchant, amounts in merchant_spending.items():
            if len(amounts) >= 4:  # At least 4 transactions
                total = sum(amounts)
                if total > opportunity_amount:
                    opportunity_amount = total
                    opportunity_merchant = merchant

        if not opportunity_merchant:
            return None

        monthly_cost = opportunity_amount / 3  # Assuming 3 months of data
        potential_savings = monthly_cost * 0.5  # Could save 50%

        return MLInsight(
            id=str(uuid.uuid4()),
            insight_type="savings_opportunity",
            title=f"Savings Opportunity: {opportunity_merchant}",
            description=f"You spend ${monthly_cost:.2f}/month at {opportunity_merchant}. "
                       f"Reducing by 50% could save ${potential_savings:.2f}/month.",
            confidence_score=0.65,
            data_points={
                "merchant": opportunity_merchant,
                "monthly_cost": monthly_cost,
                "transaction_count": len(merchant_spending[opportunity_merchant]),
                "potential_savings": potential_savings
            },
            predicted_outcome=f"Annual savings potential: ${potential_savings * 12:.2f}",
            recommendation=f"Review {opportunity_merchant} expenses and find alternatives",
            amount=Decimal(str(potential_savings)),
            created_at=datetime.utcnow()
        )

    async def _generate_risk_alerts(self, transactions: List[Any]) -> Optional[MLInsight]:
        """Generate risk alerts based on transaction patterns"""

        if not transactions:
            return None

        # Calculate spending velocity (recent vs historical)
        sorted_trans = sorted(transactions, key=lambda x: x.transaction_date)
        recent_expenses = [t for t in sorted_trans[-10:] if not t.is_income]
        older_expenses = [t for t in sorted_trans[:-10] if not t.is_income]

        if not recent_expenses or not older_expenses:
            return None

        recent_avg = sum(float(t.amount) for t in recent_expenses) / len(recent_expenses)
        older_avg = sum(float(t.amount) for t in older_expenses) / len(older_expenses)

        if recent_avg > older_avg * 1.5:
            return MLInsight(
                id=str(uuid.uuid4()),
                insight_type="risk_alert",
                title="⚠️ Spending Spike Detected",
                description=f"Your recent spending (${recent_avg:.2f}/transaction) is 50% higher than usual (${older_avg:.2f}).",
                confidence_score=0.80,
                data_points={
                    "recent_average": recent_avg,
                    "historical_average": older_avg,
                    "increase_percentage": ((recent_avg - older_avg) / older_avg) * 100
                },
                predicted_outcome="Continued high spending may impact savings goals",
                recommendation="Review recent purchases and return to normal spending patterns",
                trend="increasing",
                created_at=datetime.utcnow()
            )

        return None

