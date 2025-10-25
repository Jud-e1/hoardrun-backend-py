"""
System settings service for managing system-wide configuration.
"""

from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from ..models.system_settings import (
    SystemSettings, SystemSettingsUpdateRequest, SystemSettingsCreate,
    SystemSettingsUpdate, BackupFrequency
)
from ..core.exceptions import ValidationException, AuthorizationException
from ..config.logging import get_logger

logger = get_logger(__name__)


class SystemSettingsService:
    """Service for managing system-wide settings."""

    def __init__(self):
        self.default_settings = SystemSettingsCreate(
            maintenance_mode=False,
            max_users=1000,
            email_notifications=True,
            backup_frequency=BackupFrequency.DAILY
        )

    async def get_system_settings(self, db: Session) -> SystemSettings:
        """
        Get current system settings.

        Args:
            db: Database session

        Returns:
            SystemSettings: Current system settings
        """
        try:
            logger.info("Getting system settings")

            # Try to get settings from database
            settings = await self._get_settings_from_db(db)

            if not settings:
                # Create default settings if none exist
                logger.info("No system settings found, creating defaults")
                settings = await self._create_default_settings(db)

            logger.info("System settings retrieved successfully")
            return settings

        except Exception as e:
            logger.error(f"Error getting system settings: {e}")
            raise ValidationException(f"Failed to retrieve system settings: {str(e)}")

    async def update_system_settings(
        self,
        request: SystemSettingsUpdateRequest,
        updated_by: str,
        db: Session
    ) -> SystemSettings:
        """
        Update system settings.

        Args:
            request: Settings update request
            updated_by: User ID who is updating
            db: Database session

        Returns:
            SystemSettings: Updated system settings
        """
        try:
            logger.info(f"Updating system settings by user: {updated_by}")

            # Get current settings
            current_settings = await self.get_system_settings(db)

            # Validate the update request
            await self._validate_settings_update(request, current_settings)

            # Update settings in database
            updated_settings = await self._update_settings_in_db(
                request, updated_by, db
            )

            # Log the change for audit purposes
            await self._log_settings_change(current_settings, updated_settings, updated_by)

            logger.info("System settings updated successfully")
            return updated_settings

        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"Error updating system settings: {e}")
            raise ValidationException(f"Failed to update system settings: {str(e)}")

    async def is_maintenance_mode_enabled(self, db: Session) -> bool:
        """
        Check if maintenance mode is enabled.

        Args:
            db: Database session

        Returns:
            bool: True if maintenance mode is enabled
        """
        try:
            settings = await self.get_system_settings(db)
            return settings.maintenance_mode
        except Exception as e:
            logger.error(f"Error checking maintenance mode: {e}")
            return False  # Default to False if error

    async def get_max_users_limit(self, db: Session) -> int:
        """
        Get the maximum users limit.

        Args:
            db: Database session

        Returns:
            int: Maximum number of users allowed
        """
        try:
            settings = await self.get_system_settings(db)
            return settings.max_users
        except Exception as e:
            logger.error(f"Error getting max users limit: {e}")
            return self.default_settings.max_users  # Return default

    async def are_email_notifications_enabled(self, db: Session) -> bool:
        """
        Check if email notifications are enabled.

        Args:
            db: Database session

        Returns:
            bool: True if email notifications are enabled
        """
        try:
            settings = await self.get_system_settings(db)
            return settings.email_notifications
        except Exception as e:
            logger.error(f"Error checking email notifications: {e}")
            return self.default_settings.email_notifications  # Return default

    async def get_backup_frequency(self, db: Session) -> BackupFrequency:
        """
        Get the backup frequency setting.

        Args:
            db: Database session

        Returns:
            BackupFrequency: Current backup frequency
        """
        try:
            settings = await self.get_system_settings(db)
            return settings.backup_frequency
        except Exception as e:
            logger.error(f"Error getting backup frequency: {e}")
            return self.default_settings.backup_frequency  # Return default

    # Private helper methods
    async def _validate_settings_update(
        self,
        request: SystemSettingsUpdateRequest,
        current_settings: SystemSettings
    ) -> None:
        """Validate settings update request."""
        # Add any business logic validation here
        if request.max_users is not None and request.max_users < 1:
            raise ValidationException("Maximum users must be at least 1")

        # Check for potentially dangerous changes
        if request.maintenance_mode and not current_settings.maintenance_mode:
            logger.warning("Enabling maintenance mode")

        # Add more validation as needed

    async def _get_settings_from_db(self, db: Session) -> Optional[SystemSettings]:
        """Get system settings from database (mock implementation)."""
        # In a real implementation, this would query the database
        # For now, return None to trigger default creation
        return None

    async def _create_default_settings(self, db: Session) -> SystemSettings:
        """Create default system settings (mock implementation)."""
        now = datetime.utcnow()
        return SystemSettings(
            maintenance_mode=self.default_settings.maintenance_mode,
            max_users=self.default_settings.max_users,
            email_notifications=self.default_settings.email_notifications,
            backup_frequency=self.default_settings.backup_frequency,
            updated_at=now,
            updated_by="system"
        )

    async def _update_settings_in_db(
        self,
        request: SystemSettingsUpdateRequest,
        updated_by: str,
        db: Session
    ) -> SystemSettings:
        """Update settings in database (mock implementation)."""
        # Get current settings
        current = await self.get_system_settings(db)

        # Apply updates
        update_data = request.dict(exclude_unset=True)
        updated_settings = current.copy(update=update_data)
        updated_settings.updated_at = datetime.utcnow()
        updated_settings.updated_by = updated_by

        # In a real implementation, this would save to database
        logger.info(f"Settings updated in database: {updated_settings.dict()}")

        return updated_settings

    async def _log_settings_change(
        self,
        old_settings: SystemSettings,
        new_settings: SystemSettings,
        changed_by: str
    ) -> None:
        """Log settings change for audit purposes."""
        logger.info(
            f"System settings changed by {changed_by}",
            extra={
                "old_settings": old_settings.dict(),
                "new_settings": new_settings.dict(),
                "changed_by": changed_by,
                "changed_at": datetime.utcnow().isoformat()
            }
        )

        # In a real implementation, this would save to audit log table
