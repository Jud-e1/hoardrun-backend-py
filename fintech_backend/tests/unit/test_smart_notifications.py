"""
Unit tests for Smart Notifications Service
Tests the intelligent decision nudge generation system
"""

import pytest
from datetime import datetime, timedelta, date
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch

from ...app.services.smart_notification_service import SmartNotificationService
from ...app.models.smart_notifications import (
    SmartNotificationType, NudgePriority, NudgeAction,
    SmartNotificationSettings, SurplusDetectionResult
)


class TestSmartNotificationService:
    """Test suite for SmartNotificationService"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session"""
        return Mock()
    
    @pytest.fixture
    def service(self, mock_db_session):
        """Create a SmartNotificationService instance"""
        return SmartNotificationService(mock_db_session)
    
    @pytest.fixture
    def default_settings(self):
        """Default notification settings"""
        return SmartNotificationSettings(
            user_id="test_user_001",
            enabled=True,
            surplus_notifications=True,
            investment_notifications=True,
            overspending_notifications=True,
            goal_notifications=True,
            savings_notifications=True,
            max_daily_nudges=5,
            min_surplus_amount=Decimal("50.00"),
            overspending_threshold_percentage=80.0,
            updated_at=datetime.utcnow()
        )
    
    @pytest.mark.asyncio
    async def test_surplus_detection_with_surplus(self, service):
        """Test surplus detection when user has surplus cash"""
        # Mock analytics data showing surplus
        mock_income = Decimal("5000.00")
        mock_expenses = Decimal("3500.00")
        
        with patch.object(service.analytics_service, 'get_cash_flow_summary', new_callable=AsyncMock) as mock_cash_flow:
            mock_cash_flow.return_value = {
                "total_income": mock_income,
                "total_expenses": mock_expenses,
                "net_cash_flow": mock_income - mock_expenses
            }
            
            result = await service._detect_surplus("test_user_001", 30)
            
            assert result.has_surplus is True
            assert result.surplus_amount == Decimal("1500.00")
            assert result.confidence_score > 0.5
            assert "savings" in result.recommended_allocation
            assert "investment" in result.recommended_allocation
    
    @pytest.mark.asyncio
    async def test_surplus_detection_no_surplus(self, service):
        """Test surplus detection when user has no surplus"""
        mock_income = Decimal("3000.00")
        mock_expenses = Decimal("3200.00")
        
        with patch.object(service.analytics_service, 'get_cash_flow_summary', new_callable=AsyncMock) as mock_cash_flow:
            mock_cash_flow.return_value = {
                "total_income": mock_income,
                "total_expenses": mock_expenses,
                "net_cash_flow": mock_income - mock_expenses
            }
            
            result = await service._detect_surplus("test_user_001", 30)
            
            assert result.has_surplus is False
            assert result.surplus_amount <= 0
    
    @pytest.mark.asyncio
    async def test_generate_surplus_nudges(self, service, default_settings):
        """Test generation of surplus nudges"""
        with patch.object(service, '_detect_surplus', new_callable=AsyncMock) as mock_detect:
            mock_detect.return_value = SurplusDetectionResult(
                has_surplus=True,
                surplus_amount=Decimal("1250.00"),
                confidence_score=0.85,
                recommended_allocation={
                    "savings": Decimal("625.00"),
                    "investment": Decimal("375.00"),
                    "debt": Decimal("250.00")
                },
                reasoning="Based on your last 30 days, you earned $5,000.00 and spent $3,750.00."
            )
            
            nudges = await service._generate_surplus_nudges("test_user_001", default_settings)
            
            assert len(nudges) > 0
            nudge = nudges[0]
            assert nudge.type == SmartNotificationType.SURPLUS_DETECTED
            assert nudge.priority in [NudgePriority.HIGH, NudgePriority.MEDIUM]
            assert nudge.recommended_action in [NudgeAction.INVEST_NOW, NudgeAction.SAVE_NOW]
            assert "1250" in nudge.title or "1,250" in nudge.title
    
    @pytest.mark.asyncio
    async def test_notification_prioritization(self, service):
        """Test that notifications are properly prioritized"""
        from ...app.models.smart_notifications import SmartNotificationProfile
        
        notifications = [
            SmartNotificationProfile(
                id="1", user_id="test", type=SmartNotificationType.SURPLUS_DETECTED,
                title="Test", message="Test", priority=NudgePriority.LOW,
                recommended_action=NudgeAction.SAVE_NOW, action_details={},
                created_at=datetime.utcnow()
            ),
            SmartNotificationProfile(
                id="2", user_id="test", type=SmartNotificationType.OVERSPENDING_WARNING,
                title="Test", message="Test", priority=NudgePriority.URGENT,
                recommended_action=NudgeAction.REDUCE_SPENDING, action_details={},
                created_at=datetime.utcnow()
            ),
            SmartNotificationProfile(
                id="3", user_id="test", type=SmartNotificationType.GOAL_PROGRESS_NUDGE,
                title="Test", message="Test", priority=NudgePriority.HIGH,
                recommended_action=NudgeAction.INCREASE_CONTRIBUTION, action_details={},
                created_at=datetime.utcnow()
            )
        ]
        
        prioritized = service._prioritize_and_limit(notifications, max_nudges=5)
        
        # Check that URGENT comes first
        assert prioritized[0].priority == NudgePriority.URGENT
        assert prioritized[1].priority == NudgePriority.HIGH
        assert prioritized[2].priority == NudgePriority.LOW
    
    @pytest.mark.asyncio
    async def test_max_daily_nudges_limit(self, service):
        """Test that daily nudge limit is enforced"""
        from ...app.models.smart_notifications import SmartNotificationProfile
        
        # Create 10 notifications
        notifications = [
            SmartNotificationProfile(
                id=str(i), user_id="test", type=SmartNotificationType.SURPLUS_DETECTED,
                title=f"Test {i}", message="Test", priority=NudgePriority.MEDIUM,
                recommended_action=NudgeAction.SAVE_NOW, action_details={},
                created_at=datetime.utcnow()
            )
            for i in range(10)
        ]
        
        # Limit to 3
        limited = service._prioritize_and_limit(notifications, max_nudges=3)
        
        assert len(limited) == 3

