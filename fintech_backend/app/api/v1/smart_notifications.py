"""
Smart Notifications API Endpoints
Decision nudges and intelligent financial notifications
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from ...core.database import get_db
from ...core.auth import get_current_user
from ...models.auth import User
from ...models.smart_notifications import (
    SmartNotificationProfile, SmartNotificationResponse,
    SmartNotificationSettings
)
from ...services.smart_notification_service import SmartNotificationService
from ...config.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/smart-notifications", tags=["Smart Notifications"])


@router.get("/", response_model=SmartNotificationResponse)
async def get_smart_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all smart notifications (decision nudges) for the current user
    
    Returns intelligent, actionable financial recommendations based on:
    - Surplus cash detection
    - Overspending patterns
    - Goal progress
    - Investment opportunities
    - Savings recommendations
    """
    try:
        service = SmartNotificationService(db)
        notifications = await service.get_user_notifications(current_user.user_id)
        
        unread_count = sum(1 for n in notifications if not n.is_read)
        high_priority_count = sum(1 for n in notifications if n.priority in ["high", "urgent"])
        
        return SmartNotificationResponse(
            notifications=notifications,
            total_count=len(notifications),
            unread_count=unread_count,
            high_priority_count=high_priority_count
        )
    except Exception as e:
        logger.error(f"Error fetching smart notifications for user {current_user.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch smart notifications"
        )


@router.post("/generate", response_model=SmartNotificationResponse)
async def generate_smart_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Force generation of new smart notifications
    
    Analyzes current financial state and generates fresh decision nudges
    """
    try:
        service = SmartNotificationService(db)
        notifications = await service.generate_smart_notifications(current_user.user_id)
        
        unread_count = sum(1 for n in notifications if not n.is_read)
        high_priority_count = sum(1 for n in notifications if n.priority in ["high", "urgent"])
        
        return SmartNotificationResponse(
            notifications=notifications,
            total_count=len(notifications),
            unread_count=unread_count,
            high_priority_count=high_priority_count
        )
    except Exception as e:
        logger.error(f"Error generating smart notifications for user {current_user.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate smart notifications"
        )


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a smart notification as read"""
    try:
        service = SmartNotificationService(db)
        success = await service.mark_notification_read(notification_id, current_user.user_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        return {"success": True, "message": "Notification marked as read"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking notification {notification_id} as read: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark notification as read"
        )


@router.post("/{notification_id}/acted")
async def mark_notification_acted_upon(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a smart notification as acted upon"""
    try:
        service = SmartNotificationService(db)
        success = await service.mark_notification_acted_upon(notification_id, current_user.user_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        return {"success": True, "message": "Notification marked as acted upon"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking notification {notification_id} as acted upon: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark notification as acted upon"
        )


@router.get("/settings", response_model=SmartNotificationSettings)
async def get_notification_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's smart notification settings"""
    try:
        service = SmartNotificationService(db)
        settings = await service._get_user_settings(current_user.user_id)
        return settings
    except Exception as e:
        logger.error(f"Error fetching notification settings for user {current_user.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch notification settings"
        )

