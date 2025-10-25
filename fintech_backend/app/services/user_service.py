"""
User service for profile and settings management.
"""

import secrets
import os
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from fastapi import UploadFile
from passlib.context import CryptContext

from ..models.auth import (
    UserProfile, UserProfileUpdateRequest, UserSettingsUpdateRequest,
    UserSettings, UserStatus, UserRole
)
from ..services.auth_service import AuthService
from ..core.exceptions import (
    ValidationException, AuthenticationException, UserNotFoundException
)
from ..config.settings import get_settings
from ..config.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserService:
    """User service for handling user profile and settings management."""
    
    def __init__(self):
        self.auth_service = AuthService()
        self.upload_dir = "uploads/avatars"
        self.max_file_size = 5 * 1024 * 1024  # 5MB
        self.allowed_extensions = {".jpg", ".jpeg", ".png", ".gif"}
    
    async def get_user_profile(self, token: str, db: Session) -> UserProfile:
        """
        Get user profile information.
        
        Args:
            token: Access token
            db: Database session
            
        Returns:
            UserProfile: User profile information
        """
        try:
            logger.info("Getting user profile")
            
            # Use auth service to get current user
            user_profile = await self.auth_service.get_current_user(token, db)
            
            logger.info(f"User profile retrieved: {user_profile.id}")
            return user_profile
            
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            raise
    
    async def update_user_profile(self, token: str, request: UserProfileUpdateRequest, db: Session) -> UserProfile:
        """
        Update user profile information.
        
        Args:
            token: Access token
            request: Profile update request
            db: Database session
            
        Returns:
            UserProfile: Updated user profile
        """
        try:
            logger.info("Updating user profile")
            
            # Use auth service to update profile
            updated_profile = await self.auth_service.update_user_profile(token, request, db)
            
            logger.info(f"User profile updated: {updated_profile.id}")
            return updated_profile
            
        except Exception as e:
            logger.error(f"Error updating user profile: {e}")
            raise
    
    async def upload_avatar(self, token: str, file: UploadFile, db: Session) -> Dict[str, Any]:
        """
        Upload user profile picture.
        
        Args:
            token: Access token
            file: Uploaded file
            db: Database session
            
        Returns:
            Dict: Upload result with file URL
        """
        try:
            logger.info(f"Uploading avatar: {file.filename}")
            
            # Get current user
            current_user = await self.auth_service.get_current_user(token, db)
            
            # Validate file
            await self._validate_upload_file(file)
            
            # Generate unique filename
            file_extension = os.path.splitext(file.filename)[1].lower()
            unique_filename = f"{current_user.id}_{secrets.token_urlsafe(8)}{file_extension}"
            
            # Create upload directory if it doesn't exist
            os.makedirs(self.upload_dir, exist_ok=True)
            
            # Save file (mock implementation)
            file_path = os.path.join(self.upload_dir, unique_filename)
            file_url = f"/uploads/avatars/{unique_filename}"
            
            # In a real implementation, you would save the file:
            # with open(file_path, "wb") as buffer:
            #     content = await file.read()
            #     buffer.write(content)
            
            # Update user profile with new avatar URL (mock implementation)
            await self._update_user_avatar(current_user.id, file_url, db)
            
            logger.info(f"Avatar uploaded successfully: {file_url}")
            return {
                "uploaded": True,
                "filename": unique_filename,
                "url": file_url,
                "size": file.size
            }
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"Error uploading avatar: {e}")
            raise ValidationException(f"Avatar upload failed: {str(e)}")
    
    async def get_user_settings(self, token: str, db: Session) -> UserSettings:
        """
        Get user settings and preferences.
        
        Args:
            token: Access token
            db: Database session
            
        Returns:
            UserSettings: User settings
        """
        try:
            logger.info("Getting user settings")
            
            # Get current user
            current_user = await self.auth_service.get_current_user(token, db)
            
            # Get user settings (mock implementation)
            settings = await self._get_user_settings_from_db(current_user.id, db)
            
            logger.info(f"User settings retrieved: {current_user.id}")
            return settings
            
        except Exception as e:
            logger.error(f"Error getting user settings: {e}")
            raise
    
    async def update_user_settings(self, token: str, request: UserSettingsUpdateRequest, db: Session) -> UserSettings:
        """
        Update user settings and preferences.
        
        Args:
            token: Access token
            request: Settings update request
            db: Database session
            
        Returns:
            UserSettings: Updated user settings
        """
        try:
            logger.info("Updating user settings")
            
            # Get current user
            current_user = await self.auth_service.get_current_user(token, db)
            
            # Update settings (mock implementation)
            updated_settings = await self._update_user_settings_in_db(current_user.id, request, db)
            
            logger.info(f"User settings updated: {current_user.id}")
            return updated_settings
            
        except Exception as e:
            logger.error(f"Error updating user settings: {e}")
            raise ValidationException(f"Settings update failed: {str(e)}")
    
    async def delete_user_account(self, token: str, password: str, db: Session) -> Dict[str, Any]:
        """
        Delete user account permanently.
        
        Args:
            token: Access token
            password: User password for verification
            db: Database session
            
        Returns:
            Dict: Deletion result
        """
        try:
            logger.info("Deleting user account")
            
            # Get current user
            current_user = await self.auth_service.get_current_user(token, db)
            
            # Verify password
            user_data = await self._get_user_with_password(current_user.id, db)
            if not self._verify_password(password, user_data.get("password_hash", "")):
                raise AuthenticationException("Invalid password")
            
            # Perform account deletion (mock implementation)
            await self._delete_user_from_db(current_user.id, db)
            
            # Invalidate all user tokens
            await self.auth_service._invalidate_user_tokens(current_user.id, db)
            
            logger.info(f"User account deleted: {current_user.id}")
            return {
                "deleted": True,
                "user_id": current_user.id,
                "deleted_at": datetime.utcnow().isoformat()
            }
            
        except AuthenticationException:
            raise
        except Exception as e:
            logger.error(f"Error deleting user account: {e}")
            raise ValidationException(f"Account deletion failed: {str(e)}")
    
    # Private helper methods
    async def _validate_upload_file(self, file: UploadFile) -> None:
        """Validate uploaded file."""
        if not file.filename:
            raise ValidationException("No file provided")
        
        # Check file extension
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in self.allowed_extensions:
            raise ValidationException(f"File type not allowed. Allowed types: {', '.join(self.allowed_extensions)}")
        
        # Check file size
        if file.size and file.size > self.max_file_size:
            raise ValidationException(f"File too large. Maximum size: {self.max_file_size / (1024*1024):.1f}MB")
        
        # Check content type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise ValidationException("File must be an image")
    
    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash."""
        # Truncate password to 72 bytes to match bcrypt's limitation
        truncated_password = plain_password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
        return pwd_context.verify(truncated_password, hashed_password)
    
    async def get_all_users(self, db: Session) -> list:
        """
        Get all users in the system (Admin endpoint).

        Args:
            db: Database session

        Returns:
            List: List of all users
        """
        try:
            logger.info("Getting all users")

            # Import User model here to avoid circular imports
            from ..database.models import User

            # Query all users from the database
            users = db.query(User).all()

            # Convert to dictionary format for API response
            user_list = []
            for user in users:
                user_dict = {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "phone_number": user.phone_number,
                    "is_active": user.is_active,
                    "is_verified": user.is_verified,
                    "email_verified": user.email_verified,
                    "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
                    "date_of_birth": user.date_of_birth,
                    "country": user.country,
                    "id_number": user.id_number,
                    "bio": user.bio,
                    "profile_picture_url": user.profile_picture_url,
                    "status": user.status,
                    "role": user.role,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                    "updated_at": user.updated_at.isoformat() if user.updated_at else None
                }
                user_list.append(user_dict)

            logger.info(f"Retrieved {len(user_list)} users from database")
            return user_list

        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            raise ValidationException(f"Failed to retrieve users: {str(e)}")

    # Mock database operations (replace with actual database calls)
    async def _update_user_avatar(self, user_id: str, avatar_url: str, db: Session) -> None:
        """Update user avatar URL (mock implementation)."""
        logger.info(f"Updating avatar for user {user_id}: {avatar_url}")
        # This would update the user's profile_picture_url in the database
        pass
    
    async def _get_user_settings_from_db(self, user_id: str, db: Session) -> UserSettings:
        """Get user settings from database (mock implementation)."""
        # Mock settings data
        return UserSettings(
            email_notifications=True,
            sms_notifications=True,
            push_notifications=True,
            marketing_emails=False,
            two_factor_enabled=False,
            currency_preference="USD",
            language_preference="en",
            timezone="UTC"
        )
    
    async def _update_user_settings_in_db(self, user_id: str, request: UserSettingsUpdateRequest, db: Session) -> UserSettings:
        """Update user settings in database (mock implementation)."""
        # Get current settings
        current_settings = await self._get_user_settings_from_db(user_id, db)
        
        # Apply updates
        update_data = request.dict(exclude_unset=True)
        updated_settings = current_settings.copy(update=update_data)
        
        logger.info(f"Settings updated for user {user_id}")
        return updated_settings
    
    async def _get_user_with_password(self, user_id: str, db: Session) -> Dict[str, Any]:
        """Get user data including password hash (mock implementation)."""
        return {
            "id": user_id,
            "password_hash": "$2b$12$example_hash"
        }
    
    async def _delete_user_from_db(self, user_id: str, db: Session) -> None:
        """Delete user from database (mock implementation)."""
        logger.info(f"Deleting user from database: {user_id}")
        # This would perform the actual database deletion
        # Including related data like transactions, settings, etc.
        pass
