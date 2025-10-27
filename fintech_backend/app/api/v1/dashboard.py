"""
Dashboard API endpoints for financial summaries, analytics, and notifications.
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, Body, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from datetime import datetime, UTC

from ..models.dashboard import (
    DashboardSummaryResponse,
    AnalyticsResponse, 
    NotificationsResponse,
    NotificationMarkReadRequest,
    NotificationMarkReadResponse,
    NotificationType
)
from ..services.dashboard_service import get_dashboard_service, get_notification_service
from ..utils.validators import validate_user_id
from ..core.middleware import get_rate_limiter
from ..core.exceptions import ValidationException
from ..core.auth import get_current_user
from ..config.logging import get_logger

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
limiter = get_rate_limiter()
logger = get_logger(__name__)


@router.get(
    "",
    response_model=DashboardSummaryResponse,
    summary="Get Current User Dashboard",
    description="Retrieve dashboard summary for the authenticated user"
)
@limiter.limit("30/minute")
async def get_current_user_dashboard(
    request: Request,
    current_user = Depends(get_current_user),
    include_pending: bool = Query(default=True, description="Include pending transactions"),
    date_range_days: int = Query(default=30, ge=1, le=365, description="Date range for recent data"),
    dashboard_service = Depends(get_dashboard_service)
):
    """
    Get dashboard summary for the authenticated user.
    
    Returns financial overview, recent activity, notifications count, and quick stats.
    
    - **include_pending**: Whether to include pending transactions in recent activity
    - **date_range_days**: Number of days to look back for recent data (1-365)
    """
    try:
        # Get dashboard summary for current user
        result = await dashboard_service.get_dashboard_summary(
            user_id=current_user["user_id"],
            include_pending=include_pending,
            date_range_days=date_range_days
        )
        
        return result
        
    except ValidationException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/summary/{user_id}",
    response_model=DashboardSummaryResponse,
    summary="Get Dashboard Summary",
    description="Retrieve comprehensive dashboard summary including balances, recent activity, and alerts"
)
@limiter.limit("30/minute")
async def get_dashboard_summary(
    request: Request,
    user_id: str,
    include_pending: bool = Query(default=True, description="Include pending transactions"),
    date_range_days: int = Query(default=30, ge=1, le=365, description="Date range for recent data"),
    dashboard_service = Depends(get_dashboard_service)
):
    """
    Get dashboard summary for a user.
    
    Returns financial overview, recent activity, notifications count, and quick stats.
    
    - **user_id**: User identifier
    - **include_pending**: Whether to include pending transactions in recent activity
    - **date_range_days**: Number of days to look back for recent data (1-365)
    """
    try:
        # Validate user ID
        validated_user_id = validate_user_id(user_id)
        
        # Get dashboard summary
        result = await dashboard_service.get_dashboard_summary(
            user_id=validated_user_id,
            include_pending=include_pending,
            date_range_days=date_range_days
        )
        
        return result
        
    except ValidationException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/analytics/{user_id}",
    response_model=AnalyticsResponse,
    summary="Get Spending Analytics",
    description="Retrieve detailed spending analytics with category breakdown and trends"
)
@limiter.limit("20/minute")
async def get_spending_analytics(
    request: Request,
    user_id: str,
    period_days: int = Query(default=30, ge=1, le=365, description="Analysis period in days"),
    category_filter: Optional[str] = Query(default=None, description="Comma-separated list of categories to filter"),
    include_trends: bool = Query(default=True, description="Include monthly trend analysis"),
    dashboard_service = Depends(get_dashboard_service)
):
    """
    Get detailed spending analytics for a user.
    
    Returns spending breakdown by category, monthly trends, and insights.
    
    - **user_id**: User identifier
    - **period_days**: Number of days to analyze (1-365)
    - **category_filter**: Optional comma-separated categories to filter by
    - **include_trends**: Whether to include monthly spending trends
    """
    try:
        # Validate user ID
        validated_user_id = validate_user_id(user_id)
        
        # Parse category filter
        categories = None
        if category_filter:
            categories = [cat.strip() for cat in category_filter.split(",") if cat.strip()]
        
        # Get analytics
        result = await dashboard_service.get_spending_analytics(
            user_id=validated_user_id,
            period_days=period_days,
            category_filter=categories,
            include_trends=include_trends
        )
        
        return result
        
    except ValidationException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/notifications/{user_id}",
    response_model=NotificationsResponse,
    summary="Get User Notifications",
    description="Retrieve user notifications with filtering options"
)
@limiter.limit("40/minute")
async def get_notifications(
    request: Request,
    user_id: str,
    unread_only: bool = Query(default=False, description="Return only unread notifications"),
    notification_type: Optional[NotificationType] = Query(default=None, description="Filter by notification type"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum number of notifications"),
    dashboard_service = Depends(get_dashboard_service)
):
    """
    Get notifications for a user.
    
    Returns list of notifications with filtering and pagination options.
    
    - **user_id**: User identifier
    - **unread_only**: Whether to return only unread notifications
    - **notification_type**: Optional notification type filter
    - **limit**: Maximum number of notifications to return (1-100)
    """
    try:
        # Validate user ID
        validated_user_id = validate_user_id(user_id)
        
        # Get notifications
        result = await dashboard_service.get_notifications(
            user_id=validated_user_id,
            unread_only=unread_only,
            notification_type=notification_type.value if notification_type else None,
            limit=limit
        )
        
        return result
        
    except ValidationException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/notifications/{user_id}/mark-read",
    response_model=NotificationMarkReadResponse,
    summary="Mark Notifications as Read",
    description="Mark one or more notifications as read"
)
@limiter.limit("20/minute")
async def mark_notifications_read(
    request: Request,
    user_id: str,
    request_body: NotificationMarkReadRequest = Body(..., description="Notification IDs to mark as read"),
    dashboard_service = Depends(get_dashboard_service)
):
    """
    Mark notifications as read for a user.
    
    Updates the read status of specified notifications.
    
    - **user_id**: User identifier
    - **notification_ids**: List of notification IDs to mark as read
    """
    try:
        # Validate user ID
        validated_user_id = validate_user_id(user_id)
        
        # Mark notifications as read
        result = await dashboard_service.mark_notifications_read(
            user_id=validated_user_id,
            notification_ids=request_body.notification_ids
        )
        
        return result
        
    except ValidationException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/welcome",
    summary="Welcome Endpoint",
    description="Returns a welcome message with request logging"
)
async def welcome_endpoint(request: Request):
    """
    Welcome endpoint that logs request metadata and returns a welcome message.

    Returns a JSON response with a welcome message.
    Request metadata (method and path) is logged for monitoring.
    """
    # Log request metadata
    logger.info(
        f"Welcome endpoint accessed: {request.method} {request.url.path}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "user_agent": request.headers.get("user-agent", "unknown"),
            "client_ip": request.client.host if request.client else "unknown"
        }
    )

    return {
        "message": "Welcome to the FastAPI Service!",
        "timestamp": datetime.now(UTC).isoformat()
    }


@router.get(
    "/health-check",
    summary="Dashboard Service Health Check",
    description="Check the health of dashboard-related services"
)
async def dashboard_health_check():
    """
    Health check for dashboard services.

    Verifies that dashboard services are operational.
    """
    try:
        # Basic service health check
        dashboard_service = get_dashboard_service()
        notification_service = get_notification_service()

        # Test basic repository connectivity
        test_accounts = await dashboard_service.accounts_repo.count()
        test_notifications = await notification_service.notifications_repo.count()

        # Count unique users from accounts
        all_accounts = await dashboard_service.accounts_repo.get_all(limit=1000)
        unique_users = len(set(acc.get("user_id") for acc in all_accounts if acc.get("user_id")))

        return {
            "status": "healthy",
            "service": "dashboard",
            "checks": {
                "accounts_repository": "ok",
                "notifications_repository": "ok",
                "total_users": unique_users,
                "total_accounts": test_accounts,
                "total_notifications": test_notifications
            },
            "timestamp": datetime.now(UTC).isoformat()
        }

    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Dashboard service unhealthy: {str(e)}"
        )
