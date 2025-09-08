from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional, Dict, Any
from datetime import datetime

from ...core.auth import get_current_user
from ...models.notifications import (
    NotificationCreateRequest, NotificationUpdateRequest, BulkNotificationUpdateRequest,
    NotificationPreferencesRequest, NotificationFilters,
    NotificationProfile, NotificationSummary, NotificationPreferencesProfile,
    NotificationStats, NotificationType, NotificationPriority, NotificationStatus,
    NotificationChannel
)
from ...services.notifications_service import NotificationsService
from ...core.exceptions import NotFoundError, ValidationError, BusinessLogicError

router = APIRouter(prefix="/notifications", tags=["notifications"])
notifications_service = NotificationsService()

@router.get("/", response_model=List[NotificationProfile])
async def get_notifications(
    type: Optional[NotificationType] = Query(None, description="Filter by notification type"),
    status: Optional[NotificationStatus] = Query(None, description="Filter by notification status"),
    priority: Optional[NotificationPriority] = Query(None, description="Filter by notification priority"),
    channel: Optional[NotificationChannel] = Query(None, description="Filter by notification channel"),
    date_from: Optional[datetime] = Query(None, description="Filter notifications from this date"),
    date_to: Optional[datetime] = Query(None, description="Filter notifications to this date"),
    unread_only: bool = Query(False, description="Show only unread notifications"),
    skip: int = Query(0, ge=0, description="Number of notifications to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of notifications to return"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get user notifications with optional filtering and pagination.
    
    - **type**: Filter by notification type (transaction, security, account, etc.)
    - **status**: Filter by status (unread, read, archived)
    - **priority**: Filter by priority (low, medium, high, urgent)
    - **channel**: Filter by delivery channel (in_app, email, sms, push)
    - **date_from**: Show notifications from this date onwards
    - **date_to**: Show notifications up to this date
    - **unread_only**: Show only unread notifications
    - **skip**: Number of notifications to skip for pagination
    - **limit**: Maximum number of notifications to return (1-100)
    """
    try:
        filters = NotificationFilters(
            type=type,
            status=status,
            priority=priority,
            channel=channel,
            date_from=date_from,
            date_to=date_to,
            unread_only=unread_only
        )
        
        notifications = await notifications_service.get_notifications(
            user_id=current_user["user_id"],
            filters=filters,
            skip=skip,
            limit=limit
        )
        
        return notifications
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve notifications: {str(e)}"
        )

@router.get("/summary", response_model=NotificationSummary)
async def get_notification_summary(
    current_user: dict = Depends(get_current_user)
):
    """
    Get notification summary including counts by type, priority, and recent notifications.
    
    Returns:
    - Total notification counts
    - Breakdown by type and priority
    - Recent notifications
    """
    try:
        summary = await notifications_service.get_notification_summary(
            user_id=current_user["user_id"]
        )
        return summary
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve notification summary: {str(e)}"
        )

@router.post("/", response_model=NotificationProfile, status_code=status.HTTP_201_CREATED)
async def create_notification(
    request: NotificationCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new notification for the current user.
    
    - **title**: Notification title (1-200 characters)
    - **message**: Notification message (1-1000 characters)
    - **type**: Notification type (transaction, security, account, etc.)
    - **priority**: Priority level (low, medium, high, urgent)
    - **channels**: Delivery channels (in_app, email, sms, push)
    - **metadata**: Optional additional data
    - **scheduled_at**: Optional scheduled delivery time
    - **expires_at**: Optional expiration time
    """
    try:
        notification = await notifications_service.create_notification(
            user_id=current_user["user_id"],
            request=request
        )
        return notification
    except BusinessLogicError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create notification: {str(e)}"
        )

@router.put("/{notification_id}", response_model=NotificationProfile)
async def update_notification(
    notification_id: str,
    request: NotificationUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Update a notification (typically to mark as read/archived).
    
    - **status**: New notification status (read, archived)
    - **read_at**: Optional timestamp when notification was read
    """
    try:
        notification = await notifications_service.update_notification(
            user_id=current_user["user_id"],
            notification_id=notification_id,
            request=request
        )
        return notification
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update notification: {str(e)}"
        )

@router.put("/bulk-update", response_model=Dict[str, str])
async def bulk_update_notifications(
    request: BulkNotificationUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Bulk update multiple notifications at once.
    
    - **notification_ids**: List of notification IDs to update (1-100)
    - **status**: New status to apply to all notifications
    
    Returns a dictionary mapping notification IDs to their update status:
    - "updated": Successfully updated
    - "not_found": Notification not found
    - "error": Update failed
    """
    try:
        results = await notifications_service.bulk_update_notifications(
            user_id=current_user["user_id"],
            request=request
        )
        return results
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to bulk update notifications: {str(e)}"
        )

@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a notification permanently.
    
    This action cannot be undone.
    """
    try:
        await notifications_service.delete_notification(
            user_id=current_user["user_id"],
            notification_id=notification_id
        )
        return None
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete notification: {str(e)}"
        )

@router.get("/preferences", response_model=NotificationPreferencesProfile)
async def get_notification_preferences(
    current_user: dict = Depends(get_current_user)
):
    """
    Get user notification preferences.
    
    Returns current settings for:
    - Notification types (transaction, security, etc.)
    - Delivery channels (email, SMS, push)
    - Quiet hours and timezone
    """
    try:
        preferences = await notifications_service.get_notification_preferences(
            user_id=current_user["user_id"]
        )
        return preferences
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve notification preferences: {str(e)}"
        )

@router.put("/preferences", response_model=NotificationPreferencesProfile)
async def update_notification_preferences(
    request: NotificationPreferencesRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Update user notification preferences.
    
    Configure which types of notifications to receive and through which channels:
    - **transaction_notifications**: Enable/disable transaction notifications
    - **security_notifications**: Enable/disable security alerts
    - **account_notifications**: Enable/disable account-related notifications
    - **payment_notifications**: Enable/disable payment notifications
    - **savings_notifications**: Enable/disable savings-related notifications
    - **kyc_notifications**: Enable/disable KYC notifications
    - **system_notifications**: Enable/disable system notifications
    - **marketing_notifications**: Enable/disable marketing communications
    - **reminder_notifications**: Enable/disable reminder notifications
    - **email_enabled**: Enable/disable email delivery
    - **sms_enabled**: Enable/disable SMS delivery
    - **push_enabled**: Enable/disable push notifications
    - **quiet_hours_start**: Start time for quiet hours (HH:MM format)
    - **quiet_hours_end**: End time for quiet hours (HH:MM format)
    - **timezone**: User timezone
    """
    try:
        preferences = await notifications_service.update_notification_preferences(
            user_id=current_user["user_id"],
            request=request
        )
        return preferences
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update notification preferences: {str(e)}"
        )

@router.get("/stats", response_model=NotificationStats)
async def get_notification_stats(
    current_user: dict = Depends(get_current_user)
):
    """
    Get notification delivery statistics.
    
    Returns:
    - Total notifications sent, delivered, and failed
    - Delivery rate percentage
    - Breakdown by channel and notification type
    - Recent delivery activity
    """
    try:
        stats = await notifications_service.get_notification_stats(
            user_id=current_user["user_id"]
        )
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve notification stats: {str(e)}"
        )

@router.get("/health", response_model=Dict[str, Any])
async def get_notifications_health():
    """
    Get notifications service health status.
    
    Returns service health metrics and status information.
    """
    try:
        health_status = await notifications_service.get_health_status()
        return health_status
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve health status: {str(e)}"
        )
