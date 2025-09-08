"""
Simplified base models to avoid recursion issues.
"""
from datetime import datetime, UTC
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class SimpleBaseModel(BaseModel):
    """Simple base model without inheritance issues."""
    
    model_config = ConfigDict(
        use_enum_values=True,
        validate_assignment=True,
        populate_by_name=True
    )


class SimpleRequest(BaseModel):
    """Simple request model."""
    
    model_config = ConfigDict(
        use_enum_values=True,
        validate_assignment=True,
        populate_by_name=True
    )


class SimpleResponse(BaseModel):
    """Simple response model."""
    
    model_config = ConfigDict(use_enum_values=True)
    
    status: str = Field(default="success", description="Response status")
    message: Optional[str] = Field(None, description="Response message")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Response timestamp")
