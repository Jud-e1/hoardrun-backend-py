from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import uuid
from ..models.notifications import (
    NotificationDB, NotificationPreferencesDB, NotificationDeliveryDB,
    NotificationCreateRequest, NotificationUpdateRequest, BulkNotificationUpdateRequest,
    NotificationPreferencesRequest, NotificationFilters,
    NotificationProfile, NotificationSummary, NotificationPreferencesProfile,
    NotificationDeliveryStatus, NotificationStats,
    NotificationType, NotificationPriority, NotificationStatus, NotificationChannel
)
from ..core.exceptions import NotFoundError, ValidationError, BusinessLogicError
from ..core.websocket import broadcast_notification

class NotificationsService:
    def __init__(self):
        # Mock data storage
        self.notifications: Dict[str, NotificationDB] = {}
        self.preferences: Dict[str, NotificationPreferencesDB] = {}
        self.deliveries: Dict[str, NotificationDeliveryDB] = {}
        self._initialize_mock_data()
    
    def _initialize_mock_data(self):
        """Initialize with sample notifications and preferences"""
        # Sample user preferences
        user_id = "user_123"
        prefs_id = str(uuid.uuid4())
        self.preferences[user_id] = NotificationPreferencesDB(
            id=prefs_id,
            user_id=user_id,
            transaction_notifications=True,
            security_notifications=True,
            account_notifications=True,
            payment_notifications=True,
            savings_notifications=True,
            kyc_notifications=True,
            system_notifications=True,
            marketing_notifications=False,
            reminder_notifications=True,
            email_enabled=True,
            sms_enabled=True,
            push_enabled=True,
            quiet_hours_start="22:00",
            quiet_hours_end="07:00",
            timezone="UTC",
            created_at=datetime.utcnow() - timedelta(days=30),
            updated_at=datetime.utcnow()
        )
        
        # Sample notifications
        notifications_data = [
            {
                "title": "Transaction Successful",
                "message": "Your payment of UGX 50,000 to John Doe has been completed successfully.",
                "type": NotificationType.TRANSACTION,
                "priority": NotificationPriority.MEDIUM,
                "status": NotificationStatus.READ,
                "channels": [NotificationChannel.IN_APP, NotificationChannel.SMS],
                "metadata": {"transaction_id": "txn_123", "amount": 50000, "currency": "UGX"},
                "read_at": datetime.utcnow() - timedelta(hours=2)
            },
            {
                "title": "Security Alert",
                "message": "New device login detected from Kampala, Uganda. If this wasn't you, please secure your account immediately.",
                "type": NotificationType.SECURITY,
                "priority": NotificationPriority.HIGH,
                "status": NotificationStatus.UNREAD,
                "channels": [NotificationChannel.IN_APP, NotificationChannel.EMAIL, NotificationChannel.SMS],
                "metadata": {"device": "iPhone 13", "location": "Kampala, Uganda", "ip": "192.168.1.1"}
            },
            {
                "title": "Savings Goal Progress",
                "message": "Great job! You're 75% towards your Emergency Fund goal. Keep it up!",
                "type": NotificationType.SAVINGS,
                "priority": NotificationPriority.LOW,
                "status": NotificationStatus.UNREAD,
                "channels": [NotificationChannel.IN_APP],
                "metadata": {"goal_id": "goal_123", "progress": 75, "target_amount": 1000000}
            },
            {
                "title": "KYC Document Approved",
                "message": "Your identity document has been verified and approved. Your account is now fully activated.",
                "type": NotificationType.KYC,
                "priority": NotificationPriority.MEDIUM,
                "status": NotificationStatus.READ,
                "channels": [NotificationChannel.IN_APP, NotificationChannel.EMAIL],
                "metadata": {"document_type": "national_id", "verification_level": "tier_2"},
                "read_at": datetime.utcnow() - timedelta(days=1)
            },
            {
                "title": "System Maintenance",
                "message": "Scheduled maintenance will occur tonight from 2:00 AM to 4:00 AM. Some services may be temporarily unavailable.",
                "type": NotificationType.SYSTEM,
                "priority": NotificationPriority.MEDIUM,
                "status": NotificationStatus.UNREAD,
                "channels": [NotificationChannel.IN_APP, NotificationChannel.EMAIL],
                "metadata": {"maintenance_start": "2024-01-15T02:00:00Z", "maintenance_end": "2024-01-15T04:00:00Z"},
                "scheduled_at": datetime.utcnow() + timedelta(hours=6)
            }
        ]
        
        for i, notif_data in enumerate(notifications_data):
            notif_id = str(uuid.uuid4())
            self.notifications[notif_id] = NotificationDB(
                id=notif_id,
                user_id=user_id,
                created_at=datetime.utcnow() - timedelta(hours=i*2),
                updated_at=datetime.utcnow() - timedelta(hours=i*2),
                **notif_data
            )
    
    async def get_notifications(
        self, 
        user_id: str, 
        filters: Optional[NotificationFilters] = None,
        skip: int = 0,
        limit: int = 20
    ) -> List[NotificationProfile]:
        """Get user notifications with optional filtering"""
        user_notifications = [
            notif for notif in self.notifications.values() 
            if notif.user_id == user_id
        ]
        
        # Apply filters
        if filters:
            if filters.type:
                user_notifications = [n for n in user_notifications if n.type == filters.type]
            if filters.status:
                user_notifications = [n for n in user_notifications if n.status == filters.status]
            if filters.priority:
                user_notifications = [n for n in user_notifications if n.priority == filters.priority]
            if filters.channel:
                user_notifications = [n for n in user_notifications if filters.channel in n.channels]
            if filters.date_from:
                user_notifications = [n for n in user_notifications if n.created_at >= filters.date_from]
            if filters.date_to:
                user_notifications = [n for n in user_notifications if n.created_at <= filters.date_to]
            if filters.unread_only:
                user_notifications = [n for n in user_notifications if n.status == NotificationStatus.UNREAD]
        
        # Sort by creation date (newest first)
        user_notifications.sort(key=lambda x: x.created_at, reverse=True)
        
        # Apply pagination
        paginated_notifications = user_notifications[skip:skip + limit]
        
        # Convert to response models
        return [
            NotificationProfile(
                id=notif.id,
                title=notif.title,
                message=notif.message,
                type=notif.type,
                priority=notif.priority,
                status=notif.status,
                channels=notif.channels,
                metadata=notif.metadata,
                created_at=notif.created_at,
                read_at=notif.read_at,
                scheduled_at=notif.scheduled_at,
                expires_at=notif.expires_at,
                is_expired=notif.expires_at and notif.expires_at < datetime.utcnow() if notif.expires_at else False
            )
            for notif in paginated_notifications
        ]
    
    async def get_notification_summary(self, user_id: str) -> NotificationSummary:
        """Get notification summary for user"""
        user_notifications = [
            notif for notif in self.notifications.values() 
            if notif.user_id == user_id
        ]
        
        total_notifications = len(user_notifications)
        unread_count = len([n for n in user_notifications if n.status == NotificationStatus.UNREAD])
        read_count = len([n for n in user_notifications if n.status == NotificationStatus.READ])
        archived_count = len([n for n in user_notifications if n.status == NotificationStatus.ARCHIVED])
        
        # Count by type
        by_type = {}
        for notif_type in NotificationType:
            by_type[notif_type.value] = len([n for n in user_notifications if n.type == notif_type])
        
        # Count by priority
        by_priority = {}
        for priority in NotificationPriority:
            by_priority[priority.value] = len([n for n in user_notifications if n.priority == priority])
        
        # Get recent notifications (last 5)
        recent_notifications = sorted(user_notifications, key=lambda x: x.created_at, reverse=True)[:5]
        recent_profiles = [
            NotificationProfile(
                id=notif.id,
                title=notif.title,
                message=notif.message,
                type=notif.type,
                priority=notif.priority,
                status=notif.status,
                channels=notif.channels,
                metadata=notif.metadata,
                created_at=notif.created_at,
                read_at=notif.read_at,
                scheduled_at=notif.scheduled_at,
                expires_at=notif.expires_at,
                is_expired=notif.expires_at and notif.expires_at < datetime.utcnow() if notif.expires_at else False
            )
            for notif in recent_notifications
        ]
        
        return NotificationSummary(
            total_notifications=total_notifications,
            unread_count=unread_count,
            read_count=read_count,
            archived_count=archived_count,
            by_type=by_type,
            by_priority=by_priority,
            recent_notifications=recent_profiles
        )
    
    async def create_notification(
        self, 
        user_id: str, 
        request: NotificationCreateRequest
    ) -> NotificationProfile:
        """Create a new notification"""
        # Check user preferences to see if this type of notification is enabled
        user_prefs = self.preferences.get(user_id)
        if user_prefs:
            type_enabled = getattr(user_prefs, f"{request.type.value}_notifications", True)
            if not type_enabled:
                raise BusinessLogicError(f"User has disabled {request.type.value} notifications")
        
        # Validate scheduled time
        if request.scheduled_at and request.scheduled_at <= datetime.utcnow():
            raise ValidationError("Scheduled time must be in the future")
        
        # Validate expiry time
        if request.expires_at and request.expires_at <= datetime.utcnow():
            raise ValidationError("Expiry time must be in the future")
        
        if request.scheduled_at and request.expires_at and request.scheduled_at >= request.expires_at:
            raise ValidationError("Scheduled time must be before expiry time")
        
        notif_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        notification = NotificationDB(
            id=notif_id,
            user_id=user_id,
            title=request.title,
            message=request.message,
            type=request.type,
            priority=request.priority,
            status=NotificationStatus.UNREAD,
            channels=request.channels,
            metadata=request.metadata,
            created_at=now,
            scheduled_at=request.scheduled_at,
            expires_at=request.expires_at,
            updated_at=now
        )
        
        self.notifications[notif_id] = notification
        
        # Create delivery records for each channel
        for channel in request.channels:
            delivery_id = str(uuid.uuid4())
            self.deliveries[delivery_id] = NotificationDeliveryDB(
                id=delivery_id,
                notification_id=notif_id,
                user_id=user_id,
                channel=channel,
                status="pending",
                attempts=0,
                created_at=now,
                updated_at=now
            )
        
        # Create notification profile for response
        notification_profile = NotificationProfile(
            id=notification.id,
            title=notification.title,
            message=notification.message,
            type=notification.type,
            priority=notification.priority,
            status=notification.status,
            channels=notification.channels,
            metadata=notification.metadata,
            created_at=notification.created_at,
            read_at=notification.read_at,
            scheduled_at=notification.scheduled_at,
            expires_at=notification.expires_at,
            is_expired=False
        )
        
        # Send real-time notification via WebSocket if IN_APP channel is included
        if NotificationChannel.IN_APP in request.channels:
            try:
                await broadcast_notification({
                    "id": notification.id,
                    "title": notification.title,
                    "message": notification.message,
                    "type": notification.type.value,
                    "priority": notification.priority.value,
                    "metadata": notification.metadata,
                    "created_at": notification.created_at.isoformat()
                }, user_id)
            except Exception as e:
                # Log error but don't fail the notification creation
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to send real-time notification: {e}")
        
        return notification_profile
    
    async def update_notification(
        self, 
        user_id: str, 
        notification_id: str, 
        request: NotificationUpdateRequest
    ) -> NotificationProfile:
        """Update notification status"""
        if notification_id not in self.notifications:
            raise NotFoundError("Notification not found")
        
        notification = self.notifications[notification_id]
        if notification.user_id != user_id:
            raise NotFoundError("Notification not found")
        
        # Update fields
        if request.status:
            notification.status = request.status
        
        if request.read_at:
            notification.read_at = request.read_at
        elif request.status == NotificationStatus.READ and not notification.read_at:
            notification.read_at = datetime.utcnow()
        
        notification.updated_at = datetime.utcnow()
        
        return NotificationProfile(
            id=notification.id,
            title=notification.title,
            message=notification.message,
            type=notification.type,
            priority=notification.priority,
            status=notification.status,
            channels=notification.channels,
            metadata=notification.metadata,
            created_at=notification.created_at,
            read_at=notification.read_at,
            scheduled_at=notification.scheduled_at,
            expires_at=notification.expires_at,
            is_expired=notification.expires_at and notification.expires_at < datetime.utcnow() if notification.expires_at else False
        )
    
    async def bulk_update_notifications(
        self, 
        user_id: str, 
        request: BulkNotificationUpdateRequest
    ) -> Dict[str, str]:
        """Bulk update notification status"""
        results = {}
        
        for notification_id in request.notification_ids:
            try:
                if notification_id not in self.notifications:
                    results[notification_id] = "not_found"
                    continue
                
                notification = self.notifications[notification_id]
                if notification.user_id != user_id:
                    results[notification_id] = "not_found"
                    continue
                
                notification.status = request.status
                if request.status == NotificationStatus.READ and not notification.read_at:
                    notification.read_at = datetime.utcnow()
                notification.updated_at = datetime.utcnow()
                
                results[notification_id] = "updated"
            except Exception:
                results[notification_id] = "error"
        
        return results
    
    async def delete_notification(self, user_id: str, notification_id: str) -> bool:
        """Delete a notification"""
        if notification_id not in self.notifications:
            raise NotFoundError("Notification not found")
        
        notification = self.notifications[notification_id]
        if notification.user_id != user_id:
            raise NotFoundError("Notification not found")
        
        # Delete notification and associated deliveries
        del self.notifications[notification_id]
        
        # Delete delivery records
        delivery_ids_to_delete = [
            delivery_id for delivery_id, delivery in self.deliveries.items()
            if delivery.notification_id == notification_id
        ]
        for delivery_id in delivery_ids_to_delete:
            del self.deliveries[delivery_id]
        
        return True
    
    async def get_notification_preferences(self, user_id: str) -> NotificationPreferencesProfile:
        """Get user notification preferences"""
        if user_id not in self.preferences:
            # Create default preferences
            await self.update_notification_preferences(user_id, NotificationPreferencesRequest())
        
        prefs = self.preferences[user_id]
        return NotificationPreferencesProfile(
            user_id=prefs.user_id,
            transaction_notifications=prefs.transaction_notifications,
            security_notifications=prefs.security_notifications,
            account_notifications=prefs.account_notifications,
            payment_notifications=prefs.payment_notifications,
            savings_notifications=prefs.savings_notifications,
            kyc_notifications=prefs.kyc_notifications,
            system_notifications=prefs.system_notifications,
            marketing_notifications=prefs.marketing_notifications,
            reminder_notifications=prefs.reminder_notifications,
            email_enabled=prefs.email_enabled,
            sms_enabled=prefs.sms_enabled,
            push_enabled=prefs.push_enabled,
            quiet_hours_start=prefs.quiet_hours_start,
            quiet_hours_end=prefs.quiet_hours_end,
            timezone=prefs.timezone,
            updated_at=prefs.updated_at
        )
    
    async def update_notification_preferences(
        self, 
        user_id: str, 
        request: NotificationPreferencesRequest
    ) -> NotificationPreferencesProfile:
        """Update user notification preferences"""
        now = datetime.utcnow()
        
        if user_id in self.preferences:
            prefs = self.preferences[user_id]
            prefs.transaction_notifications = request.transaction_notifications
            prefs.security_notifications = request.security_notifications
            prefs.account_notifications = request.account_notifications
            prefs.payment_notifications = request.payment_notifications
            prefs.savings_notifications = request.savings_notifications
            prefs.kyc_notifications = request.kyc_notifications
            prefs.system_notifications = request.system_notifications
            prefs.marketing_notifications = request.marketing_notifications
            prefs.reminder_notifications = request.reminder_notifications
            prefs.email_enabled = request.email_enabled
            prefs.sms_enabled = request.sms_enabled
            prefs.push_enabled = request.push_enabled
            prefs.quiet_hours_start = request.quiet_hours_start
            prefs.quiet_hours_end = request.quiet_hours_end
            prefs.timezone = request.timezone
            prefs.updated_at = now
        else:
            prefs_id = str(uuid.uuid4())
            prefs = NotificationPreferencesDB(
                id=prefs_id,
                user_id=user_id,
                transaction_notifications=request.transaction_notifications,
                security_notifications=request.security_notifications,
                account_notifications=request.account_notifications,
                payment_notifications=request.payment_notifications,
                savings_notifications=request.savings_notifications,
                kyc_notifications=request.kyc_notifications,
                system_notifications=request.system_notifications,
                marketing_notifications=request.marketing_notifications,
                reminder_notifications=request.reminder_notifications,
                email_enabled=request.email_enabled,
                sms_enabled=request.sms_enabled,
                push_enabled=request.push_enabled,
                quiet_hours_start=request.quiet_hours_start,
                quiet_hours_end=request.quiet_hours_end,
                timezone=request.timezone,
                created_at=now,
                updated_at=now
            )
            self.preferences[user_id] = prefs
        
        return NotificationPreferencesProfile(
            user_id=prefs.user_id,
            transaction_notifications=prefs.transaction_notifications,
            security_notifications=prefs.security_notifications,
            account_notifications=prefs.account_notifications,
            payment_notifications=prefs.payment_notifications,
            savings_notifications=prefs.savings_notifications,
            kyc_notifications=prefs.kyc_notifications,
            system_notifications=prefs.system_notifications,
            marketing_notifications=prefs.marketing_notifications,
            reminder_notifications=prefs.reminder_notifications,
            email_enabled=prefs.email_enabled,
            sms_enabled=prefs.sms_enabled,
            push_enabled=prefs.push_enabled,
            quiet_hours_start=prefs.quiet_hours_start,
            quiet_hours_end=prefs.quiet_hours_end,
            timezone=prefs.timezone,
            updated_at=prefs.updated_at
        )
    
    async def get_notification_stats(self, user_id: str) -> NotificationStats:
        """Get notification delivery statistics"""
        user_deliveries = [
            delivery for delivery in self.deliveries.values()
            if delivery.user_id == user_id
        ]
        
        total_sent = len(user_deliveries)
        total_delivered = len([d for d in user_deliveries if d.status == "delivered"])
        total_failed = len([d for d in user_deliveries if d.status == "failed"])
        delivery_rate = (total_delivered / total_sent * 100) if total_sent > 0 else 0
        
        # Stats by channel
        by_channel = {}
        for channel in NotificationChannel:
            channel_deliveries = [d for d in user_deliveries if d.channel == channel]
            by_channel[channel.value] = {
                "sent": len(channel_deliveries),
                "delivered": len([d for d in channel_deliveries if d.status == "delivered"]),
                "failed": len([d for d in channel_deliveries if d.status == "failed"])
            }
        
        # Stats by type (need to join with notifications)
        by_type = {}
        for notif_type in NotificationType:
            type_notifications = [
                n for n in self.notifications.values()
                if n.user_id == user_id and n.type == notif_type
            ]
            type_deliveries = [
                d for d in user_deliveries
                if d.notification_id in [n.id for n in type_notifications]
            ]
            by_type[notif_type.value] = {
                "sent": len(type_deliveries),
                "delivered": len([d for d in type_deliveries if d.status == "delivered"]),
                "failed": len([d for d in type_deliveries if d.status == "failed"])
            }
        
        # Recent activity
        recent_deliveries = sorted(user_deliveries, key=lambda x: x.created_at, reverse=True)[:10]
        recent_activity = []
        for delivery in recent_deliveries:
            notification = self.notifications.get(delivery.notification_id)
            if notification:
                recent_activity.append({
                    "notification_title": notification.title,
                    "channel": delivery.channel.value,
                    "status": delivery.status,
                    "delivered_at": delivery.delivered_at.isoformat() if delivery.delivered_at else None,
                    "created_at": delivery.created_at.isoformat()
                })
        
        return NotificationStats(
            total_sent=total_sent,
            total_delivered=total_delivered,
            total_failed=total_failed,
            delivery_rate=round(delivery_rate, 2),
            by_channel=by_channel,
            by_type=by_type,
            recent_activity=recent_activity
        )
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get notifications service health status"""
        total_notifications = len(self.notifications)
        total_preferences = len(self.preferences)
        total_deliveries = len(self.deliveries)
        
        # Calculate delivery success rate
        recent_deliveries = [
            d for d in self.deliveries.values()
            if d.created_at > datetime.utcnow() - timedelta(hours=24)
        ]
        success_rate = 0
        if recent_deliveries:
            successful = len([d for d in recent_deliveries if d.status == "delivered"])
            success_rate = (successful / len(recent_deliveries)) * 100
        
        return {
            "service": "notifications",
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {
                "total_notifications": total_notifications,
                "total_preferences": total_preferences,
                "total_deliveries": total_deliveries,
                "delivery_success_rate_24h": round(success_rate, 2)
            },
            "version": "1.0.0"
        }
