"""
Unit tests for exception handlers.
"""
import pytest
from unittest.mock import Mock, AsyncMock
from fastapi import Request, HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from decimal import Decimal

from ..core.exceptions import (
    FintechException,
    InsufficientFundsException,
    ValidationException
)
from ..core.exception_handlers import (
    fintech_exception_handler,
    validation_exception_handler,
    http_exception_handler,
    generic_exception_handler
)


class TestFintechExceptionHandler:
    """Test cases for fintech exception handler."""
    
    @pytest.fixture
    def mock_request(self):
        """Create a mock request object."""
        request = Mock(spec=Request)
        request.url.path = "/api/test"
        request.method = "POST"
        request.state = Mock()
        request.state.request_id = "req_123"
        return request
    
    @pytest.mark.asyncio
    async def test_fintech_exception_handler(self, mock_request):
        """Test handling of FintechException."""
        exc = InsufficientFundsException(
            available_balance=Decimal("100.00"),
            requested_amount=Decimal("150.00")
        )
        
        response = await fintech_exception_handler(mock_request, exc)
        
        assert response.status_code == 400
        
        # Parse response content
        import json
        content = json.loads(response.body.decode())
        
        assert content["status"] == "error"
        assert content["error_code"] == "INSUFFICIENT_FUNDS"
        assert "Insufficient funds" in content["message"]
        assert content["request_id"] == "req_123"
        assert "details" in content
        assert content["details"]["available_balance"] == "100.00"
    
    @pytest.mark.asyncio
    async def test_fintech_exception_handler_without_request_id(self, mock_request):
        """Test handling of FintechException without request ID."""
        mock_request.state.request_id = None
        
        exc = ValidationException("Test validation error")
        
        response = await fintech_exception_handler(mock_request, exc)
        
        assert response.status_code == 422
        
        import json
        content = json.loads(response.body.decode())
        
        assert content["request_id"] is None
        assert content["error_code"] == "VALIDATION_ERROR"


class TestValidationExceptionHandler:
    """Test cases for validation exception handler."""
    
    @pytest.fixture
    def mock_request(self):
        """Create a mock request object."""
        request = Mock(spec=Request)
        request.url.path = "/api/test"
        request.method = "POST"
        request.state = Mock()
        request.state.request_id = "req_456"
        return request
    
    @pytest.mark.asyncio
    async def test_validation_exception_handler(self, mock_request):
        """Test handling of validation errors."""
        # Create a mock validation error
        errors = [
            {
                "loc": ("field1",),
                "msg": "field required",
                "type": "value_error.missing",
                "input": None
            },
            {
                "loc": ("field2", "nested"),
                "msg": "ensure this value is greater than 0",
                "type": "value_error.number.not_gt",
                "input": -1
            }
        ]
        
        exc = Mock(spec=RequestValidationError)
        exc.errors.return_value = errors
        
        response = await validation_exception_handler(mock_request, exc)
        
        assert response.status_code == 422
        
        import json
        content = json.loads(response.body.decode())
        
        assert content["status"] == "error"
        assert content["error_code"] == "VALIDATION_ERROR"
        assert content["message"] == "Validation failed"
        assert content["request_id"] == "req_456"
        
        validation_errors = content["details"]["validation_errors"]
        assert len(validation_errors) == 2
        
        # Check first error
        assert validation_errors[0]["field"] == "field1"
        assert validation_errors[0]["message"] == "field required"
        assert validation_errors[0]["type"] == "value_error.missing"
        
        # Check second error
        assert validation_errors[1]["field"] == "field2 -> nested"
        assert validation_errors[1]["message"] == "ensure this value is greater than 0"
        assert validation_errors[1]["input"] == -1


class TestHTTPExceptionHandler:
    """Test cases for HTTP exception handler."""
    
    @pytest.fixture
    def mock_request(self):
        """Create a mock request object."""
        request = Mock(spec=Request)
        request.url.path = "/api/test"
        request.method = "GET"
        request.state = Mock()
        request.state.request_id = "req_789"
        return request
    
    @pytest.mark.asyncio
    async def test_http_exception_handler_404(self, mock_request):
        """Test handling of 404 HTTP exception."""
        exc = HTTPException(status_code=404, detail="Resource not found")
        
        response = await http_exception_handler(mock_request, exc)
        
        assert response.status_code == 404
        
        import json
        content = json.loads(response.body.decode())
        
        assert content["status"] == "error"
        assert content["error_code"] == "NOT_FOUND"
        assert content["message"] == "Resource not found"
        assert content["request_id"] == "req_789"
    
    @pytest.mark.asyncio
    async def test_http_exception_handler_401(self, mock_request):
        """Test handling of 401 HTTP exception."""
        exc = HTTPException(status_code=401, detail="Unauthorized access")
        
        response = await http_exception_handler(mock_request, exc)
        
        assert response.status_code == 401
        
        import json
        content = json.loads(response.body.decode())
        
        assert content["error_code"] == "UNAUTHORIZED"
        assert content["message"] == "Unauthorized access"
    
    @pytest.mark.asyncio
    async def test_http_exception_handler_unknown_status(self, mock_request):
        """Test handling of HTTP exception with unknown status code."""
        exc = HTTPException(status_code=418, detail="I'm a teapot")
        
        response = await http_exception_handler(mock_request, exc)
        
        assert response.status_code == 418
        
        import json
        content = json.loads(response.body.decode())
        
        assert content["error_code"] == "HTTP_ERROR"
        assert content["message"] == "I'm a teapot"


class TestGenericExceptionHandler:
    """Test cases for generic exception handler."""
    
    @pytest.fixture
    def mock_request(self):
        """Create a mock request object."""
        request = Mock(spec=Request)
        request.url.path = "/api/test"
        request.method = "POST"
        request.state = Mock()
        request.state.request_id = "req_generic"
        return request
    
    @pytest.mark.asyncio
    async def test_generic_exception_handler(self, mock_request):
        """Test handling of generic exceptions."""
        exc = ValueError("Something went wrong")
        
        response = await generic_exception_handler(mock_request, exc)
        
        assert response.status_code == 500
        
        import json
        content = json.loads(response.body.decode())
        
        assert content["status"] == "error"
        assert content["error_code"] == "INTERNAL_SERVER_ERROR"
        assert content["message"] == "An unexpected error occurred"
        assert content["request_id"] == "req_generic"
        
        # Details should not be included in production (when not in debug mode)
        # But exception_type might be included for debugging
        if "details" in content and content["details"]:
            assert content["details"]["exception_type"] == "ValueError"
    
    @pytest.mark.asyncio
    async def test_generic_exception_handler_without_request_id(self, mock_request):
        """Test handling of generic exceptions without request ID."""
        mock_request.state.request_id = None
        
        exc = RuntimeError("Runtime error occurred")
        
        response = await generic_exception_handler(mock_request, exc)
        
        assert response.status_code == 500
        
        import json
        content = json.loads(response.body.decode())
        
        assert content["request_id"] is None
        assert content["error_code"] == "INTERNAL_SERVER_ERROR"


class TestExceptionHandlerIntegration:
    """Integration tests for exception handlers."""
    
    @pytest.fixture
    def mock_request(self):
        """Create a mock request object."""
        request = Mock(spec=Request)
        request.url.path = "/api/integration/test"
        request.method = "PUT"
        request.state = Mock()
        request.state.request_id = "req_integration"
        return request
    
    @pytest.mark.asyncio
    async def test_exception_handler_response_format_consistency(self, mock_request):
        """Test that all exception handlers return consistent response format."""
        exceptions_and_handlers = [
            (InsufficientFundsException(Decimal("10"), Decimal("20")), fintech_exception_handler),
            (HTTPException(status_code=400, detail="Bad request"), http_exception_handler),
            (ValueError("Generic error"), generic_exception_handler)
        ]
        
        for exc, handler in exceptions_and_handlers:
            response = await handler(mock_request, exc)
            
            import json
            content = json.loads(response.body.decode())
            
            # All responses should have these fields
            assert "status" in content
            assert "message" in content
            assert "error_code" in content
            assert "timestamp" in content
            assert "request_id" in content
            
            # Status should always be "error"
            assert content["status"] == "error"
            
            # Should have valid timestamp format
            from datetime import datetime
            timestamp = datetime.fromisoformat(content["timestamp"].replace('Z', '+00:00'))
            assert isinstance(timestamp, datetime)
    
    @pytest.mark.asyncio
    async def test_exception_handler_logging_integration(self, mock_request, caplog):
        """Test that exception handlers properly log exceptions."""
        import logging
        
        # Set logging level to capture all logs
        caplog.set_level(logging.ERROR)
        
        exc = InsufficientFundsException(
            available_balance=Decimal("50.00"),
            requested_amount=Decimal("100.00")
        )
        
        await fintech_exception_handler(mock_request, exc)
        
        # Check that error was logged
        assert len(caplog.records) > 0
        log_record = caplog.records[0]
        assert log_record.levelname == "ERROR"
        assert "INSUFFICIENT_FUNDS" in log_record.message
    
    @pytest.mark.asyncio
    async def test_exception_details_serialization(self, mock_request):
        """Test that exception details are properly serialized."""
        exc = InsufficientFundsException(
            available_balance=Decimal("123.45"),
            requested_amount=Decimal("678.90"),
            currency="EUR"
        )
        
        response = await fintech_exception_handler(mock_request, exc)
        
        import json
        content = json.loads(response.body.decode())
        
        details = content["details"]
        assert details["available_balance"] == "123.45"
        assert details["requested_amount"] == "678.90"
        assert details["currency"] == "EUR"
        assert details["shortfall"] == "555.45"
        
        # All values should be strings (serializable)
        for key, value in details.items():
            assert isinstance(value, (str, int, float, bool, type(None)))


class TestExceptionHandlerEdgeCases:
    """Test edge cases for exception handlers."""
    
    @pytest.fixture
    def mock_request_minimal(self):
        """Create a minimal mock request object."""
        request = Mock(spec=Request)
        request.url.path = "/api/minimal"
        request.method = "GET"
        request.state = Mock()
        # No request_id set
        return request
    
    @pytest.mark.asyncio
    async def test_exception_handler_with_minimal_request(self, mock_request_minimal):
        """Test exception handlers with minimal request object."""
        # Remove request_id attribute entirely
        if hasattr(mock_request_minimal.state, 'request_id'):
            delattr(mock_request_minimal.state, 'request_id')
        
        exc = ValidationException("Minimal test error")
        
        response = await fintech_exception_handler(mock_request_minimal, exc)
        
        assert response.status_code == 422
        
        import json
        content = json.loads(response.body.decode())
        
        assert content["request_id"] is None
        assert content["error_code"] == "VALIDATION_ERROR"
    
    @pytest.mark.asyncio
    async def test_exception_handler_with_empty_details(self, mock_request_minimal):
        """Test exception handlers with empty details."""
        exc = FintechException(
            message="Test error",
            error_code="TEST_ERROR",
            details={}
        )
        
        response = await fintech_exception_handler(mock_request_minimal, exc)
        
        import json
        content = json.loads(response.body.decode())
        
        assert content["details"] == {}
        assert content["error_code"] == "TEST_ERROR"