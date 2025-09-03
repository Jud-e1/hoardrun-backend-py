"""
Unit tests for configuration and logging functionality.
"""
import json
import logging
import os
import tempfile
import uuid
from unittest.mock import patch, MagicMock
from typing import Dict, Any

import pytest
from pydantic import ValidationError

from app.config.settings import Settings, get_settings, reload_settings
from app.config.logging import (
    setup_logging,
    get_logger,
    set_correlation_id,
    get_correlation_id,
    clear_correlation_id,
    JSONFormatter,
    TextFormatter,
    CorrelationIdFilter,
    log_business_event,
    log_api_request,
    log_external_service_call,
)


class TestSettings:
    """Test cases for Settings configuration."""
    
    def test_default_settings(self):
        """Test that default settings are loaded correctly."""
        settings = Settings()
        
        assert settings.app_name == "Fintech Backend API"
        assert settings.app_version == "1.0.0"
        assert settings.debug is False
        assert settings.environment == "development"
        assert settings.host == "0.0.0.0"
        assert settings.port == 8000
        assert settings.log_level == "INFO"
        assert settings.log_format == "json"
        assert settings.default_currency == "USD"
        assert "USD" in settings.supported_currencies
        assert settings.max_transfer_amount == 100000.0
        assert settings.min_transfer_amount == 1.0
    
    def test_environment_variable_override(self):
        """Test that environment variables override default settings."""
        with patch.dict(os.environ, {
            "APP_NAME": "Test Fintech API",
            "DEBUG": "true",
            "PORT": "9000",
            "LOG_LEVEL": "DEBUG",
            "DEFAULT_CURRENCY": "EUR"
        }):
            settings = Settings()
            
            assert settings.app_name == "Test Fintech API"
            assert settings.debug is True
            assert settings.port == 9000
            assert settings.log_level == "DEBUG"
            assert settings.default_currency == "EUR"
    
    def test_log_level_validation(self):
        """Test log level validation."""
        # Valid log levels
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            settings = Settings(log_level=level)
            assert settings.log_level == level
        
        # Invalid log level
        with pytest.raises(ValidationError) as exc_info:
            Settings(log_level="INVALID")
        
        assert "Log level must be one of" in str(exc_info.value)
    
    def test_log_format_validation(self):
        """Test log format validation."""
        # Valid formats
        for fmt in ["json", "text"]:
            settings = Settings(log_format=fmt)
            assert settings.log_format == fmt
        
        # Invalid format
        with pytest.raises(ValidationError) as exc_info:
            Settings(log_format="invalid")
        
        assert "Log format must be one of" in str(exc_info.value)
    
    def test_environment_validation(self):
        """Test environment validation."""
        # Valid environments
        for env in ["development", "staging", "production"]:
            settings = Settings(environment=env)
            assert settings.environment == env
        
        # Invalid environment
        with pytest.raises(ValidationError) as exc_info:
            Settings(environment="invalid")
        
        assert "Environment must be one of" in str(exc_info.value)
    
    def test_currency_validation(self):
        """Test currency code validation."""
        # Valid currency
        settings = Settings(default_currency="GBP")
        assert settings.default_currency == "GBP"
        
        # Invalid currency - too short
        with pytest.raises(ValidationError) as exc_info:
            Settings(default_currency="US")
        
        assert "3-letter alphabetic code" in str(exc_info.value)
        
        # Invalid currency - too long
        with pytest.raises(ValidationError) as exc_info:
            Settings(default_currency="USDD")
        
        assert "3-letter alphabetic code" in str(exc_info.value)
        
        # Invalid currency - contains numbers
        with pytest.raises(ValidationError) as exc_info:
            Settings(default_currency="US1")
        
        assert "3-letter alphabetic code" in str(exc_info.value)
    
    def test_supported_currencies_validation(self):
        """Test supported currencies validation."""
        # Valid currencies
        settings = Settings(supported_currencies=["USD", "EUR", "GBP"])
        assert settings.supported_currencies == ["USD", "EUR", "GBP"]
        
        # Invalid currency in list
        with pytest.raises(ValidationError) as exc_info:
            Settings(supported_currencies=["USD", "EU", "GBP"])
        
        assert "3-letter alphabetic code" in str(exc_info.value)
    
    def test_cors_origins_validation(self):
        """Test CORS origins validation."""
        # Valid specific origins
        settings = Settings(cors_origins=["http://localhost:3000", "https://example.com"])
        assert len(settings.cors_origins) == 2
        
        # Valid wildcard only
        settings = Settings(cors_origins=["*"])
        assert settings.cors_origins == ["*"]
        
        # Invalid - wildcard with other origins
        with pytest.raises(ValidationError) as exc_info:
            Settings(cors_origins=["*", "http://localhost:3000"])
        
        assert "cannot contain '*' with other origins" in str(exc_info.value)
    
    def test_get_settings_function(self):
        """Test get_settings function returns settings instance."""
        settings = get_settings()
        assert isinstance(settings, Settings)
        assert settings.app_name == "Fintech Backend API"
    
    def test_reload_settings_function(self):
        """Test reload_settings function creates new settings instance."""
        with patch.dict(os.environ, {"APP_NAME": "Reloaded API"}):
            settings = reload_settings()
            assert settings.app_name == "Reloaded API"


class TestLogging:
    """Test cases for logging configuration."""
    
    def test_correlation_id_context(self):
        """Test correlation ID context management."""
        # Initially no correlation ID
        assert get_correlation_id() is None
        
        # Set correlation ID
        test_id = "test-correlation-id"
        result_id = set_correlation_id(test_id)
        assert result_id == test_id
        assert get_correlation_id() == test_id
        
        # Auto-generate correlation ID
        auto_id = set_correlation_id()
        assert auto_id is not None
        assert get_correlation_id() == auto_id
        
        # Clear correlation ID
        clear_correlation_id()
        assert get_correlation_id() is None
    
    def test_correlation_id_filter(self):
        """Test CorrelationIdFilter adds correlation ID to log records."""
        filter_instance = CorrelationIdFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None
        )
        
        # Without correlation ID set
        result = filter_instance.filter(record)
        assert result is True
        assert hasattr(record, 'correlation_id')
        assert record.correlation_id is not None
        
        # With correlation ID set
        test_id = "test-id"
        set_correlation_id(test_id)
        record2 = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None
        )
        
        result = filter_instance.filter(record2)
        assert result is True
        assert record2.correlation_id == test_id
        
        clear_correlation_id()
    
    def test_json_formatter(self):
        """Test JSONFormatter formats log records as JSON."""
        formatter = JSONFormatter()
        set_correlation_id("test-correlation-id")
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.correlation_id = "test-correlation-id"
        record.funcName = "test_function"
        record.module = "test_module"
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert log_data["level"] == "INFO"
        assert log_data["logger"] == "test.logger"
        assert log_data["message"] == "Test message"
        assert log_data["module"] == "test_module"
        assert log_data["function"] == "test_function"
        assert log_data["line"] == 42
        assert log_data["correlation_id"] == "test-correlation-id"
        assert "timestamp" in log_data
        
        clear_correlation_id()
    
    def test_json_formatter_with_exception(self):
        """Test JSONFormatter handles exceptions correctly."""
        formatter = JSONFormatter()
        
        try:
            raise ValueError("Test exception")
        except ValueError as e:
            import sys
            exc_info = sys.exc_info()
            record = logging.LogRecord(
                name="test.logger",
                level=logging.ERROR,
                pathname="/path/to/file.py",
                lineno=42,
                msg="Error occurred",
                args=(),
                exc_info=exc_info
            )
            record.correlation_id = "test-id"
            record.funcName = "test_function"
            record.module = "test_module"
            
            formatted = formatter.format(record)
            log_data = json.loads(formatted)
            
            assert "exception" in log_data
            assert log_data["exception"]["type"] == "ValueError"
            assert log_data["exception"]["message"] == "Test exception"
            assert "traceback" in log_data["exception"]
    
    def test_json_formatter_with_extra_fields(self):
        """Test JSONFormatter includes extra fields."""
        formatter = JSONFormatter()
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.correlation_id = "test-id"
        record.funcName = "test_function"
        record.module = "test_module"
        record.user_id = "user123"
        record.request_id = "req456"
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert "extra" in log_data
        assert log_data["extra"]["user_id"] == "user123"
        assert log_data["extra"]["request_id"] == "req456"
    
    def test_text_formatter(self):
        """Test TextFormatter formats log records as text."""
        formatter = TextFormatter()
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.correlation_id = "test-correlation-id"
        
        formatted = formatter.format(record)
        
        assert "INFO" in formatted
        assert "test.logger" in formatted
        assert "Test message" in formatted
        assert "test-correlation-id" in formatted
    
    def test_setup_logging_json_format(self):
        """Test setup_logging with JSON format."""
        settings = Settings(log_format="json", log_level="DEBUG")
        
        with patch('logging.config.dictConfig') as mock_config:
            setup_logging(settings)
            
            mock_config.assert_called_once()
            config = mock_config.call_args[0][0]
            
            assert config["formatters"]["default"]["()"] == JSONFormatter
            assert config["handlers"]["console"]["level"] == "DEBUG"
            assert "correlation_id" in config["filters"]
    
    def test_setup_logging_text_format(self):
        """Test setup_logging with text format."""
        settings = Settings(log_format="text", log_level="INFO")
        
        with patch('logging.config.dictConfig') as mock_config:
            setup_logging(settings)
            
            mock_config.assert_called_once()
            config = mock_config.call_args[0][0]
            
            assert config["formatters"]["default"]["()"] == TextFormatter
            assert config["handlers"]["console"]["level"] == "INFO"
    
    def test_setup_logging_with_file(self):
        """Test setup_logging with file handler."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            settings = Settings(log_file=tmp_file.name)
            
            with patch('logging.config.dictConfig') as mock_config:
                setup_logging(settings)
                
                config = mock_config.call_args[0][0]
                
                assert "file" in config["handlers"]
                assert config["handlers"]["file"]["filename"] == tmp_file.name
                assert config["handlers"]["file"]["class"] == "logging.handlers.RotatingFileHandler"
        
        # Clean up
        os.unlink(tmp_file.name)
    
    def test_get_logger(self):
        """Test get_logger returns logger with correct name."""
        logger = get_logger("test_module")
        assert logger.name == "fintech_backend.test_module"
    
    def test_log_business_event(self):
        """Test log_business_event function."""
        logger = MagicMock()
        event_data = {"transaction_id": "tx123", "amount": 100.0}
        
        log_business_event(
            logger=logger,
            event_type="TRANSFER_INITIATED",
            event_data=event_data,
            user_id="user123",
            level=logging.INFO
        )
        
        logger.log.assert_called_once_with(
            logging.INFO,
            "Business event: TRANSFER_INITIATED",
            extra={
                "event_type": "TRANSFER_INITIATED",
                "event_data": event_data,
                "user_id": "user123",
                "business_event": True,
            }
        )
    
    def test_log_api_request(self):
        """Test log_api_request function."""
        logger = MagicMock()
        
        log_api_request(
            logger=logger,
            method="POST",
            path="/api/transfer",
            status_code=200,
            duration_ms=150.5,
            user_id="user123"
        )
        
        logger.info.assert_called_once_with(
            "POST /api/transfer - 200 - 150.50ms",
            extra={
                "api_request": True,
                "method": "POST",
                "path": "/api/transfer",
                "status_code": 200,
                "duration_ms": 150.5,
                "user_id": "user123",
            }
        )
    
    def test_log_external_service_call_success(self):
        """Test log_external_service_call function for successful calls."""
        logger = MagicMock()
        
        log_external_service_call(
            logger=logger,
            service_name="payment_gateway",
            operation="process_payment",
            duration_ms=250.0,
            success=True
        )
        
        logger.log.assert_called_once_with(
            logging.INFO,
            "External service call: payment_gateway.process_payment - SUCCESS - 250.00ms",
            extra={
                "external_service_call": True,
                "service_name": "payment_gateway",
                "operation": "process_payment",
                "duration_ms": 250.0,
                "success": True,
            }
        )
    
    def test_log_external_service_call_failure(self):
        """Test log_external_service_call function for failed calls."""
        logger = MagicMock()
        
        log_external_service_call(
            logger=logger,
            service_name="bank_api",
            operation="get_balance",
            duration_ms=5000.0,
            success=False,
            error_message="Connection timeout"
        )
        
        logger.log.assert_called_once_with(
            logging.WARNING,
            "External service call: bank_api.get_balance - FAILED - 5000.00ms",
            extra={
                "external_service_call": True,
                "service_name": "bank_api",
                "operation": "get_balance",
                "duration_ms": 5000.0,
                "success": False,
                "error_message": "Connection timeout",
            }
        )