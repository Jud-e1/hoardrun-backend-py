"""
SQLAlchemy User model for database operations.
"""
from sqlalchemy import Column, String, DateTime, Boolean, Text, Date, Enum as SQLEnum
from sqlalchemy.sql import func
from ..database.config import Base
from .auth import UserStatus, UserRole


class User(Base):
    """SQLAlchemy User model."""

    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}

    # Primary key
    id = Column(String(36), primary_key=True, index=True)

    # Authentication fields
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)

    # Personal information
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    phone_number = Column(String(20), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    country = Column(String(3), nullable=True)  # ISO 3166-1 alpha-3
    id_number = Column(String(50), nullable=True)

    # Profile information
    bio = Column(Text, nullable=True)
    profile_picture_url = Column(String(500), nullable=True)

    # Account status and role
    status = Column(SQLEnum(UserStatus), default=UserStatus.PENDING, nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.USER, nullable=False)

    # Email verification
    email_verified = Column(Boolean, default=False, nullable=False)
    email_verification_code = Column(String(6), nullable=True, unique=True)

    # Password reset
    password_reset_token = Column(String(255), nullable=True)
    password_reset_expires = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<User(id='{self.id}', email='{self.email}', status='{self.status}')>"
