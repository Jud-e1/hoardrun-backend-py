"""
Unit tests for base models and validation.
"""
import pytest
from datetime import datetime
from decimal import Decimal
from pydantic import ValidationError

from ..models.base import (
    BaseModel,
    BaseRequest,
    BaseResponse,
    PaginatedResponse,
    ErrorResponse
)


class TestBaseModel:
    """Test cases for BaseModel."""
    
    def test_base_model_creation(self):
        """Test basic model creation with common fields."""
        model = BaseModel(
            id="test_id",
            created_at=datetime(2023, 1, 1, 12, 0, 0),
            updated_at=datetime(2023, 1, 2, 12, 0, 0)
        )
        
        assert model.id == "test_id"
        assert model.created_at == datetime(2023, 1, 1, 12, 0, 0)
        assert model.updated_at == datetime(2023, 1, 2, 12, 0, 0)
    
    def test_base_model_optional_fields(self):
        """Test that all fields are optional."""
        model = BaseModel()
        
        assert model.id is None
        assert model.created_at is None
        assert model.updated_at is None
    
    def test_base_model_json_encoding(self):
        """Test JSON encoding of datetime and decimal fields."""
        model = BaseModel(
            id="test_id",
            created_at=datetime(2023, 1, 1, 12, 0, 0),
            updated_at=datetime(2023, 1, 2, 12, 0, 0)
        )
        
        json_data = model.model_dump()
        assert json_data["id"] == "test_id"
        assert json_data["created_at"] == datetime(2023, 1, 1, 12, 0, 0)
        assert json_data["updated_at"] == datetime(2023, 1, 2, 12, 0, 0)
    
    def test_base_model_validation_assignment(self):
        """Test that validation occurs on assignment."""
        model = BaseModel()
        
        # Valid assignment
        model.id = "valid_id"
        assert model.id == "valid_id"


class TestBaseRequest:
    """Test cases for BaseRequest."""
    
    def test_base_request_creation(self):
        """Test basic request model creation."""
        request = BaseRequest()
        assert isinstance(request, BaseRequest)
    
    def test_base_request_config(self):
        """Test request model configuration."""
        # Test that the config is properly set
        assert BaseRequest.model_config.get('use_enum_values') is True
        assert BaseRequest.model_config.get('validate_assignment') is True


class TestBaseResponse:
    """Test cases for BaseResponse."""
    
    def test_base_response_defaults(self):
        """Test default values for response model."""
        response = BaseResponse()
        
        assert response.status == "success"
        assert response.message is None
        assert isinstance(response.timestamp, datetime)
    
    def test_base_response_custom_values(self):
        """Test custom values for response model."""
        custom_time = datetime(2023, 1, 1, 12, 0, 0)
        response = BaseResponse(
            status="custom",
            message="Custom message",
            timestamp=custom_time
        )
        
        assert response.status == "custom"
        assert response.message == "Custom message"
        assert response.timestamp == custom_time
    
    def test_base_response_json_encoding(self):
        """Test JSON encoding of response model."""
        response = BaseResponse()
        json_data = response.model_dump()
        
        assert json_data["status"] == "success"
        assert json_data["message"] is None
        assert isinstance(json_data["timestamp"], datetime)


class TestPaginatedResponse:
    """Test cases for PaginatedResponse."""
    
    def test_paginated_response_defaults(self):
        """Test default values for paginated response."""
        response = PaginatedResponse()
        
        assert response.page == 1
        assert response.page_size == 20
        assert response.total_items == 0
        assert response.total_pages == 0
    
    def test_paginated_response_custom_values(self):
        """Test custom values for paginated response."""
        response = PaginatedResponse(
            page=2,
            page_size=10,
            total_items=50,
            total_pages=5
        )
        
        assert response.page == 2
        assert response.page_size == 10
        assert response.total_items == 50
        assert response.total_pages == 5
    
    def test_paginated_response_has_next(self):
        """Test has_next property."""
        # Has next page
        response = PaginatedResponse(page=2, total_pages=5)
        assert response.has_next is True
        
        # No next page
        response = PaginatedResponse(page=5, total_pages=5)
        assert response.has_next is False
    
    def test_paginated_response_has_previous(self):
        """Test has_previous property."""
        # Has previous page
        response = PaginatedResponse(page=2, total_pages=5)
        assert response.has_previous is True
        
        # No previous page
        response = PaginatedResponse(page=1, total_pages=5)
        assert response.has_previous is False
    
    def test_paginated_response_validation(self):
        """Test validation of paginated response fields."""
        # Valid values
        response = PaginatedResponse(page=1, page_size=20)
        assert response.page == 1
        assert response.page_size == 20
        
        # Invalid page (less than 1)
        with pytest.raises(ValidationError):
            PaginatedResponse(page=0)
        
        # Invalid page_size (less than 1)
        with pytest.raises(ValidationError):
            PaginatedResponse(page_size=0)
        
        # Invalid page_size (greater than 100)
        with pytest.raises(ValidationError):
            PaginatedResponse(page_size=101)


class TestErrorResponse:
    """Test cases for ErrorResponse."""
    
    def test_error_response_defaults(self):
        """Test default values for error response."""
        response = ErrorResponse(error_code="TEST_ERROR")
        
        assert response.status == "error"
        assert response.error_code == "TEST_ERROR"
        assert response.details is None
        assert response.request_id is None
        assert isinstance(response.timestamp, datetime)
    
    def test_error_response_custom_values(self):
        """Test custom values for error response."""
        details = {"field": "test_field", "value": "test_value"}
        response = ErrorResponse(
            message="Custom error message",
            error_code="CUSTOM_ERROR",
            details=details,
            request_id="req_123"
        )
        
        assert response.status == "error"
        assert response.message == "Custom error message"
        assert response.error_code == "CUSTOM_ERROR"
        assert response.details == details
        assert response.request_id == "req_123"
    
    def test_error_response_required_fields(self):
        """Test that error_code is required."""
        # Valid with required field
        response = ErrorResponse(error_code="TEST_ERROR")
        assert response.error_code == "TEST_ERROR"
        
        # Invalid without required field
        with pytest.raises(ValidationError):
            ErrorResponse()


class TestModelIntegration:
    """Integration tests for model interactions."""
    
    def test_model_inheritance(self):
        """Test that models properly inherit from base classes."""
        # Test inheritance chain
        assert issubclass(BaseResponse, BaseRequest.__bases__[0])  # Both inherit from PydanticBaseModel
        assert issubclass(PaginatedResponse, BaseResponse)
        assert issubclass(ErrorResponse, BaseResponse)
    
    def test_model_serialization_consistency(self):
        """Test that all models serialize consistently."""
        models = [
            BaseModel(id="test"),
            BaseRequest(),
            BaseResponse(),
            PaginatedResponse(),
            ErrorResponse(error_code="TEST")
        ]
        
        for model in models:
            # Should be able to serialize to dict
            data = model.model_dump()
            assert isinstance(data, dict)
            
            # Should be able to serialize to JSON
            json_str = model.model_dump_json()
            assert isinstance(json_str, (str, bytes))
    
    def test_decimal_handling(self):
        """Test decimal handling in models."""
        # Create a test model with decimal field
        class TestModel(BaseModel):
            amount: Decimal
        
        model = TestModel(amount=Decimal("123.45"))
        assert model.amount == Decimal("123.45")
        
        # Test JSON encoding
        json_data = model.model_dump()
        # The decimal should be preserved as Decimal in model_dump
        assert json_data["amount"] == Decimal("123.45")