"""
Base Pydantic models with common fields and configurations.
"""
from datetime import datetime, UTC
from decimal import Decimal
from typing import Optional, Generic, TypeVar, List
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
    """Base model for API responses."""
    
    model_config = ConfigDict(
        use_enum_values=True
    )
    
    status: str = Field(default="success", description="Response status")
    message: Optional[str] = Field(None, description="Response message")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Response timestamp")


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
    
    data: List[T] = Field(..., description="List of items")
    page: int = Field(1, ge=1, description="Current page number")
    page_size: int = Field(20, ge=1, le=100, description="Number of items per page")
    total_items: int = Field(0, ge=0, description="Total number of items")
    total_pages: int = Field(0, ge=0, description="Total number of pages")
    
    @property
    def has_next(self) -> bool:
        """Check if there are more pages."""
        return self.page < self.total_pages
    
    @property
    def has_previous(self) -> bool:
        """Check if there are previous pages."""
        return self.page > 1


class SuccessResponse(BaseResponse):
    """Model for success responses."""
    
    status: str = Field(default="success", description="Success status")
    success: bool = Field(default=True, description="Success indicator")


class ErrorResponse(BaseResponse):
    """Model for error responses."""
    
    status: str = Field(default="error", description="Error status")
    error_code: str = Field(..., description="Specific error code")
    details: Optional[dict] = Field(None, description="Additional error details")
    request_id: Optional[str] = Field(None, description="Request correlation ID")
