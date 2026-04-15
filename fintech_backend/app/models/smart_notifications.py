"""
DEPRECATED: smart_notifications.py has been merged into notifications.py.

All smart notification models are now in app.models.notifications.
This module re-exports them for backward compatibility.
"""
from app.models.notifications import (  # noqa: F401
    SmartNotificationType,
    NudgeAction,
    SmartMetadata,
    SmartNotificationProfile,
    SmartNotificationSettings,
    SmartNotificationCreateRequest,
    SmartNotificationResponse,
    SurplusDetectionResult,
    OverspendingAnalysis,
    InvestmentOpportunityProfile,
    GoalProgressNudge,
)

# Legacy alias kept for any code that imported NudgePriority from here
from app.models.notifications import NotificationPriority as NudgePriority  # noqa: F401
