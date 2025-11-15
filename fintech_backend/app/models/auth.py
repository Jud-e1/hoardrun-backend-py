"""
Authentication models for user registration, login, and profile management.
"""

from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class UserStatus(str, Enum):
    """User account status enumeration."""
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"


class UserRole(str, Enum):
    """User role enumeration."""
    USER = "user"
    PREMIUM = "premium"
    ADMIN = "admin"


# Request Models
class UserRegisterRequest(BaseModel):
    """User registration request model."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password (min 8 characters)")
    first_name: str = Field(..., min_length=1, max_length=50, description="User first name")
    last_name: str = Field(..., min_length=1, max_length=50, description="User last name")
    phone_number: Optional[str] = Field(None, description="User phone number")
    date_of_birth: Optional[str] = Field(None, description="Date of birth (YYYY-MM-DD)")
    country: Optional[str] = Field(None, description="Country code")
    id_number: Optional[str] = Field(None, description="User ID number")
    terms_accepted: bool = Field(..., description="Terms and conditions acceptance")
    
    @validator('password')
    def validate_password(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v
    
    @validator('terms_accepted')
    def validate_terms(cls, v):
        """Validate terms acceptance."""
        if not v:
            raise ValueError('Terms and conditions must be accepted')
        return v


class UserLoginRequest(BaseModel):
    """User login request model."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")
    remember_me: bool = Field(False, description="Remember login session")


class PasswordResetRequest(BaseModel):
    """Password reset request model."""
    email: EmailStr = Field(..., description="User email address")


class PasswordChangeRequest(BaseModel):
    """Password change request model."""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")
    
    @validator('new_password')
    def validate_new_password(cls, v):
        """Validate new password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class EmailVerificationRequest(BaseModel):
    """Email verification request model."""
    token: str = Field(..., description="Email verification token")


class UserProfileUpdateRequest(BaseModel):
    """User profile update request model."""
    first_name: Optional[str] = Field(None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(None, min_length=1, max_length=50)
    phone_number: Optional[str] = Field(None)
    date_of_birth: Optional[str] = Field(None)
    country: Optional[str] = Field(None)
    bio: Optional[str] = Field(None, max_length=500)
    profile_picture_url: Optional[str] = Field(None)


class UserSettingsUpdateRequest(BaseModel):
    """User settings update request model."""
    email_notifications: Optional[bool] = Field(None)
    sms_notifications: Optional[bool] = Field(None)
    push_notifications: Optional[bool] = Field(None)
    marketing_emails: Optional[bool] = Field(None)
    two_factor_enabled: Optional[bool] = Field(None)
    currency_preference: Optional[str] = Field(None)
    language_preference: Optional[str] = Field(None)
    timezone: Optional[str] = Field(None)


# Response Models
class UserProfile(BaseModel):
    """User profile model."""
    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    first_name: str = Field(..., description="User first name")
    last_name: str = Field(..., description="User last name")
    phone_number: Optional[str] = Field(None, description="User phone number")
    date_of_birth: Optional[str] = Field(None, description="Date of birth")
    country: Optional[str] = Field(None, description="Country")
    id_number: Optional[str] = Field(None, description="User ID number")
    bio: Optional[str] = Field(None, description="User bio")
    profile_picture_url: Optional[str] = Field(None, description="Profile picture URL")
    status: UserStatus = Field(..., description="User account status")
    role: UserRole = Field(..., description="User role")
    email_verified: bool = Field(..., description="Email verification status")
    created_at: datetime = Field(..., description="Account creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    last_login_at: Optional[datetime] = Field(None, description="Last login timestamp")
    
    class Config:
        from_attributes = True


class UserSettings(BaseModel):
    """User settings model."""
    email_notifications: bool = Field(True, description="Email notifications enabled")
    sms_notifications: bool = Field(True, description="SMS notifications enabled")
    push_notifications: bool = Field(True, description="Push notifications enabled")
    marketing_emails: bool = Field(False, description="Marketing emails enabled")
    two_factor_enabled: bool = Field(False, description="Two-factor authentication enabled")
    currency_preference: str = Field("USD", description="Preferred currency")
    language_preference: str = Field("en", description="Preferred language")
    timezone: str = Field("UTC", description="User timezone")
    
    class Config:
        from_attributes = True


class TokenData(BaseModel):
    """Token data model."""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    expires_at: datetime = Field(..., description="Token expiration timestamp")


class UserResponse(BaseModel):
    """User response model."""
    success: bool = Field(True, description="Response success status")
    message: str = Field(..., description="Response message")
    data: Dict[str, UserProfile] = Field(..., description="User data")


class LoginData(BaseModel):
    """Login response data model."""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    expires_at: datetime = Field(..., description="Token expiration timestamp")
    user: UserProfile = Field(..., description="User profile data")


class TokenResponse(BaseModel):
    """Token response model."""
    success: bool = Field(True, description="Response success status")
    message: str = Field(..., description="Response message")
    data: TokenData = Field(..., description="Token data")


class LoginResponse(BaseModel):
    """Login response model."""
    success: bool = Field(True, description="Response success status")
    message: str = Field(..., description="Response message")
    data: LoginData = Field(..., description="Login data with tokens and user info")


class AuthResponse(BaseModel):
    """Authentication response model."""
    success: bool = Field(True, description="Response success status")
    message: str = Field(..., description="Response message")
    data: Dict[str, Any] = Field(..., description="Response data")


# Database Models (for SQLAlchemy)
class UserCreate(BaseModel):
    """User creation model for database operations."""
    email: str
    password_hash: str
    first_name: str
    last_name: str
    phone_number: Optional[str] = None
    date_of_birth: Optional[str] = None
    country: Optional[str] = None
    id_number: Optional[str] = None
    status: UserStatus = UserStatus.PENDING
    role: UserRole = UserRole.USER
    email_verified: bool = False
    email_verification_code: Optional[str] = None
    password_reset_token: Optional[str] = None
    password_reset_expires: Optional[datetime] = None


class UserUpdate(BaseModel):
    """User update model for database operations."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    date_of_birth: Optional[str] = None
    country: Optional[str] = None
    id_number: Optional[str] = None
    bio: Optional[str] = None
    profile_picture_url: Optional[str] = None
    status: Optional[UserStatus] = None
    email_verified: Optional[bool] = None
    last_login_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RefreshTokenCreate(BaseModel):
    """Refresh token creation model."""
    user_id: str
    token: str
    expires_at: datetime
    is_active: bool = True


class RefreshTokenUpdate(BaseModel):
    """Refresh token update model."""
    is_active: Optional[bool] = None
    revoked_at: Optional[datetime] = None


# Utility Models
class JWTPayload(BaseModel):
    """JWT token payload model."""
    sub: str = Field(..., description="Subject (user ID)")
    email: str = Field(..., description="User email")
    role: str = Field(..., description="User role")
    exp: int = Field(..., description="Expiration timestamp")
    iat: int = Field(..., description="Issued at timestamp")
    jti: str = Field(..., description="JWT ID")


class PasswordValidation(BaseModel):
    """Password validation result model."""
    is_valid: bool = Field(..., description="Password validity")
    errors: list[str] = Field(default_factory=list, description="Validation errors")
    strength_score: int = Field(..., ge=0, le=100, description="Password strength score")


class EmailTemplate(BaseModel):
    """Email template model."""
    template_name: str = Field(..., description="Template name")
    subject: str = Field(..., description="Email subject")
    html_content: str = Field(..., description="HTML email content")
    text_content: str = Field(..., description="Plain text email content")
    variables: Dict[str, Any] = Field(default_factory=dict, description="Template variables")


# Alias for backward compatibility
User = UserProfile
