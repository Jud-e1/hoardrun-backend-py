"""
Authentication service for user registration, login, and profile management.
"""

import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
import jwt

from ..models.auth import (
    UserRegisterRequest, UserLoginRequest, UserProfile, TokenData, LoginData,
    UserProfileUpdateRequest, PasswordChangeRequest, UserCreate, UserUpdate,
    UserStatus, UserRole, JWTPayload
)
from ..core.exceptions import (
    ValidationException, AuthenticationException, AuthorizationException,
    UserNotFoundException, EmailAlreadyExistsException
)
from ..auth import passwords
from ..auth.signing_key import ALGORITHM, jwt_secret
from ..config.settings import get_settings
from ..config.logging import get_logger
from .email_service import get_email_service
from . import auth_codes, login_throttle
from .inbox import notify

logger = get_logger(__name__)


def password_problem(password: str) -> Optional[str]:
    """Why a new password isn't strong enough (the sign-up rule), or None."""
    if len(password or "") < 8:
        return "Use at least 8 characters."
    if not any(c.isupper() for c in password) or not any(c.islower() for c in password):
        return "Use upper and lower case letters."
    if not any(c.isdigit() for c in password):
        return "Include at least one number."
    return None
settings = get_settings()

# Using bcrypt directly for password hashing


class AuthService:
    """Authentication service for handling user authentication and authorization."""

    def __init__(self):
        self.settings = get_settings()
        self.secret_key = jwt_secret()
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
            EmailAlreadyExistsException: If email is already registered and verified
            ValidationException: If validation fails
        """
        try:
            logger.info(f"Registering user with email: {request.email}")

            # Check if user already exists
            existing_user = await self._get_user_by_email(request.email, db)
            if existing_user:
                # If user exists but email is not verified, resend verification email
                if not existing_user.get("email_verified"):
                    logger.info(f"User exists but not verified: {request.email}")

                    # A fresh code, unless one went out in the last minute
                    if not auth_codes.too_soon(db, existing_user["id"], auth_codes.VERIFY):
                        verification_code = auth_codes.issue_verification_code(db, existing_user["id"])
                        await self._send_verification_email(existing_user["email"], verification_code, existing_user.get("first_name"))

                    # Return user profile with a flag indicating email needs verification
                    user_profile = UserProfile(
                        id=existing_user["id"],
                        email=existing_user["email"],
                        first_name=existing_user["first_name"],
                        last_name=existing_user["last_name"],
                        phone_number=existing_user.get("phone_number"),
                        date_of_birth=existing_user.get("date_of_birth"),
                        country=existing_user.get("country"),
                        id_number=existing_user.get("id_number"),
                        status=UserStatus(existing_user["status"]),
                        role=UserRole(existing_user["role"]),
                        email_verified=existing_user["email_verified"],
                        created_at=existing_user["created_at"],
                        updated_at=existing_user["updated_at"]
                    )

                    logger.info(f"Verification email resent to: {request.email}")
                    return user_profile
                else:
                    # User exists and is verified
                    raise EmailAlreadyExistsException(f"User with email {request.email} already exists")

            # Hash password
            password_hash = self._hash_password(request.password)

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

            # Only a hash of the code is kept (auth_codes)
            verification_code = auth_codes.issue_verification_code(db, db_user.id)
            await self._send_verification_email(user_data.email, verification_code, db_user.first_name)

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

            # Too many wrong passwords recently: refuse before checking this one
            wait = login_throttle.locked_for(db, request.email)
            if wait is not None:
                minutes = max(1, int(wait.total_seconds() // 60) + 1)
                raise AuthenticationException(
                    f"Too many wrong passwords. Try again in {minutes} minute{'s' if minutes != 1 else ''}, or reset your password.")

            # Get user by email
            user = await self._get_user_by_email(request.email, db)

            # Truncate password to 72 bytes to match bcrypt's limitation
            password_bytes = request.password.encode('utf-8')
            password_bytes = password_bytes[:72]
            truncated_password = password_bytes.decode('utf-8', errors='ignore')

            # An unknown email gets the same answer as a wrong password, so sign-in can't reveal who has an account
            if not user or not self._verify_password(truncated_password, user.get("password_hash", "")):
                if login_throttle.record_failure(db, request.email) and user:
                    notify(db, user["id"], "security", "Sign-in locked",
                           "Someone entered the wrong password for your Hoardrun account 5 times, so password sign-in is "
                           "paused for 15 minutes. If this wasn't you, reset your password.",
                           link="/forgot-password", key=f"login-locked:{datetime.utcnow().strftime('%Y%m%d%H%M')}")
                    db.commit()
                raise AuthenticationException("Invalid email or password")
            login_throttle.clear(db, request.email)

            # Check if user is active
            if user.get("status") == "deactivated":
                raise AuthenticationException("This account is closed.")
            if user.get("status") != UserStatus.ACTIVE.value:
                raise AuthenticationException("Account is not active. Please verify your email.")

            login_data = await self.login_data_for(user, db)

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

    async def login_data_for(self, user: Dict[str, Any], db: Session) -> LoginData:
        """Tokens and profile for a user who has proved who they are (password or Google)."""
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
        return login_data

    async def verify_email(self, code: str, db: Session, email: Optional[str] = None) -> Dict[str, Any]:
        """Confirm an email address with the 6-digit code sent to it. The code only works with its own email."""
        if not email:
            raise ValidationException("Enter the email you signed up with, then the code.")
        try:
            user = auth_codes.check_verification_code(db, email, code)
        except auth_codes.CodeError as error:
            raise ValidationException(str(error))
        if not user.email_verified:
            await self._update_user_verification_status(user.id, db)
        logger.info(f"Email verified for user: {user.id}")
        return {"verified": True, "user_id": user.id, "email": user.email, "message": "Email verified"}

    async def resend_verification_email(self, email: str, db: Session) -> Dict[str, Any]:
        """Send a new code. The answer is the same whether or not the email has an account."""
        user = await self._get_user_by_email(email, db)
        if user and not user.get("email_verified") and user.get("status") != "deactivated" \
                and not auth_codes.too_soon(db, user["id"], auth_codes.VERIFY):
            verification_code = auth_codes.issue_verification_code(db, user["id"])
            await self._send_verification_email(user["email"], verification_code, user.get("first_name"))
        return {"sent": True}

    async def send_verification_email_background(self, email: str, verification_code: str):
        """
        Background task to send verification email.

        Args:
            email: User email
            verification_code: Verification code
        """
        try:
            await self._send_verification_email(email, verification_code)
            logger.info(f"Background verification email sent to: {email}")
        except Exception as e:
            logger.error(f"Background email send failed for {email}: {e}")

    async def request_password_reset(self, email: str, db: Session) -> Dict[str, Any]:
        """Email a one-time reset link. The answer is the same whether or not the email has an account."""
        user = await self._get_user_by_email(email, db)
        if user and user.get("status") != "deactivated" and not auth_codes.too_soon(db, user["id"], auth_codes.RESET):
            token = auth_codes.issue_reset_token(db, user["id"])
            await self._send_password_reset_email(user["email"], token, user.get("first_name"))
        return {"sent": True}

    async def reset_password(self, token: str, new_password: str, db: Session) -> Dict[str, Any]:
        """Set a new password with a reset link. The link works once."""
        problem = password_problem(new_password)
        if problem:
            raise ValidationException(problem)
        try:
            user = auth_codes.use_reset_token(db, token)
        except auth_codes.CodeError as error:
            raise ValidationException(str(error))
        user.password_hash = self._hash_password(new_password)
        # A new password ends any sign-in lock
        login_throttle.clear(db, user.email)
        user.updated_at = datetime.utcnow()
        # A security notice, so it's also emailed after the commit
        notify(db, user.id, "security", "Your password was changed",
               "Your Hoardrun password was just reset from an email link. If this wasn't you, reset it again right away.",
               link="/settings", key=f"password-reset:{user.updated_at.isoformat()}")
        db.commit()
        logger.info(f"Password reset for user: {user.id}")
        return {"reset": True}

    def reset_link_is_live(self, token: str, db: Session) -> bool:
        return auth_codes.reset_token_is_live(db, token)

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
            # Refresh tokens only work on the refresh endpoint
            if payload.get("type") == "refresh":
                raise AuthenticationException("Invalid token")
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

            from ..database.models import User as DBUser

            # Only change what was sent, so a partial save can't blank other fields
            changes = request.dict(exclude_unset=True)
            db_user = db.query(DBUser).filter(DBUser.id == current_user.id).first()
            if not db_user:
                raise ValidationException("User not found")
            for field, value in changes.items():
                setattr(db_user, field, value)
            db.commit()

            updated_user = current_user.copy(update=changes)

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

            await self._update_user_password(current_user.id, new_password_hash, db)
            await get_email_service().send_password_changed_email(user.get("email"), user.get("first_name"))

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
        return passwords.hash_password(password)

    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Check a password against its bcrypt hash; a stored value that isn't one never matches."""
        return passwords.verify_password(plain_password, hashed_password)

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

        return jwt.encode(payload, self.secret_key, algorithm=ALGORITHM)

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

        return jwt.encode(payload, self.secret_key, algorithm=ALGORITHM)

    def _decode_token(self, token: str) -> Dict[str, Any]:
        """Decode JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            raise AuthenticationException("Token has expired")
        except jwt.InvalidTokenError:
            raise AuthenticationException("Invalid token")

    def _generate_user_id(self) -> str:
        """Generate unique user ID."""
        return f"user_{secrets.token_urlsafe(16)}"

    def _generate_verification_code(self) -> str:
        """Generate a 6-digit verification code."""
        return ''.join(secrets.choice('0123456789') for _ in range(6))

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
                "email_verification_code": user.email_verification_code,
                "password_reset_token": user.password_reset_token,
                    "password_reset_expires": user.password_reset_expires,
                    "last_login_at": user.last_login_at,
                    "created_at": user.created_at,
                    "updated_at": user.updated_at,
                    "is_active": user.is_active
                }
            return None
        except Exception as e:
            logger.error(f"Error getting user by verification code: {e}")
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

    async def _update_verification_code(self, user_id: str, code: str, db: Session) -> None:
        """Update user verification code."""
        try:
            from ..database.models import User as DBUser

            user = db.query(DBUser).filter(DBUser.id == user_id).first()
            if user:
                user.email_verification_code = code
                user.updated_at = datetime.utcnow()
                db.commit()
                logger.info(f"Updated verification code for user {user_id}")
        except Exception as e:
            logger.error(f"Error updating verification code: {e}")
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

    async def _send_verification_email(self, email: str, token: str, name: Optional[str] = None) -> None:
        """Send email verification email using Resend."""
        email_service = get_email_service()
        success = await email_service.send_verification_email(email, token, name)
        if success:
            logger.info(f"Verification email sent to {email}")
        else:
            logger.error(f"Failed to send verification email to {email}")

    async def _send_password_reset_email(self, email: str, token: str, name: Optional[str] = None) -> None:
        """Send password reset email using Resend."""
        email_service = get_email_service()
        success = await email_service.send_password_reset_email(email, token, name)
        if success:
            logger.info(f"Password reset email sent to {email}")
        else:
             logger.error(f"Failed to send password reset email to {email}")


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
                "email_verification_code": user.email_verification_code,
                "password_reset_token": user.password_reset_token,
                "password_reset_expires": user.password_reset_expires,
                "last_login_at": user.last_login_at,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
                "is_active": user.is_active
            }
        return None

    async def _get_user_by_verification_code(self, code: str, db: Session) -> Optional[Dict[str, Any]]:
        """Get user by verification code."""
        try:
            from ..database.models import User as DBUser

            user = db.query(DBUser).filter(DBUser.email_verification_code == code).first()
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
                    "email_verification_code": user.email_verification_code,
                    "password_reset_token": user.password_reset_token,
                    "password_reset_expires": user.password_reset_expires,
                    "last_login_at": user.last_login_at,
                    "created_at": user.created_at,
                    "updated_at": user.updated_at,
                    "is_active": user.is_active
                }
            return None
        except Exception as e:
            logger.error(f"Error getting user by verification code: {e}")
            return None
