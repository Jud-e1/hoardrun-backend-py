"""
Unit Tests for Financial Health Score Service

Tests for scoring algorithms, factor calculations, and recommendations.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

from app.services.financial_health_service import FinancialHealthService
from app.models.financial_health import (
    FactorCategory,
    HealthScoreLevel,
    TrendDirection
)


@pytest.fixture
def mock_db():
    """Mock database session"""
    return Mock()


@pytest.fixture
def service(mock_db):
    """Create service instance"""
    return FinancialHealthService(mock_db)


@pytest.fixture
def sample_financial_data():
    """Sample financial data for testing"""
    return {
        'monthly_income': 6000,
        'monthly_expenses': 3500,
        'monthly_savings': 1200,
        'monthly_debt_payment': 800,
        'emergency_fund': 12000,
        'total_debt': 25000,
        'total_investments': 45000,
        'budget_adherence': 85,
        'income_growth_rate': 5.5,
        'income_stability': 90,
        'portfolio_diversification': 70
    }


class TestEmergencyFundScore:
    """Tests for emergency fund scoring"""
    
    def test_excellent_emergency_fund(self, service):
        """Test scoring with 6+ months of expenses"""
        data = {
            'monthly_expenses': 3000,
            'emergency_fund': 18000  # 6 months
        }
        factor = service._calculate_emergency_fund_score(data)
        
        assert factor.score == 100
        assert factor.category == FactorCategory.EMERGENCY_FUND
        assert factor.current_value == 6.0
        assert factor.status == HealthScoreLevel.EXCELLENT
    
    def test_good_emergency_fund(self, service):
        """Test scoring with 3-6 months of expenses"""
        data = {
            'monthly_expenses': 3000,
            'emergency_fund': 12000  # 4 months
        }
        factor = service._calculate_emergency_fund_score(data)
        
        assert 60 < factor.score < 100
        assert factor.current_value == 4.0
    
    def test_poor_emergency_fund(self, service):
        """Test scoring with less than 1 month"""
        data = {
            'monthly_expenses': 3000,
            'emergency_fund': 1500  # 0.5 months
        }
        factor = service._calculate_emergency_fund_score(data)
        
        assert factor.score < 30
        assert factor.current_value == 0.5


class TestDebtScore:
    """Tests for debt scoring"""
    
    def test_excellent_debt_ratio(self, service):
        """Test scoring with low debt-to-income ratio"""
        data = {
            'monthly_income': 6000,
            'monthly_debt_payment': 600,  # 10% DTI
            'total_debt': 10000
        }
        factor = service._calculate_debt_score(data)
        
        assert factor.score == 100
        assert factor.current_value == 10.0
    
    def test_poor_debt_ratio(self, service):
        """Test scoring with high debt-to-income ratio"""
        data = {
            'monthly_income': 6000,
            'monthly_debt_payment': 3000,  # 50% DTI
            'total_debt': 100000
        }
        factor = service._calculate_debt_score(data)
        
        assert factor.score < 30
        assert factor.current_value == 50.0


class TestSavingsScore:
    """Tests for savings rate scoring"""
    
    def test_excellent_savings_rate(self, service):
        """Test scoring with 20%+ savings rate"""
        data = {
            'monthly_income': 6000,
            'monthly_savings': 1500  # 25%
        }
        factor = service._calculate_savings_score(data)
        
        assert factor.score == 100
        assert factor.current_value == 25.0
    
    def test_poor_savings_rate(self, service):
        """Test scoring with low savings rate"""
        data = {
            'monthly_income': 6000,
            'monthly_savings': 150  # 2.5%
        }
        factor = service._calculate_savings_score(data)
        
        assert factor.score < 30


class TestOverallScore:
    """Tests for overall score calculation"""
    
    @pytest.mark.asyncio
    async def test_calculate_health_score(self, service, sample_financial_data):
        """Test complete health score calculation"""
        score = await service.calculate_health_score(
            user_id="test_user",
            financial_data=sample_financial_data
        )
        
        assert 0 <= score.overall_score <= 100
        assert len(score.factors) == 6  # All 6 factors
        assert score.user_id == "test_user"
        assert score.level in [
            HealthScoreLevel.CRITICAL,
            HealthScoreLevel.POOR,
            HealthScoreLevel.FAIR,
            HealthScoreLevel.GOOD,
            HealthScoreLevel.EXCELLENT
        ]
    
    @pytest.mark.asyncio
    async def test_factor_weights_sum_to_one(self, service, sample_financial_data):
        """Test that factor weights sum to 1.0"""
        score = await service.calculate_health_score(
            user_id="test_user",
            financial_data=sample_financial_data
        )
        
        total_weight = sum(factor.weight for factor in score.factors)
        assert abs(total_weight - 1.0) < 0.001  # Allow for floating point errors


class TestImprovements:
    """Tests for improvement recommendations"""
    
    @pytest.mark.asyncio
    async def test_generates_improvements(self, service, sample_financial_data):
        """Test that improvements are generated"""
        score = await service.calculate_health_score(
            user_id="test_user",
            financial_data=sample_financial_data
        )
        
        assert len(score.improvements) > 0
        for improvement in score.improvements:
            assert improvement.title
            assert improvement.description
            assert len(improvement.action_steps) > 0
            assert 1 <= improvement.priority <= 5


class TestScoreHistory:
    """Tests for score history"""
    
    @pytest.mark.asyncio
    async def test_get_score_history(self, service):
        """Test fetching score history"""
        history = await service.get_score_history(
            user_id="test_user",
            days=90
        )
        
        assert len(history.trends) == 90
        assert history.average_score > 0
        assert history.highest_score >= history.average_score
        assert history.lowest_score <= history.average_score

