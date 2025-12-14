"""
System settings models for managing system-wide configuration.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
from enum import Enum


class BackupFrequency(str, Enum):
    """Backup frequency enumeration."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


# Request Models
class SystemSettingsUpdateRequest(BaseModel):
    """System settings update request model."""
    maintenance_mode: Optional[bool] = Field(None, description="Enable/disable maintenance mode")
    max_users: Optional[int] = Field(None, ge=1, le=1000000, description="Maximum number of users allowed")
    email_notifications: Optional[bool] = Field(None, description="Enable/disable system email notifications")
    backup_frequency: Optional[BackupFrequency] = Field(None, description="Backup frequency setting")

    @validator('max_users')
    def validate_max_users(cls, v):
        """Validate max users value."""
        if v is not None and v < 1:
            raise ValueError('Max users must be at least 1')
        return v


# Response Models
class SystemSettings(BaseModel):
    """System settings model."""
    maintenance_mode: bool = Field(False, description="Maintenance mode status")
    max_users: int = Field(1000, description="Maximum number of users allowed")
    email_notifications: bool = Field(True, description="Email notifications enabled")
    backup_frequency: BackupFrequency = Field(BackupFrequency.DAILY, description="Backup frequency")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    updated_by: Optional[str] = Field(None, description="User who last updated settings")

    class Config:
        from_attributes = True


class SystemSettingsResponse(BaseModel):
    """System settings response model."""
    success: bool = Field(True, description="Response success status")
    message: str = Field(..., description="Response message")
    data: SystemSettings = Field(..., description="System settings data")


class SystemSettingsUpdateResponse(BaseModel):
    """System settings update response model."""
    success: bool = Field(True, description="Response success status")
    message: str = Field(..., description="Response message")
    data: SystemSettings = Field(..., description="Updated system settings data")


# Database Models (for SQLAlchemy)
class SystemSettingsCreate(BaseModel):
    """System settings creation model for database operations."""
    maintenance_mode: bool = False
    max_users: int = 1000
    email_notifications: bool = True
    backup_frequency: BackupFrequency = BackupFrequency.DAILY
    updated_by: Optional[str] = None


class SystemSettingsUpdate(BaseModel):
    """System settings update model for database operations."""
    maintenance_mode: Optional[bool] = None
    max_users: Optional[int] = None
    email_notifications: Optional[bool] = None
    backup_frequency: Optional[BackupFrequency] = None
    updated_by: Optional[str] = None
    updated_at: Optional[datetime] = None


# Utility Models
class SystemSettingsValidation(BaseModel):
    """System settings validation result model."""
    is_valid: bool = Field(..., description="Settings validity")
    errors: list[str] = Field(default_factory=list, description="Validation errors")
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")


class SystemSettingsAudit(BaseModel):
    """System settings audit log model."""
    id: str = Field(..., description="Audit log ID")
    action: str = Field(..., description="Action performed (create, update, delete)")
    old_settings: Optional[SystemSettings] = Field(None, description="Previous settings")
    new_settings: Optional[SystemSettings] = Field(None, description="New settings")
    changed_by: str = Field(..., description="User who made the change")
    changed_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of change")
    ip_address: Optional[str] = Field(None, description="IP address of the change")
    user_agent: Optional[str] = Field(None, description="User agent of the change")
