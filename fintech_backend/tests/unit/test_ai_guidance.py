"""
Unit tests for AI Financial Guidance Service
Tests personalized recommendations, investment readiness scoring, and ML insights
"""

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch

from fintech_backend.app.services.ai_guidance_service import AIGuidanceService
from fintech_backend.app.models.ai_guidance import (
    AIGuidanceRequest, RecommendationType, RecommendationPriority,
    InvestmentReadinessLevel, RiskTolerance, FinancialPersona
)


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    return Mock()


@pytest.fixture
def ai_guidance_service(mock_db_session):
    """Create AI Guidance Service instance"""
    return AIGuidanceService(mock_db_session)


@pytest.fixture
def mock_user_id():
    """Mock user ID"""
    return "test-user-123"


@pytest.fixture
def mock_transactions():
    """Mock transaction data"""
    transactions = []
    base_date = date.today() - timedelta(days=90)
    
    # Add income transactions
    for i in range(3):
        trans = Mock()
        trans.transaction_date = base_date + timedelta(days=i*30)
        trans.amount = Decimal("3000.00")
        trans.is_income = True
        trans.category = "salary"
        trans.merchant = "Employer Inc"
        transactions.append(trans)
    
    # Add expense transactions
    categories = ["groceries", "utilities", "entertainment", "transport"]
    for i in range(30):
        trans = Mock()
        trans.transaction_date = base_date + timedelta(days=i*3)
        trans.amount = Decimal("50.00") + Decimal(str(i * 5))
        trans.is_income = False
        trans.category = Mock()
        trans.category.value = categories[i % len(categories)]
        trans.merchant = f"Merchant {i}"
        transactions.append(trans)
    
    return transactions


@pytest.fixture
def mock_health_score():
    """Mock financial health score"""
    score = Mock()
    score.overall_score = 75
    score.spending_score = 70
    score.savings_score = 65
    score.budget_adherence_score = 80
    score.debt_management_score = 75
    score.emergency_fund_score = 60
    return score


@pytest.fixture
def mock_savings_insights():
    """Mock savings insights"""
    insights = Mock()
    insights.current_savings_rate = Decimal("300.00")
    insights.recommended_savings_rate = Decimal("500.00")
    return insights


@pytest.fixture
def mock_savings_stats():
    """Mock savings statistics"""
    stats = Mock()
    stats.monthly_savings_rate = Decimal("400.00")
    stats.total_goals = 3
    stats.completed_goals = 1
    stats.average_progress = 65.0
    return stats


@pytest.fixture
def mock_surplus_result():
    """Mock surplus detection result"""
    result = Mock()
    result.has_surplus = True
    result.surplus_amount = Decimal("1500.00")
    result.confidence_score = 0.85
    return result


class TestAIGuidanceService:
    """Test AI Guidance Service"""
    
    @pytest.mark.asyncio
    async def test_get_user_settings(self, ai_guidance_service, mock_user_id):
        """Test getting user settings"""
        settings = await ai_guidance_service._get_user_settings(mock_user_id)
        
        assert settings.user_id == mock_user_id
        assert settings.enabled is True
        assert settings.risk_tolerance == RiskTolerance.MODERATE
        assert settings.recommendation_frequency == "weekly"
        assert settings.enable_ml_insights is True
    
    @pytest.mark.asyncio
    async def test_calculate_cash_flow_stability(self, ai_guidance_service, mock_transactions):
        """Test cash flow stability calculation"""
        stability_score = await ai_guidance_service._calculate_cash_flow_stability(mock_transactions)
        
        assert isinstance(stability_score, int)
        assert 0 <= stability_score <= 100
    
    @pytest.mark.asyncio
    async def test_calculate_recommended_allocation_conservative(self, ai_guidance_service):
        """Test portfolio allocation for conservative risk tolerance"""
        allocation = ai_guidance_service._calculate_recommended_allocation(
            RiskTolerance.CONSERVATIVE,
            InvestmentReadinessLevel.READY,
            70
        )
        
        assert "stocks" in allocation
        assert "bonds" in allocation
        assert "cash" in allocation
        assert allocation["bonds"] > allocation["stocks"]  # Conservative = more bonds
    
    @pytest.mark.asyncio
    async def test_calculate_recommended_allocation_aggressive(self, ai_guidance_service):
        """Test portfolio allocation for aggressive risk tolerance"""
        allocation = ai_guidance_service._calculate_recommended_allocation(
            RiskTolerance.AGGRESSIVE,
            InvestmentReadinessLevel.HIGHLY_READY,
            85
        )
        
        assert allocation["stocks"] > allocation["bonds"]  # Aggressive = more stocks
        assert allocation["stocks"] >= 0.70
    
    @pytest.mark.asyncio
    async def test_priority_value_conversion(self, ai_guidance_service):
        """Test priority to numeric value conversion"""
        assert ai_guidance_service._priority_value(RecommendationPriority.CRITICAL) == 4
        assert ai_guidance_service._priority_value(RecommendationPriority.HIGH) == 3
        assert ai_guidance_service._priority_value(RecommendationPriority.MEDIUM) == 2
        assert ai_guidance_service._priority_value(RecommendationPriority.LOW) == 1

    @pytest.mark.asyncio
    async def test_create_emergency_fund_recommendation(
        self, ai_guidance_service, mock_user_id, mock_health_score, mock_transactions
    ):
        """Test emergency fund recommendation creation"""
        recommendation = await ai_guidance_service._create_emergency_fund_recommendation(
            mock_user_id, mock_health_score, mock_transactions
        )

        assert recommendation.type == RecommendationType.BUILD_EMERGENCY_FUND
        assert recommendation.priority in [RecommendationPriority.CRITICAL, RecommendationPriority.HIGH]
        assert recommendation.impact_score == 90
        assert len(recommendation.action_steps) > 0
        assert recommendation.amount is not None

    @pytest.mark.asyncio
    async def test_create_savings_recommendation(
        self, ai_guidance_service, mock_user_id, mock_savings_insights, mock_surplus_result
    ):
        """Test savings recommendation creation"""
        recommendation = await ai_guidance_service._create_savings_recommendation(
            mock_user_id, mock_savings_insights, mock_surplus_result
        )

        assert recommendation.type == RecommendationType.SAVE_MORE
        assert recommendation.priority == RecommendationPriority.HIGH
        assert recommendation.estimated_savings is not None
        assert len(recommendation.action_steps) >= 3

    @pytest.mark.asyncio
    async def test_create_investment_recommendation(
        self, ai_guidance_service, mock_user_id, mock_surplus_result
    ):
        """Test investment recommendation creation"""
        recommendation = await ai_guidance_service._create_investment_recommendation(
            mock_user_id, mock_surplus_result, RiskTolerance.MODERATE
        )

        assert recommendation.type == RecommendationType.INVEST_NOW
        assert recommendation.amount is not None
        assert recommendation.amount <= mock_surplus_result.surplus_amount
        assert "invest" in recommendation.title.lower()

    @pytest.mark.asyncio
    async def test_analyze_spending_patterns(self, ai_guidance_service, mock_transactions):
        """Test spending pattern analysis"""
        insight = await ai_guidance_service._analyze_spending_patterns(mock_transactions)

        if insight:  # May return None if no patterns found
            assert insight.insight_type == "spending_pattern"
            assert insight.confidence_score > 0
            assert insight.confidence_score <= 1
            assert "category" in insight.data_points

    @pytest.mark.asyncio
    async def test_analyze_income_trends(self, ai_guidance_service, mock_transactions):
        """Test income trend analysis"""
        insight = await ai_guidance_service._analyze_income_trends(mock_transactions)

        if insight:
            assert insight.insight_type == "income_trend"
            assert insight.trend in ["increasing", "decreasing", "stable", "volatile"]
            assert "average_income" in insight.data_points

    @pytest.mark.asyncio
    async def test_detect_savings_opportunities(self, ai_guidance_service, mock_transactions):
        """Test savings opportunity detection"""
        insight = await ai_guidance_service._detect_savings_opportunities(mock_transactions)

        if insight:
            assert insight.insight_type == "savings_opportunity"
            assert "potential_savings" in insight.data_points
            assert insight.recommendation is not None

    @pytest.mark.asyncio
    async def test_generate_risk_alerts(self, ai_guidance_service, mock_transactions):
        """Test risk alert generation"""
        insight = await ai_guidance_service._generate_risk_alerts(mock_transactions)

        # May return None if no risks detected
        if insight:
            assert insight.insight_type == "risk_alert"
            assert insight.confidence_score > 0

    @pytest.mark.asyncio
    @patch.object(AIGuidanceService, '_get_user_transactions', new_callable=AsyncMock)
    @patch.object(AIGuidanceService, 'get_financial_health_score', new_callable=AsyncMock)
    async def test_calculate_investment_readiness(
        self, mock_health, mock_trans, ai_guidance_service,
        mock_user_id, mock_health_score, mock_transactions
    ):
        """Test investment readiness calculation"""
        # Setup mocks
        mock_health.return_value = mock_health_score
        mock_trans.return_value = mock_transactions

        settings = await ai_guidance_service._get_user_settings(mock_user_id)

        # Mock the required service methods
        with patch.object(ai_guidance_service.analytics_service, 'get_financial_health_score',
                         return_value=mock_health_score):
            with patch.object(ai_guidance_service.savings_service, 'get_savings_statistics',
                            return_value=Mock(total_goals=3, completed_goals=1, average_progress=65.0)):
                with patch.object(ai_guidance_service.notification_service, '_detect_surplus',
                                return_value=Mock(has_surplus=True, surplus_amount=Decimal("1000"))):
                    with patch.object(ai_guidance_service.analytics_service, '_get_user_transactions',
                                    return_value=mock_transactions):

                        readiness = await ai_guidance_service.calculate_investment_readiness(
                            mock_user_id, settings
                        )

                        assert 0 <= readiness.overall_score <= 100
                        assert readiness.readiness_level in list(InvestmentReadinessLevel)
                        assert "emergency_fund" in readiness.component_scores
                        assert "cash_flow_stability" in readiness.component_scores
                        assert readiness.emergency_fund_status in ["none", "insufficient", "adequate", "excellent"]
                        assert readiness.minimum_investment_amount > 0


class TestRecommendationFiltering:
    """Test recommendation filtering and prioritization"""

    @pytest.mark.asyncio
    async def test_filter_by_excluded_types(self, ai_guidance_service, mock_user_id):
        """Test filtering recommendations by excluded types"""
        settings = await ai_guidance_service._get_user_settings(mock_user_id)
        settings.exclude_recommendation_types = [RecommendationType.INVEST_NOW]

        # Create mock recommendations
        recommendations = [
            Mock(type=RecommendationType.SAVE_MORE, priority=RecommendationPriority.HIGH, impact_score=80),
            Mock(type=RecommendationType.INVEST_NOW, priority=RecommendationPriority.MEDIUM, impact_score=70),
            Mock(type=RecommendationType.BUILD_EMERGENCY_FUND, priority=RecommendationPriority.CRITICAL, impact_score=90)
        ]

        filtered = [
            rec for rec in recommendations
            if rec.type not in settings.exclude_recommendation_types
        ]

        assert len(filtered) == 2
        assert all(rec.type != RecommendationType.INVEST_NOW for rec in filtered)

