"""
Financial Health Score Service

Comprehensive service for calculating and managing financial health scores.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import statistics
from sqlalchemy.orm import Session

from app.models.financial_health import (
    FinancialHealthScore,
    HealthFactor,
    ScoreImprovement,
    HealthScoreTrend,
    HealthScoreHistory,
    HealthScoreSettings,
    HealthScoreLevel,
    FactorCategory,
    TrendDirection
)


class FinancialHealthService:
    """Service for calculating and analyzing financial health scores"""

    # Default weights for each factor (must sum to 1.0)
    DEFAULT_WEIGHTS = {
        FactorCategory.EMERGENCY_FUND: 0.25,
        FactorCategory.DEBT: 0.20,
        FactorCategory.SAVINGS: 0.20,
        FactorCategory.SPENDING: 0.15,
        FactorCategory.INCOME: 0.10,
        FactorCategory.INVESTMENTS: 0.10,
    }

    def __init__(self, db: Session):
        self.db = db

    async def calculate_health_score(
        self,
        user_id: str,
        financial_data: Dict,
        settings: Optional[HealthScoreSettings] = None
    ) -> FinancialHealthScore:
        """
        Calculate comprehensive financial health score

        Args:
            user_id: User identifier
            financial_data: Dictionary containing user's financial data
            settings: Optional user preferences for calculation

        Returns:
            Complete financial health score assessment
        """
        # Get weights (custom or default)
        weights = self._get_weights(settings)

        # Calculate individual factor scores
        factors = await self._calculate_all_factors(financial_data, weights, settings)

        # Calculate overall score
        overall_score = self._calculate_overall_score(factors)

        # Determine trend
        trend_direction, score_change_30d, score_change_90d = await self._calculate_trend(
            user_id, overall_score
        )

        # Identify strengths and weaknesses
        top_strengths, areas_for_improvement = self._identify_strengths_weaknesses(factors)

        # Generate improvement recommendations
        improvements = await self._generate_improvements(factors, financial_data)

        # Calculate percentile (mock for now - would compare with other users)
        percentile = self._calculate_percentile(overall_score)

        return FinancialHealthScore(
            user_id=user_id,
            overall_score=round(overall_score, 1),
            level=self._determine_level(overall_score),
            factors=factors,
            trend_direction=trend_direction,
            score_change_30d=score_change_30d,
            score_change_90d=score_change_90d,
            percentile=percentile,
            top_strengths=top_strengths,
            areas_for_improvement=areas_for_improvement,
            improvements=improvements,
            calculated_at=datetime.utcnow(),
            next_update=datetime.utcnow() + timedelta(days=1)
        )

    async def _calculate_all_factors(
        self,
        financial_data: Dict,
        weights: Dict[FactorCategory, float],
        settings: Optional[HealthScoreSettings]
    ) -> List[HealthFactor]:
        """Calculate scores for all financial health factors"""
        factors = []

        # Emergency Fund Factor
        if self._should_include_factor(FactorCategory.EMERGENCY_FUND, settings):
            emergency_fund = self._calculate_emergency_fund_score(financial_data)
            emergency_fund.weight = weights.get(FactorCategory.EMERGENCY_FUND, 0.25)
            factors.append(emergency_fund)

        # Debt Factor
        if self._should_include_factor(FactorCategory.DEBT, settings):
            debt = self._calculate_debt_score(financial_data)
            debt.weight = weights.get(FactorCategory.DEBT, 0.20)
            factors.append(debt)

        # Savings Factor
        if self._should_include_factor(FactorCategory.SAVINGS, settings):
            savings = self._calculate_savings_score(financial_data)
            savings.weight = weights.get(FactorCategory.SAVINGS, 0.20)
            factors.append(savings)

        # Spending Factor
        if self._should_include_factor(FactorCategory.SPENDING, settings):
            spending = self._calculate_spending_score(financial_data)
            spending.weight = weights.get(FactorCategory.SPENDING, 0.15)
            factors.append(spending)

        # Income Factor
        if self._should_include_factor(FactorCategory.INCOME, settings):
            income = self._calculate_income_score(financial_data)
            income.weight = weights.get(FactorCategory.INCOME, 0.10)
            factors.append(income)

        # Investments Factor
        if self._should_include_factor(FactorCategory.INVESTMENTS, settings):
            investments = self._calculate_investments_score(financial_data)
            investments.weight = weights.get(FactorCategory.INVESTMENTS, 0.10)
            factors.append(investments)

        # Normalize weights if factors were excluded
        total_weight = sum(f.weight for f in factors)
        if total_weight > 0 and total_weight != 1.0:
            for factor in factors:
                factor.weight = factor.weight / total_weight

        return factors

    def _calculate_emergency_fund_score(self, financial_data: Dict) -> HealthFactor:
        """Calculate emergency fund adequacy score"""
        monthly_expenses = financial_data.get('monthly_expenses', 3000)
        emergency_fund = financial_data.get('emergency_fund', 0)

        # Target: 6 months of expenses
        target = monthly_expenses * 6
        months_covered = emergency_fund / monthly_expenses if monthly_expenses > 0 else 0

        # Score calculation: 0-100 based on months covered
        if months_covered >= 6:
            score = 100
        elif months_covered >= 3:
            score = 60 + (months_covered - 3) * 13.33  # 60-100 for 3-6 months
        elif months_covered >= 1:
            score = 30 + (months_covered - 1) * 15  # 30-60 for 1-3 months
        else:
            score = months_covered * 30  # 0-30 for 0-1 month

        return HealthFactor(
            category=FactorCategory.EMERGENCY_FUND,
            name="Emergency Fund",
            score=min(100, max(0, score)),
            weight=0.25,
            current_value=months_covered,
            target_value=6.0,
            unit="months",
            status=self._determine_level(score),
            description=f"You have {months_covered:.1f} months of expenses saved",
            impact="Critical safety net for unexpected expenses and job loss"
        )

    def _calculate_debt_score(self, financial_data: Dict) -> HealthFactor:
        """Calculate debt health score"""
        total_debt = financial_data.get('total_debt', 0)
        monthly_income = financial_data.get('monthly_income', 5000)
        monthly_debt_payment = financial_data.get('monthly_debt_payment', 0)

        # Calculate debt-to-income ratio
        dti_ratio = (monthly_debt_payment / monthly_income * 100) if monthly_income > 0 else 0

        # Score calculation based on DTI ratio
        if dti_ratio <= 15:
            score = 100
        elif dti_ratio <= 28:
            score = 85 - (dti_ratio - 15) * 1.15  # 85-100 for 15-28%
        elif dti_ratio <= 36:
            score = 60 - (dti_ratio - 28) * 3.125  # 60-85 for 28-36%
        elif dti_ratio <= 43:
            score = 30 - (dti_ratio - 36) * 4.29  # 30-60 for 36-43%
        else:
            score = max(0, 30 - (dti_ratio - 43) * 2)  # 0-30 for >43%

        return HealthFactor(
            category=FactorCategory.DEBT,
            name="Debt Management",
            score=min(100, max(0, score)),
            weight=0.20,
            current_value=dti_ratio,
            target_value=28.0,
            unit="%",
            status=self._determine_level(score),
            description=f"Debt-to-income ratio: {dti_ratio:.1f}%",
            impact="Lower debt burden improves financial flexibility and reduces stress"
        )

    def _calculate_savings_score(self, financial_data: Dict) -> HealthFactor:
        """Calculate savings rate score"""
        monthly_income = financial_data.get('monthly_income', 5000)
        monthly_savings = financial_data.get('monthly_savings', 0)

        # Calculate savings rate
        savings_rate = (monthly_savings / monthly_income * 100) if monthly_income > 0 else 0

        # Score calculation based on savings rate
        if savings_rate >= 20:
            score = 100
        elif savings_rate >= 15:
            score = 80 + (savings_rate - 15) * 4  # 80-100 for 15-20%
        elif savings_rate >= 10:
            score = 60 + (savings_rate - 10) * 4  # 60-80 for 10-15%
        elif savings_rate >= 5:
            score = 30 + (savings_rate - 5) * 6  # 30-60 for 5-10%
        else:
            score = savings_rate * 6  # 0-30 for 0-5%

        return HealthFactor(
            category=FactorCategory.SAVINGS,
            name="Savings Rate",
            score=min(100, max(0, score)),
            weight=0.20,
            current_value=savings_rate,
            target_value=20.0,
            unit="%",
            status=self._determine_level(score),
            description=f"Saving {savings_rate:.1f}% of income monthly",
            impact="Higher savings rate accelerates wealth building and financial independence"
        )

    def _calculate_spending_score(self, financial_data: Dict) -> HealthFactor:
        """Calculate spending discipline score"""
        monthly_income = financial_data.get('monthly_income', 5000)
        monthly_expenses = financial_data.get('monthly_expenses', 3000)
        budget_adherence = financial_data.get('budget_adherence', 75)  # 0-100%

        # Calculate expense ratio
        expense_ratio = (monthly_expenses / monthly_income * 100) if monthly_income > 0 else 100

        # Score based on expense ratio and budget adherence
        if expense_ratio <= 50:
            expense_score = 100
        elif expense_ratio <= 70:
            expense_score = 80 - (expense_ratio - 50) * 1  # 80-100 for 50-70%
        elif expense_ratio <= 80:
            expense_score = 60 - (expense_ratio - 70) * 2  # 60-80 for 70-80%
        else:
            expense_score = max(0, 60 - (expense_ratio - 80) * 3)  # 0-60 for >80%

        # Combine with budget adherence
        score = (expense_score * 0.6) + (budget_adherence * 0.4)

        return HealthFactor(
            category=FactorCategory.SPENDING,
            name="Spending Control",
            score=min(100, max(0, score)),
            weight=0.15,
            current_value=expense_ratio,
            target_value=70.0,
            unit="%",
            status=self._determine_level(score),
            description=f"Spending {expense_ratio:.1f}% of income, {budget_adherence:.0f}% budget adherence",
            impact="Controlled spending creates room for savings and investments"
        )

    def _calculate_income_score(self, financial_data: Dict) -> HealthFactor:
        """Calculate income stability and growth score"""
        monthly_income = financial_data.get('monthly_income', 5000)
        income_growth_rate = financial_data.get('income_growth_rate', 0)  # % year-over-year
        income_stability = financial_data.get('income_stability', 80)  # 0-100% consistency

        # Score based on growth and stability
        if income_growth_rate >= 10:
            growth_score = 100
        elif income_growth_rate >= 5:
            growth_score = 80 + (income_growth_rate - 5) * 4
        elif income_growth_rate >= 0:
            growth_score = 60 + (income_growth_rate) * 4
        else:
            growth_score = max(0, 60 + income_growth_rate * 6)  # Penalty for negative growth

        # Combine growth and stability
        score = (growth_score * 0.4) + (income_stability * 0.6)

        return HealthFactor(
            category=FactorCategory.INCOME,
            name="Income Health",
            score=min(100, max(0, score)),
            weight=0.10,
            current_value=income_growth_rate,
            target_value=5.0,
            unit="%",
            status=self._determine_level(score),
            description=f"{income_growth_rate:.1f}% income growth, {income_stability:.0f}% stability",
            impact="Stable and growing income provides foundation for financial health"
        )

    def _calculate_investments_score(self, financial_data: Dict) -> HealthFactor:
        """Calculate investment portfolio score"""
        total_investments = financial_data.get('total_investments', 0)
        monthly_income = financial_data.get('monthly_income', 5000)
        portfolio_diversification = financial_data.get('portfolio_diversification', 50)  # 0-100%

        # Calculate investment-to-income ratio (months of income invested)
        investment_ratio = total_investments / monthly_income if monthly_income > 0 else 0

        # Score based on investment level
        if investment_ratio >= 24:  # 2+ years of income
            investment_score = 100
        elif investment_ratio >= 12:  # 1-2 years
            investment_score = 80 + (investment_ratio - 12) * 1.67
        elif investment_ratio >= 6:  # 6-12 months
            investment_score = 60 + (investment_ratio - 6) * 3.33
        elif investment_ratio >= 3:  # 3-6 months
            investment_score = 30 + (investment_ratio - 3) * 10
        else:
            investment_score = investment_ratio * 10

        # Combine with diversification
        score = (investment_score * 0.7) + (portfolio_diversification * 0.3)

        return HealthFactor(
            category=FactorCategory.INVESTMENTS,
            name="Investment Portfolio",
            score=min(100, max(0, score)),
            weight=0.10,
            current_value=investment_ratio,
            target_value=24.0,
            unit="months",
            status=self._determine_level(score),
            description=f"{investment_ratio:.1f} months of income invested, {portfolio_diversification:.0f}% diversified",
            impact="Investments build long-term wealth and financial security"
        )

    def _calculate_overall_score(self, factors: List[HealthFactor]) -> float:
        """Calculate weighted overall score from all factors"""
        if not factors:
            return 0.0

        total_score = sum(factor.score * factor.weight for factor in factors)
        return round(total_score, 1)

    async def _calculate_trend(
        self,
        user_id: str,
        current_score: float
    ) -> Tuple[TrendDirection, float, float]:
        """Calculate score trend over time"""
        # TODO: Fetch historical scores from database
        # For now, return mock data
        score_change_30d = 2.5  # Mock: +2.5 points in last 30 days
        score_change_90d = 5.0  # Mock: +5.0 points in last 90 days

        # Determine trend direction
        if score_change_30d > 2:
            trend = TrendDirection.IMPROVING
        elif score_change_30d < -2:
            trend = TrendDirection.DECLINING
        else:
            trend = TrendDirection.STABLE

        return trend, score_change_30d, score_change_90d

    def _identify_strengths_weaknesses(
        self,
        factors: List[HealthFactor]
    ) -> Tuple[List[str], List[str]]:
        """Identify top strengths and areas for improvement"""
        # Sort factors by score
        sorted_factors = sorted(factors, key=lambda f: f.score, reverse=True)

        # Top 3 strengths (highest scores)
        strengths = [
            f"{f.name}: {f.description}"
            for f in sorted_factors[:3]
            if f.score >= 70
        ]

        # Top 3 weaknesses (lowest scores)
        weaknesses = [
            f"{f.name}: {f.description}"
            for f in sorted_factors[-3:]
            if f.score < 70
        ]
        weaknesses.reverse()  # Show worst first

        return strengths, weaknesses

    async def _generate_improvements(
        self,
        factors: List[HealthFactor],
        financial_data: Dict
    ) -> List[ScoreImprovement]:
        """Generate prioritized improvement recommendations"""
        improvements = []

        # Sort factors by score (lowest first = highest priority)
        sorted_factors = sorted(factors, key=lambda f: f.score)

        for i, factor in enumerate(sorted_factors[:5]):  # Top 5 improvements
            if factor.score >= 85:  # Skip factors that are already excellent
                continue

            improvement = self._create_improvement_for_factor(factor, financial_data, i + 1)
            if improvement:
                improvements.append(improvement)

        return improvements

    def _create_improvement_for_factor(
        self,
        factor: HealthFactor,
        financial_data: Dict,
        priority: int
    ) -> Optional[ScoreImprovement]:
        """Create specific improvement recommendation for a factor"""

        # Emergency Fund improvements
        if factor.category == FactorCategory.EMERGENCY_FUND:
            months_needed = max(0, 6 - factor.current_value)
            monthly_expenses = financial_data.get('monthly_expenses', 3000)
            amount_needed = months_needed * monthly_expenses

            return ScoreImprovement(
                factor=FactorCategory.EMERGENCY_FUND,
                title="Build Emergency Fund",
                description=f"Increase emergency fund to cover 6 months of expenses (${amount_needed:,.0f} more needed)",
                potential_impact=min(25, (100 - factor.score) * factor.weight),
                difficulty="medium",
                timeframe="6-12 months",
                action_steps=[
                    f"Set up automatic transfer of ${amount_needed/12:.0f}/month to savings",
                    "Open high-yield savings account for emergency fund",
                    "Reduce discretionary spending by 10-15%",
                    "Consider side income to accelerate savings"
                ],
                priority=priority
            )

        # Debt improvements
        elif factor.category == FactorCategory.DEBT:
            return ScoreImprovement(
                factor=FactorCategory.DEBT,
                title="Reduce Debt Burden",
                description="Lower your debt-to-income ratio to improve financial flexibility",
                potential_impact=min(20, (100 - factor.score) * factor.weight),
                difficulty="hard",
                timeframe="12-24 months",
                action_steps=[
                    "List all debts by interest rate (highest first)",
                    "Pay minimum on all debts, extra on highest rate",
                    "Consider debt consolidation if rates are high",
                    "Negotiate lower interest rates with creditors",
                    "Avoid taking on new debt"
                ],
                priority=priority
            )

        # Savings improvements
        elif factor.category == FactorCategory.SAVINGS:
            target_rate = 20.0
            current_rate = factor.current_value
            increase_needed = target_rate - current_rate

            return ScoreImprovement(
                factor=FactorCategory.SAVINGS,
                title="Increase Savings Rate",
                description=f"Boost savings from {current_rate:.1f}% to {target_rate}% of income",
                potential_impact=min(20, (100 - factor.score) * factor.weight),
                difficulty="medium",
                timeframe="3-6 months",
                action_steps=[
                    f"Increase monthly savings by {increase_needed:.1f}% of income",
                    "Automate savings on payday",
                    "Review and cut unnecessary subscriptions",
                    "Use the 50/30/20 budgeting rule",
                    "Save windfalls (bonuses, tax refunds)"
                ],
                priority=priority
            )

        # Spending improvements
        elif factor.category == FactorCategory.SPENDING:
            return ScoreImprovement(
                factor=FactorCategory.SPENDING,
                title="Improve Spending Control",
                description="Better track and manage your expenses",
                potential_impact=min(15, (100 - factor.score) * factor.weight),
                difficulty="easy",
                timeframe="1-3 months",
                action_steps=[
                    "Track every expense for 30 days",
                    "Create realistic budget categories",
                    "Use cash for discretionary spending",
                    "Implement 24-hour rule for large purchases",
                    "Review spending weekly"
                ],
                priority=priority
            )

        # Income improvements
        elif factor.category == FactorCategory.INCOME:
            return ScoreImprovement(
                factor=FactorCategory.INCOME,
                title="Increase Income Stability",
                description="Grow and stabilize your income sources",
                potential_impact=min(10, (100 - factor.score) * factor.weight),
                difficulty="hard",
                timeframe="6-12 months",
                action_steps=[
                    "Negotiate raise or promotion at current job",
                    "Develop high-demand skills",
                    "Start side business or freelancing",
                    "Diversify income streams",
                    "Build professional network"
                ],
                priority=priority
            )

        # Investment improvements
        elif factor.category == FactorCategory.INVESTMENTS:
            return ScoreImprovement(
                factor=FactorCategory.INVESTMENTS,
                title="Build Investment Portfolio",
                description="Start or grow your investment portfolio",
                potential_impact=min(10, (100 - factor.score) * factor.weight),
                difficulty="medium",
                timeframe="Ongoing",
                action_steps=[
                    "Open retirement account (401k, IRA)",
                    "Start with low-cost index funds",
                    "Invest 10-15% of income monthly",
                    "Diversify across asset classes",
                    "Rebalance portfolio quarterly"
                ],
                priority=priority
            )

        return None

    def _get_weights(self, settings: Optional[HealthScoreSettings]) -> Dict[FactorCategory, float]:
        """Get factor weights (custom or default)"""
        if settings and settings.custom_weights:
            return settings.custom_weights
        return self.DEFAULT_WEIGHTS.copy()

    def _should_include_factor(
        self,
        factor: FactorCategory,
        settings: Optional[HealthScoreSettings]
    ) -> bool:
        """Check if factor should be included in calculation"""
        if not settings:
            return True
        return factor not in settings.excluded_factors

    def _determine_level(self, score: float) -> HealthScoreLevel:
        """Determine health level from score"""
        if score >= 86:
            return HealthScoreLevel.EXCELLENT
        elif score >= 76:
            return HealthScoreLevel.GOOD
        elif score >= 61:
            return HealthScoreLevel.FAIR
        elif score >= 41:
            return HealthScoreLevel.POOR
        else:
            return HealthScoreLevel.CRITICAL

    def _calculate_percentile(self, score: float) -> float:
        """Calculate user's percentile (mock implementation)"""
        # TODO: Compare with actual user database
        # For now, use a simple formula
        if score >= 90:
            return 95.0
        elif score >= 80:
            return 80.0 + (score - 80) * 1.5
        elif score >= 70:
            return 60.0 + (score - 70) * 2.0
        elif score >= 60:
            return 40.0 + (score - 60) * 2.0
        else:
            return score * 0.67

    async def get_score_history(
        self,
        user_id: str,
        days: int = 90
    ) -> HealthScoreHistory:
        """Get historical health score data"""
        # TODO: Fetch from database
        # For now, generate mock trend data
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        trends = []
        current_score = 75.0

        for i in range(days):
            date = start_date + timedelta(days=i)
            # Simulate gradual improvement
            score = current_score + (i * 0.05) + (i % 7 * 0.5)  # Weekly variation
            score = min(100, max(0, score))

            trends.append(HealthScoreTrend(
                date=date,
                score=round(score, 1),
                level=self._determine_level(score),
                factors={}
            ))

        scores = [t.score for t in trends]

        return HealthScoreHistory(
            user_id=user_id,
            trends=trends,
            period_start=start_date,
            period_end=end_date,
            average_score=round(statistics.mean(scores), 1),
            highest_score=round(max(scores), 1),
            lowest_score=round(min(scores), 1)
        )

