"""
Smart Notification Service
Generates intelligent decision nudges based on user financial behavior
"""

import uuid
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any
from decimal import Decimal
from sqlalchemy.orm import Session

from ..models.smart_notifications import (
    SmartNotificationProfile, SmartNotificationType, NudgePriority, NudgeAction,
    SurplusDetectionResult, OverspendingAnalysis, InvestmentOpportunityProfile,
    GoalProgressNudge, SmartNotificationSettings, SmartNotificationCreateRequest
)
from ..models.analytics import TransactionCategory
from ..services.analytics_service import AnalyticsService
from ..services.savings_service import SavingsService
from ..config.logging import get_logger

logger = get_logger(__name__)


class SmartNotificationService:
    """Service for generating and managing smart financial notifications"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.analytics_service = AnalyticsService(db_session)
        self.savings_service = SavingsService()
        self._notifications_cache: Dict[str, List[SmartNotificationProfile]] = {}
    
    async def generate_smart_notifications(self, user_id: str) -> List[SmartNotificationProfile]:
        """Generate all smart notifications for a user"""
        notifications = []
        
        # Get user settings
        settings = await self._get_user_settings(user_id)
        if not settings.enabled:
            return []
        
        # Generate different types of nudges
        if settings.surplus_notifications:
            surplus_nudges = await self._generate_surplus_nudges(user_id, settings)
            notifications.extend(surplus_nudges)
        
        if settings.overspending_notifications:
            overspending_nudges = await self._generate_overspending_nudges(user_id, settings)
            notifications.extend(overspending_nudges)
        
        if settings.goal_notifications:
            goal_nudges = await self._generate_goal_nudges(user_id, settings)
            notifications.extend(goal_nudges)
        
        if settings.investment_notifications:
            investment_nudges = await self._generate_investment_nudges(user_id, settings)
            notifications.extend(investment_nudges)
        
        if settings.savings_notifications:
            savings_nudges = await self._generate_savings_nudges(user_id, settings)
            notifications.extend(savings_nudges)
        
        # Limit to max daily nudges
        notifications = self._prioritize_and_limit(notifications, settings.max_daily_nudges)
        
        # Cache notifications
        self._notifications_cache[user_id] = notifications
        
        return notifications
    
    async def _generate_surplus_nudges(
        self, 
        user_id: str, 
        settings: SmartNotificationSettings
    ) -> List[SmartNotificationProfile]:
        """Detect surplus cash and generate investment/savings nudges"""
        nudges = []
        
        # Analyze cash flow
        surplus_result = await self._detect_surplus(user_id, settings.min_surplus_amount)
        
        if surplus_result.has_surplus and surplus_result.surplus_amount >= settings.min_surplus_amount:
            # Create surplus notification
            nudge = SmartNotificationProfile(
                id=str(uuid.uuid4()),
                user_id=user_id,
                type=SmartNotificationType.SURPLUS_DETECTED,
                title=f"💰 You have ${surplus_result.surplus_amount:.2f} available to invest or save",
                message=f"Great news! Based on your spending patterns, you have a surplus of ${surplus_result.surplus_amount:.2f}. "
                        f"{surplus_result.reasoning}",
                priority=NudgePriority.HIGH if surplus_result.surplus_amount > 500 else NudgePriority.MEDIUM,
                recommended_action=NudgeAction.INVEST_NOW if surplus_result.surplus_amount > 1000 else NudgeAction.SAVE_NOW,
                action_details={
                    "surplus_amount": float(surplus_result.surplus_amount),
                    "recommended_allocation": {k: float(v) for k, v in surplus_result.recommended_allocation.items()},
                    "confidence": surplus_result.confidence_score
                },
                amount=surplus_result.surplus_amount,
                is_read=False,
                is_acted_upon=False,
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=7)
            )
            nudges.append(nudge)
        
        return nudges
    
    async def _generate_overspending_nudges(
        self, 
        user_id: str, 
        settings: SmartNotificationSettings
    ) -> List[SmartNotificationProfile]:
        """Generate nudges for overspending patterns"""
        nudges = []
        
        # Analyze spending vs budgets
        overspending_analysis = await self._analyze_overspending(user_id, settings.overspending_threshold_percentage)
        
        if overspending_analysis.is_overspending:
            nudge = SmartNotificationProfile(
                id=str(uuid.uuid4()),
                user_id=user_id,
                type=SmartNotificationType.OVERSPENDING_WARNING,
                title=f"⚠️ You're {overspending_analysis.percentage_over:.0f}% over budget in {overspending_analysis.category}",
                message=f"You've spent ${overspending_analysis.amount_over_budget:.2f} more than budgeted in {overspending_analysis.category}. "
                        f"Consider reducing spending by ${overspending_analysis.suggested_reduction:.2f} to stay on track.",
                priority=NudgePriority.URGENT if overspending_analysis.percentage_over > 120 else NudgePriority.HIGH,
                recommended_action=NudgeAction.REDUCE_SPENDING,
                action_details={
                    "category": overspending_analysis.category,
                    "amount_over": float(overspending_analysis.amount_over_budget),
                    "suggested_reduction": float(overspending_analysis.suggested_reduction),
                    "alternatives": overspending_analysis.alternative_actions
                },
                amount=overspending_analysis.amount_over_budget,
                category=overspending_analysis.category,
                is_read=False,
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=3)
            )
            nudges.append(nudge)
        
        return nudges
    
    async def _generate_goal_nudges(
        self, 
        user_id: str, 
        settings: SmartNotificationSettings
    ) -> List[SmartNotificationProfile]:
        """Generate nudges for goal progress"""
        nudges = []
        
        # Get user goals
        user_goals = await self.savings_service.get_user_goals(user_id)
        
        for goal in user_goals:
            progress_nudge = await self._analyze_goal_progress(goal)
            
            if not progress_nudge.on_track and progress_nudge.days_remaining > 0:
                nudge = SmartNotificationProfile(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    type=SmartNotificationType.GOAL_PROGRESS_NUDGE,
                    title=f"🎯 Your '{progress_nudge.goal_name}' goal needs attention",
                    message=f"You're at {progress_nudge.current_progress:.1f}% of your goal with {progress_nudge.days_remaining} days left. "
                            f"{progress_nudge.suggested_action}",
                    priority=NudgePriority.MEDIUM,
                    recommended_action=NudgeAction.INCREASE_CONTRIBUTION,
                    action_details={
                        "goal_id": progress_nudge.goal_id,
                        "current_progress": progress_nudge.current_progress,
                        "suggested_amount": float(progress_nudge.suggested_amount) if progress_nudge.suggested_amount else None
                    },
                    goal_id=progress_nudge.goal_id,
                    amount=progress_nudge.suggested_amount,
                    is_read=False,
                    created_at=datetime.utcnow(),
                    expires_at=datetime.utcnow() + timedelta(days=7)
                )
                nudges.append(nudge)
        
        return nudges

    async def _generate_investment_nudges(
        self,
        user_id: str,
        settings: SmartNotificationSettings
    ) -> List[SmartNotificationProfile]:
        """Generate investment opportunity nudges"""
        nudges = []

        # Check if user has investable surplus
        surplus_result = await self._detect_surplus(user_id, Decimal("1000.00"))

        if surplus_result.has_surplus and surplus_result.surplus_amount >= 1000:
            nudge = SmartNotificationProfile(
                id=str(uuid.uuid4()),
                user_id=user_id,
                type=SmartNotificationType.INVESTMENT_OPPORTUNITY,
                title=f"📈 Ready to invest ${surplus_result.surplus_amount:.2f}?",
                message=f"You have ${surplus_result.surplus_amount:.2f} available. "
                        f"Consider investing to grow your wealth. Based on your risk profile, we recommend diversified options.",
                priority=NudgePriority.MEDIUM,
                recommended_action=NudgeAction.INVEST_NOW,
                action_details={
                    "amount": float(surplus_result.surplus_amount),
                    "investment_options": ["stocks", "bonds", "index_funds"],
                    "risk_level": "moderate"
                },
                amount=surplus_result.surplus_amount,
                is_read=False,
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=14)
            )
            nudges.append(nudge)

        return nudges

    async def _generate_savings_nudges(
        self,
        user_id: str,
        settings: SmartNotificationSettings
    ) -> List[SmartNotificationProfile]:
        """Generate savings opportunity nudges"""
        nudges = []

        # Check for emergency fund
        user_goals = await self.savings_service.get_user_goals(user_id)
        has_emergency_fund = any(goal.get("goal_type") == "emergency_fund" for goal in user_goals)

        if not has_emergency_fund:
            nudge = SmartNotificationProfile(
                id=str(uuid.uuid4()),
                user_id=user_id,
                type=SmartNotificationType.EMERGENCY_FUND_REMINDER,
                title="🛡️ Build your emergency fund",
                message="You don't have an emergency fund yet. Financial experts recommend saving 3-6 months of expenses. "
                        "Start with a small goal and build from there.",
                priority=NudgePriority.HIGH,
                recommended_action=NudgeAction.SET_GOAL,
                action_details={
                    "goal_type": "emergency_fund",
                    "recommended_months": 6,
                    "suggested_start_amount": 1000.00
                },
                is_read=False,
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=30)
            )
            nudges.append(nudge)

        return nudges

    # Helper methods

    async def _detect_surplus(self, user_id: str, min_amount: Decimal) -> SurplusDetectionResult:
        """Detect if user has surplus cash available"""
        # Get recent transactions (last 30 days)
        recent_date = date.today() - timedelta(days=30)
        transactions = await self.analytics_service._get_user_transactions(
            user_id, start_date=recent_date, include_income=True
        )

        # Calculate income and expenses
        total_income = sum(t.amount for t in transactions if t.is_income)
        total_expenses = sum(t.amount for t in transactions if not t.is_income)

        surplus = total_income - total_expenses
        has_surplus = surplus >= min_amount

        # Calculate confidence based on consistency
        confidence = 0.8 if len(transactions) > 10 else 0.5

        # Recommend allocation
        recommended_allocation = {
            "savings": surplus * Decimal("0.5"),
            "investment": surplus * Decimal("0.3"),
            "debt": surplus * Decimal("0.2")
        }

        reasoning = f"Based on your last 30 days, you earned ${total_income:.2f} and spent ${total_expenses:.2f}."

        return SurplusDetectionResult(
            has_surplus=has_surplus,
            surplus_amount=surplus if surplus > 0 else Decimal("0"),
            confidence_score=confidence,
            recommended_allocation=recommended_allocation,
            reasoning=reasoning
        )

    async def _analyze_overspending(
        self,
        user_id: str,
        threshold_percentage: float
    ) -> OverspendingAnalysis:
        """Analyze if user is overspending in any category"""
        # Get user budgets
        budgets = await self.analytics_service.get_user_budgets(user_id)

        for budget in budgets:
            if budget.percentage_used >= threshold_percentage:
                amount_over = budget.spent_amount - budget.budgeted_amount
                percentage_over = budget.percentage_used

                return OverspendingAnalysis(
                    is_overspending=True,
                    category=budget.category.value,
                    amount_over_budget=amount_over if amount_over > 0 else Decimal("0"),
                    percentage_over=percentage_over,
                    trend="increasing",  # TODO: Calculate actual trend
                    suggested_reduction=amount_over * Decimal("0.5") if amount_over > 0 else Decimal("0"),
                    alternative_actions=[
                        "Review recent transactions in this category",
                        "Set up spending alerts",
                        "Find cheaper alternatives"
                    ]
                )

        # No overspending detected
        return OverspendingAnalysis(
            is_overspending=False,
            category="",
            amount_over_budget=Decimal("0"),
            percentage_over=0.0,
            trend="stable",
            suggested_reduction=Decimal("0"),
            alternative_actions=[]
        )

    async def _analyze_goal_progress(self, goal: Dict[str, Any]) -> GoalProgressNudge:
        """Analyze progress towards a savings goal"""
        target_amount = Decimal(str(goal.get("target_amount", 0)))
        current_amount = Decimal(str(goal.get("current_amount", 0)))
        target_date = goal.get("target_date")

        progress = (current_amount / target_amount * 100) if target_amount > 0 else 0

        # Calculate days remaining
        if isinstance(target_date, str):
            target_date = datetime.fromisoformat(target_date).date()
        days_remaining = (target_date - date.today()).days if target_date else 0

        # Check if on track
        created_at = goal.get("created_at", datetime.utcnow())
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        days_elapsed = (date.today() - created_at.date()).days if hasattr(created_at, 'date') else 0
        total_days = days_elapsed + days_remaining
        expected_progress = (days_elapsed / max(total_days, 1)) * 100 if total_days > 0 else 100
        on_track = progress >= expected_progress * 0.9  # 90% of expected progress

        # Calculate suggested amount
        remaining_amount = target_amount - current_amount
        suggested_amount = remaining_amount / max(days_remaining / 30, 1) if days_remaining > 0 else remaining_amount

        suggested_action = (
            f"Increase your monthly contribution to ${suggested_amount:.2f} to reach your goal on time."
            if not on_track else
            "You're on track! Keep up the great work."
        )

        return GoalProgressNudge(
            goal_id=goal.get("id", ""),
            goal_name=goal.get("name", ""),
            current_progress=progress,
            target_amount=target_amount,
            current_amount=current_amount,
            days_remaining=days_remaining,
            on_track=on_track,
            suggested_action=suggested_action,
            suggested_amount=suggested_amount if not on_track else None
        )

    async def _get_user_settings(self, user_id: str) -> SmartNotificationSettings:
        """Get user's smart notification settings"""
        # TODO: Fetch from database
        # For now, return default settings
        return SmartNotificationSettings(
            user_id=user_id,
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

    def _prioritize_and_limit(
        self,
        notifications: List[SmartNotificationProfile],
        max_count: int
    ) -> List[SmartNotificationProfile]:
        """Prioritize notifications and limit to max count"""
        # Sort by priority (URGENT > HIGH > MEDIUM > LOW)
        priority_order = {
            NudgePriority.URGENT: 0,
            NudgePriority.HIGH: 1,
            NudgePriority.MEDIUM: 2,
            NudgePriority.LOW: 3
        }

        sorted_notifications = sorted(
            notifications,
            key=lambda n: priority_order.get(n.priority, 999)
        )

        return sorted_notifications[:max_count]

    async def get_user_notifications(self, user_id: str) -> List[SmartNotificationProfile]:
        """Get all smart notifications for a user"""
        # Check cache first
        if user_id in self._notifications_cache:
            return self._notifications_cache[user_id]

        # Generate new notifications
        return await self.generate_smart_notifications(user_id)

    async def mark_notification_read(self, notification_id: str, user_id: str) -> bool:
        """Mark a notification as read"""
        if user_id in self._notifications_cache:
            for notification in self._notifications_cache[user_id]:
                if notification.id == notification_id:
                    notification.is_read = True
                    return True
        return False

    async def mark_notification_acted_upon(self, notification_id: str, user_id: str) -> bool:
        """Mark a notification as acted upon"""
        if user_id in self._notifications_cache:
            for notification in self._notifications_cache[user_id]:
                if notification.id == notification_id:
                    notification.is_acted_upon = True
                    notification.action_taken_at = datetime.utcnow()
                    return True
        return False

