"""
Authentication service for user registration, login, and profile management.
"""

import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
import bcrypt
from jose import jwt

from ..models.auth import (
    UserRegisterRequest, UserLoginRequest, UserProfile, TokenData, LoginData,
    UserProfileUpdateRequest, PasswordChangeRequest, UserCreate, UserUpdate,
    UserStatus, UserRole, JWTPayload
)
from ..core.exceptions import (
    ValidationException, AuthenticationException, AuthorizationException,
    UserNotFoundException, EmailAlreadyExistsException
)
from ..config.settings import get_settings
from ..config.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Using bcrypt directly for password hashing


class AuthService:
    """Authentication service for handling user authentication and authorization."""
    
    def __init__(self):
        self.settings = get_settings()
        self.secret_key = self.settings.jwt_secret_key or self.settings.secret_key or "your-secret-key-here"
        self.algorithm = self.settings.jwt_algorithm or self.settings.algorithm or "HS256"
        self.access_token_expire_minutes = self.settings.jwt_access_token_expire_minutes or self.settings.access_token_expire_minutes or 30
        self.refresh_token_expire_days = self.settings.jwt_refresh_token_expire_days or 7
    
    async def register_user(self, request: UserRegisterRequest, db: Session) -> UserProfile:
        """
        Register a new user account.
        
        Args:
            request: User registration request
            db: Database session
            
        Returns:
            UserProfile: Created user profile
            
        Raises:
            EmailAlreadyExistsException: If email is already registered
            ValidationException: If validation fails
        """
        try:
            logger.info(f"Registering user with email: {request.email}")
            
            # Check if user already exists
            existing_user = await self._get_user_by_email(request.email, db)
            if existing_user:
                raise EmailAlreadyExistsException(f"User with email {request.email} already exists")
            
            # Hash password
            password_hash = self._hash_password(request.password)
            
            # Generate email verification token
            verification_token = self._generate_verification_token()
            
            # Create user data - regular users start as PENDING and unverified
            user_data = UserCreate(
                email=request.email,
                password_hash=password_hash,
                first_name=request.first_name,
                last_name=request.last_name,
                phone_number=request.phone_number,
                date_of_birth=request.date_of_birth,
                country=request.country,
                id_number=request.id_number,
                status=UserStatus.PENDING,
                role=UserRole.USER,
                email_verified=False,
                email_verification_token=verification_token
            )
            
            # Save user to database
            from ..database.models import User as DBUser
            
            db_user = DBUser(
                email=user_data.email,
                password_hash=user_data.password_hash,
                first_name=user_data.first_name,
                last_name=user_data.last_name,
                phone_number=user_data.phone_number,
                date_of_birth=user_data.date_of_birth,
                country=user_data.country,
                id_number=user_data.id_number,
                status=user_data.status.value,
                role=user_data.role.value,
                email_verified=user_data.email_verified,
                email_verification_token=user_data.email_verification_token,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
            
            # Create user profile response
            user_profile = UserProfile(
                id=db_user.id,
                email=db_user.email,
                first_name=db_user.first_name,
                last_name=db_user.last_name,
                phone_number=db_user.phone_number,
                date_of_birth=db_user.date_of_birth,
                country=db_user.country,
                id_number=db_user.id_number,
                status=UserStatus(db_user.status),
                role=UserRole(db_user.role),
                email_verified=db_user.email_verified,
                created_at=db_user.created_at,
                updated_at=db_user.updated_at
            )
            
            # Send verification email (mock)
            await self._send_verification_email(user_data.email, verification_token)
            
            logger.info(f"User registered successfully: {db_user.id}")
            return user_profile
            
        except EmailAlreadyExistsException:
            raise
        except Exception as e:
            logger.error(f"Error registering user: {e}")
            raise ValidationException(f"Registration failed: {str(e)}")
    
    async def authenticate_user(self, request: UserLoginRequest, db: Session) -> LoginData:
        """
        Authenticate user and return tokens with user data.
        
        Args:
            request: User login request
            db: Database session
            
        Returns:
            LoginData: Access and refresh tokens with user profile
            
        Raises:
            AuthenticationException: If authentication fails
            UserNotFoundException: If user not found
        """
        try:
            logger.info(f"Authenticating user: {request.email}")
            
            # Get user by email
            user = await self._get_user_by_email(request.email, db)
            if not user:
                raise UserNotFoundException(f"User with email {request.email} not found")
            
            # Truncate password to 72 bytes to match bcrypt's limitation
            password_bytes = request.password.encode('utf-8')
            password_bytes = password_bytes[:72]
            truncated_password = password_bytes.decode('utf-8', errors='ignore')

            # Verify password
            if not self._verify_password(truncated_password, user.get("password_hash", "")):
                raise AuthenticationException("Invalid email or password")
            
            # Check if user is active
            if user.get("status") != UserStatus.ACTIVE.value:
                raise AuthenticationException("Account is not active. Please verify your email.")
            
            # Generate tokens
            access_token = self._create_access_token(user)
            refresh_token = self._create_refresh_token(user)
            
            # Update last login
            await self._update_last_login(user["id"], db)
            
            # Calculate expiration
            expires_in = self.access_token_expire_minutes * 60
            expires_at = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
            
            # Create user profile
            user_profile = UserProfile(
                id=user["id"],
                email=user["email"],
                first_name=user["first_name"],
                last_name=user["last_name"],
                phone_number=user.get("phone_number"),
                date_of_birth=user.get("date_of_birth"),
                country=user.get("country"),
                id_number=user.get("id_number"),
                bio=user.get("bio"),
                profile_picture_url=user.get("profile_picture_url"),
                status=UserStatus(user["status"]),
                role=UserRole(user["role"]),
                email_verified=user["email_verified"],
                created_at=user["created_at"],
                updated_at=user["updated_at"],
                last_login_at=user.get("last_login_at")
            )
            
            # Create login data with tokens and user info
            login_data = LoginData(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=expires_in,
                expires_at=expires_at,
                user=user_profile
            )
            
            logger.info(f"User authenticated successfully: {user['id']}")
            return login_data
            
        except (AuthenticationException, UserNotFoundException):
            raise
        except Exception as e:
            logger.error(f"Error authenticating user: {e}")
            raise AuthenticationException(f"Authentication failed: {str(e)}")
    
    async def logout_user(self, token: str, db: Session) -> Dict[str, Any]:
        """
        Logout user and invalidate tokens.
        
        Args:
            token: Access token
            db: Database session
            
        Returns:
            Dict: Logout result
        """
        try:
            logger.info("Logging out user")
            
            # Decode token to get user info
            payload = self._decode_token(token)
            user_id = payload.get("sub")
            
            # Invalidate refresh tokens (mock implementation)
            await self._invalidate_user_tokens(user_id, db)
            
            logger.info(f"User logged out successfully: {user_id}")
            return {"logged_out": True, "user_id": user_id}
            
        except Exception as e:
            logger.error(f"Error logging out user: {e}")
            raise AuthorizationException(f"Logout failed: {str(e)}")
    
    async def refresh_access_token(self, refresh_token: str, db: Session) -> TokenData:
        """
        Refresh access token using refresh token.
        
        Args:
            refresh_token: Refresh token
            db: Database session
            
        Returns:
            TokenData: New access and refresh tokens
        """
        try:
            logger.info("Refreshing access token")
            
            # Verify refresh token
            payload = self._decode_token(refresh_token)
            user_id = payload.get("sub")
            
            # Get user (mock implementation)
            user = await self._get_user_by_id(user_id, db)
            if not user:
                raise AuthenticationException("Invalid refresh token")
            
            # Generate new tokens
            access_token = self._create_access_token(user)
            new_refresh_token = self._create_refresh_token(user)
            
            # Calculate expiration
            expires_in = self.access_token_expire_minutes * 60
            expires_at = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
            
            token_data = TokenData(
                access_token=access_token,
                refresh_token=new_refresh_token,
                token_type="bearer",
                expires_in=expires_in,
                expires_at=expires_at
            )
            
            logger.info(f"Token refreshed successfully for user: {user_id}")
            return token_data
            
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            raise AuthenticationException(f"Token refresh failed: {str(e)}")
    
    async def verify_email(self, token: str, db: Session) -> Dict[str, Any]:
        """
        Verify user email address.
        
        Args:
            token: Email verification token
            db: Database session
            
        Returns:
            Dict: Verification result
        """
        try:
            logger.info(f"Verifying email with token: {token[:10]}...")
            
            # Find user by verification token (mock implementation)
            user = await self._get_user_by_verification_token(token, db)
            if not user:
                raise ValidationException("Invalid or expired verification token")
            
            # Update user status (mock implementation)
            await self._update_user_verification_status(user["id"], db)
            
            logger.info(f"Email verified successfully for user: {user['id']}")
            return {"verified": True, "user_id": user["id"]}
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"Error verifying email: {e}")
            raise ValidationException(f"Email verification failed: {str(e)}")
    
    async def resend_verification_email(self, email: str, db: Session) -> Dict[str, Any]:
        """
        Resend email verification.
        
        Args:
            email: User email
            db: Database session
            
        Returns:
            Dict: Resend result
        """
        try:
            logger.info(f"Resending verification email to: {email}")
            
            # Get user by email
            user = await self._get_user_by_email(email, db)
            if not user:
                raise UserNotFoundException(f"User with email {email} not found")
            
            # Check if already verified
            if user.get("email_verified"):
                return {"sent": False, "message": "Email already verified"}
            
            # Generate new verification token
            verification_token = self._generate_verification_token()
            
            # Update user with new token (mock implementation)
            await self._update_verification_token(user["id"], verification_token, db)
            
            # Send verification email (mock)
            await self._send_verification_email(email, verification_token)
            
            logger.info(f"Verification email resent to: {email}")
            return {"sent": True, "email": email}
            
        except UserNotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error resending verification email: {e}")
            raise ValidationException(f"Failed to resend verification email: {str(e)}")
    
    async def request_password_reset(self, email: str, db: Session) -> Dict[str, Any]:
        """
        Request password reset.
        
        Args:
            email: User email
            db: Database session
            
        Returns:
            Dict: Reset request result
        """
        try:
            logger.info(f"Password reset requested for: {email}")
            
            # Get user by email
            user = await self._get_user_by_email(email, db)
            if not user:
                raise UserNotFoundException(f"User with email {email} not found")
            
            # Generate reset token
            reset_token = self._generate_reset_token()
            reset_expires = datetime.utcnow() + timedelta(hours=1)
            
            # Update user with reset token (mock implementation)
            await self._update_reset_token(user["id"], reset_token, reset_expires, db)
            
            # Send reset email (mock)
            await self._send_password_reset_email(email, reset_token)
            
            logger.info(f"Password reset email sent to: {email}")
            return {"sent": True, "email": email}
            
        except UserNotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error requesting password reset: {e}")
            raise ValidationException(f"Password reset request failed: {str(e)}")
    
    async def reset_password(self, token: str, new_password: str, db: Session) -> Dict[str, Any]:
        """
        Reset password using reset token.
        
        Args:
            token: Password reset token
            new_password: New password
            db: Database session
            
        Returns:
            Dict: Reset result
        """
        try:
            logger.info(f"Resetting password with token: {token[:10]}...")
            
            # Find user by reset token (mock implementation)
            user = await self._get_user_by_reset_token(token, db)
            if not user:
                raise ValidationException("Invalid or expired reset token")
            
            # Hash new password
            password_hash = self._hash_password(new_password)
            
            # Update user password (mock implementation)
            await self._update_user_password(user["id"], password_hash, db)
            
            # Clear reset token (mock implementation)
            await self._clear_reset_token(user["id"], db)
            
            logger.info(f"Password reset successfully for user: {user['id']}")
            return {"reset": True, "user_id": user["id"]}
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"Error resetting password: {e}")
            raise ValidationException(f"Password reset failed: {str(e)}")
    
    async def get_current_user(self, token: str, db: Session) -> UserProfile:
        """
        Get current user from token.
        
        Args:
            token: Access token
            db: Database session
            
        Returns:
            UserProfile: Current user profile
        """
        try:
            # Decode token
            payload = self._decode_token(token)
            user_id = payload.get("sub")
            
            # Get user (mock implementation)
            user = await self._get_user_by_id(user_id, db)
            if not user:
                raise AuthenticationException("Invalid token")
            
            # Convert to UserProfile
            user_profile = UserProfile(
                id=user["id"],
                email=user["email"],
                first_name=user["first_name"],
                last_name=user["last_name"],
                phone_number=user.get("phone_number"),
                date_of_birth=user.get("date_of_birth"),
                country=user.get("country"),
                id_number=user.get("id_number"),
                bio=user.get("bio"),
                profile_picture_url=user.get("profile_picture_url"),
                status=UserStatus(user["status"]),
                role=UserRole(user["role"]),
                email_verified=user["email_verified"],
                created_at=user["created_at"],
                updated_at=user["updated_at"],
                last_login_at=user.get("last_login_at")
            )
            
            return user_profile
            
        except Exception as e:
            logger.error(f"Error getting current user: {e}")
            raise AuthenticationException(f"Failed to get current user: {str(e)}")
    
    async def update_user_profile(self, token: str, request: UserProfileUpdateRequest, db: Session) -> UserProfile:
        """
        Update user profile.
        
        Args:
            token: Access token
            request: Profile update request
            db: Database session
            
        Returns:
            UserProfile: Updated user profile
        """
        try:
            # Get current user
            current_user = await self.get_current_user(token, db)
            
            # Update user data (mock implementation)
            update_data = UserUpdate(
                first_name=request.first_name,
                last_name=request.last_name,
                phone_number=request.phone_number,
                date_of_birth=request.date_of_birth,
                country=request.country,
                bio=request.bio,
                profile_picture_url=request.profile_picture_url,
                updated_at=datetime.utcnow()
            )
            
            # Apply updates to current user
            updated_user = current_user.copy(update=update_data.dict(exclude_unset=True))
            
            logger.info(f"User profile updated: {current_user.id}")
            return updated_user
            
        except Exception as e:
            logger.error(f"Error updating user profile: {e}")
            raise ValidationException(f"Profile update failed: {str(e)}")
    
    async def change_password(self, token: str, request: PasswordChangeRequest, db: Session) -> Dict[str, Any]:
        """
        Change user password.
        
        Args:
            token: Access token
            request: Password change request
            db: Database session
            
        Returns:
            Dict: Change result
        """
        try:
            # Get current user
            current_user = await self.get_current_user(token, db)
            
            # Get user with password hash (mock implementation)
            user = await self._get_user_by_id(current_user.id, db)
            
            # Verify current password
            if not self._verify_password(request.current_password, user.get("password_hash", "")):
                raise AuthenticationException("Current password is incorrect")
            
            # Hash new password
            new_password_hash = self._hash_password(request.new_password)
            
            # Update password (mock implementation)
            await self._update_user_password(current_user.id, new_password_hash, db)
            
            logger.info(f"Password changed for user: {current_user.id}")
            return {"changed": True, "user_id": current_user.id}
            
        except AuthenticationException:
            raise
        except Exception as e:
            logger.error(f"Error changing password: {e}")
            raise ValidationException(f"Password change failed: {str(e)}")
    
    # Private helper methods
    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt."""
        # Truncate password to 72 bytes to match bcrypt's limitation
        password_bytes = password.encode('utf-8')
        password_bytes = password_bytes[:72]
        # Hash the password
        hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
        return hashed.decode('utf-8')
    
    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash."""
        # Check if hashed_password is a bcrypt hash (starts with $2a$ or $2b$)
        if hashed_password.startswith(('$2a$', '$2b$')):
            # Truncate password to 72 bytes to match bcrypt's limitation
            password_bytes = plain_password.encode('utf-8')
            password_bytes = password_bytes[:72]
            hashed_bytes = hashed_password.encode('utf-8')
            return bcrypt.checkpw(password_bytes, hashed_bytes)
        else:
            # If not a bcrypt hash, assume it's plain text and compare directly
            return plain_password == hashed_password
    
    def _create_access_token(self, user: Dict[str, Any]) -> str:
        """Create JWT access token."""
        now = datetime.utcnow()
        expire = now + timedelta(minutes=self.access_token_expire_minutes)
        
        payload = {
            "sub": user["id"],
            "email": user["email"],
            "role": user["role"],
            "exp": expire,
            "iat": now,
            "token_type": "access",
            "is_active": user.get("is_active", True),
            "is_verified": user.get("email_verified", True),
            "jti": secrets.token_urlsafe(16)
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def _create_refresh_token(self, user: Dict[str, Any]) -> str:
        """Create JWT refresh token."""
        now = datetime.utcnow()
        expire = now + timedelta(days=self.refresh_token_expire_days)
        
        payload = {
            "sub": user["id"],
            "email": user["email"],
            "type": "refresh",
            "exp": expire,
            "iat": now,
            "jti": secrets.token_urlsafe(16)
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def _decode_token(self, token: str) -> Dict[str, Any]:
        """Decode JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise AuthenticationException("Token has expired")
        except jwt.JWTError:
            raise AuthenticationException("Invalid token")
    
    def _generate_user_id(self) -> str:
        """Generate unique user ID."""
        return f"user_{secrets.token_urlsafe(16)}"
    
    def _generate_verification_token(self) -> str:
        """Generate email verification token."""
        return secrets.token_urlsafe(32)
    
    def _generate_reset_token(self) -> str:
        """Generate password reset token."""
        return secrets.token_urlsafe(32)
    
    # Database operations
    async def _get_user_by_email(self, email: str, db: Session) -> Optional[Dict[str, Any]]:
        """Get user by email."""
        try:
            from ..database.models import User as DBUser

            user = db.query(DBUser).filter(DBUser.email == email).first()
            if user:
                return {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "phone_number": user.phone_number,
                    "date_of_birth": user.date_of_birth,
                    "country": user.country,
                    "id_number": user.id_number,
                    "bio": user.bio,
                    "profile_picture_url": user.profile_picture_url,
                    "status": user.status,
                    "role": user.role,
                    "email_verified": user.email_verified,
                    "password_hash": user.password_hash,
                    "email_verification_token": user.email_verification_token,
                    "password_reset_token": user.password_reset_token,
                    "password_reset_expires": user.password_reset_expires,
                    "last_login_at": user.last_login_at,
                    "created_at": user.created_at,
                    "updated_at": user.updated_at,
                    "is_active": user.is_active
                }
            return None
        except Exception as e:
            logger.error(f"Database error in _get_user_by_email: {e}")
            raise AuthenticationException(f"Database connection error: {str(e)}")
    
    async def _get_user_by_id(self, user_id: str, db: Session) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        from ..database.models import User as DBUser

        user = db.query(DBUser).filter(DBUser.id == user_id).first()
        if user:
            return {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone_number": user.phone_number,
                "date_of_birth": user.date_of_birth,
                "country": user.country,
                "id_number": user.id_number,
                "bio": user.bio,
                "profile_picture_url": user.profile_picture_url,
                "status": user.status,
                "role": user.role,
                "email_verified": user.email_verified,
                "password_hash": user.password_hash,
                "email_verification_token": user.email_verification_token,
                "password_reset_token": user.password_reset_token,
                "password_reset_expires": user.password_reset_expires,
                "last_login_at": user.last_login_at,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
                "is_active": user.is_active
            }
        return None
    
    async def _get_user_by_verification_token(self, token: str, db: Session) -> Optional[Dict[str, Any]]:
        """Get user by verification token."""
        try:
            from ..database.models import User as DBUser

            user = db.query(DBUser).filter(DBUser.email_verification_token == token).first()
            if user:
                return {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "phone_number": user.phone_number,
                    "date_of_birth": user.date_of_birth,
                    "country": user.country,
                    "id_number": user.id_number,
                    "bio": user.bio,
                    "profile_picture_url": user.profile_picture_url,
                    "status": user.status,
                    "role": user.role,
                    "email_verified": user.email_verified,
                    "password_hash": user.password_hash,
                    "email_verification_token": user.email_verification_token,
                    "password_reset_token": user.password_reset_token,
                    "password_reset_expires": user.password_reset_expires,
                    "last_login_at": user.last_login_at,
                    "created_at": user.created_at,
                    "updated_at": user.updated_at,
                    "is_active": user.is_active
                }
            return None
        except Exception as e:
            logger.error(f"Error getting user by verification token: {e}")
            return None
    
    async def _get_user_by_reset_token(self, token: str, db: Session) -> Optional[Dict[str, Any]]:
        """Get user by reset token (mock implementation)."""
        return None
    
    async def _update_last_login(self, user_id: str, db: Session) -> None:
        """Update user last login timestamp."""
        try:
            from ..database.models import User as DBUser

            user = db.query(DBUser).filter(DBUser.id == user_id).first()
            if user:
                user.last_login_at = datetime.utcnow()
                user.updated_at = datetime.utcnow()
                db.commit()
                logger.info(f"Updated last login for user {user_id}")
        except Exception as e:
            logger.error(f"Error updating last login: {e}")
            db.rollback()
            raise
    
    async def _update_user_verification_status(self, user_id: str, db: Session) -> None:
        """Update user email verification status."""
        try:
            from ..database.models import User as DBUser

            user = db.query(DBUser).filter(DBUser.id == user_id).first()
            if user:
                user.email_verified = True
                user.status = "active"  # Set status to ACTIVE after verification
                user.updated_at = datetime.utcnow()
                db.commit()
                logger.info(f"User {user_id} email verified and status set to ACTIVE")
        except Exception as e:
            logger.error(f"Error updating user verification status: {e}")
            db.rollback()
            raise
    
    async def _update_verification_token(self, user_id: str, token: str, db: Session) -> None:
        """Update user verification token."""
        try:
            from ..database.models import User as DBUser

            user = db.query(DBUser).filter(DBUser.id == user_id).first()
            if user:
                user.email_verification_token = token
                user.updated_at = datetime.utcnow()
                db.commit()
                logger.info(f"Updated verification token for user {user_id}")
        except Exception as e:
            logger.error(f"Error updating verification token: {e}")
            db.rollback()
            raise
    
    async def _update_reset_token(self, user_id: str, token: str, expires: datetime, db: Session) -> None:
        """Update user reset token."""
        try:
            from ..database.models import User as DBUser

            user = db.query(DBUser).filter(DBUser.id == user_id).first()
            if user:
                user.password_reset_token = token
                user.password_reset_expires = expires
                user.updated_at = datetime.utcnow()
                db.commit()
                logger.info(f"Updated reset token for user {user_id}")
        except Exception as e:
            logger.error(f"Error updating reset token: {e}")
            db.rollback()
            raise
    
    async def _update_user_password(self, user_id: str, password_hash: str, db: Session) -> None:
        """Update user password."""
        try:
            from ..database.models import User as DBUser

            user = db.query(DBUser).filter(DBUser.id == user_id).first()
            if user:
                user.password_hash = password_hash
                user.updated_at = datetime.utcnow()
                db.commit()
                logger.info(f"Updated password for user {user_id}")
        except Exception as e:
            logger.error(f"Error updating user password: {e}")
            db.rollback()
            raise
    
    async def _clear_reset_token(self, user_id: str, db: Session) -> None:
        """Clear user reset token."""
        try:
            from ..database.models import User as DBUser

            user = db.query(DBUser).filter(DBUser.id == user_id).first()
            if user:
                user.password_reset_token = None
                user.password_reset_expires = None
                user.updated_at = datetime.utcnow()
                db.commit()
                logger.info(f"Cleared reset token for user {user_id}")
        except Exception as e:
            logger.error(f"Error clearing reset token: {e}")
            db.rollback()
            raise
    
    async def _invalidate_user_tokens(self, user_id: str, db: Session) -> None:
        """Invalidate all user tokens."""
        # Note: In a real implementation, you would invalidate tokens in Redis/cache
        # For now, this is a placeholder as token invalidation would require additional infrastructure
        logger.info(f"Token invalidation requested for user {user_id} (not implemented)")
    
    async def _send_verification_email(self, email: str, token: str) -> None:
        """Send email verification email (mock implementation)."""
        logger.info(f"Sending verification email to {email} with token {token[:10]}...")
    
    async def _send_password_reset_email(self, email: str, token: str) -> None:
        """Send password reset email (mock implementation)."""
        logger.info(f"Sending password reset email to {email} with token {token[:10]}...")
