"""
Base Pydantic models with common fields and configurations.
All response models should inherit from BaseResponse to avoid copy-paste.
"""
from datetime import datetime, UTC
from decimal import Decimal
from typing import Optional, Generic, TypeVar, List, Any, Dict
from pydantic import BaseModel as PydanticBaseModel, Field, ConfigDict

T = TypeVar('T')


class BaseRequest(PydanticBaseModel):
    """Base model for API requests."""

    model_config = ConfigDict(
        use_enum_values=True,
        validate_assignment=True,
        populate_by_name=True
    )


class BaseResponse(PydanticBaseModel):
    """
    Canonical base for ALL API response models.

    Usage:
        class AccountResponse(BaseResponse):
            data: dict = {}          # override as needed

        class CardListResponse(BaseResponse):
            data: list = []
    """

    model_config = ConfigDict(use_enum_values=True)

    success: bool = True
    message: str = ""
    data: Any = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TimestampMixin:
    """Mixin for models that need timestamp fields."""

    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")


class BaseModel(PydanticBaseModel):
    """Base model with common fields for all entities."""

    model_config = ConfigDict(
        use_enum_values=True,
        validate_assignment=True,
        populate_by_name=True
    )

    id: Optional[str] = Field(None, description="Unique identifier")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")


class PaginationRequest(BaseRequest):
    """Base model for pagination requests."""

    page: int = Field(1, ge=1, description="Current page number")
    page_size: int = Field(20, ge=1, le=100, description="Number of items per page")


class PaginatedResponse(BaseResponse, Generic[T]):
    """Base model for paginated responses."""

    data: List[T] = Field(default_factory=list, description="List of items")
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    total_items: int = Field(0, ge=0)
    total_pages: int = Field(0, ge=0)

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        return self.page > 1


class SuccessResponse(BaseResponse):
    """Model for success responses."""

    status: str = Field(default="success")


class ErrorResponse(BaseResponse):
    """Model for error responses."""

    success: bool = False
    status: str = Field(default="error")
    error_code: str = Field(..., description="Specific error code")
    details: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
