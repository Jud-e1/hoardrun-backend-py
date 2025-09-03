"""
Structured logging configuration with JSON formatting and correlation IDs.
"""
import json
import logging
import logging.config
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from contextvars import ContextVar

from .settings import Settings


# Context variable for correlation ID
correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


class CorrelationIdFilter(logging.Filter):
    """Logging filter to add correlation ID to log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation ID to the log record."""
        record.correlation_id = correlation_id.get() or str(uuid.uuid4())
        return True


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Create base log entry
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "correlation_id": getattr(record, 'correlation_id', None),
        }
        
        # Add exception information if present
        if record.exc_info and record.exc_info != (None, None, None):
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info) if record.exc_info else None,
            }
        
        # Add extra fields from the record
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in {
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
                'module', 'exc_info', 'exc_text', 'stack_info', 'lineno', 'funcName',
                'created', 'msecs', 'relativeCreated', 'thread', 'threadName',
                'processName', 'process', 'getMessage', 'correlation_id'
            }:
                extra_fields[key] = value
        
        if extra_fields:
            log_entry["extra"] = extra_fields
        
        return json.dumps(log_entry, default=str, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """Custom text formatter with correlation ID."""
    
    def __init__(self):
        super().__init__(
            fmt="%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )


def set_correlation_id(cid: Optional[str] = None) -> str:
    """Set correlation ID for the current context."""
    if cid is None:
        cid = str(uuid.uuid4())
    correlation_id.set(cid)
    return cid


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID."""
    return correlation_id.get()


def clear_correlation_id() -> None:
    """Clear correlation ID from current context."""
    correlation_id.set(None)


def setup_logging(settings: Settings) -> None:
    """Setup logging configuration based on settings."""
    
    # Determine formatter based on log format setting
    if settings.log_format == "json":
        formatter_class = JSONFormatter
        formatter_args = {}
    else:
        formatter_class = TextFormatter
        formatter_args = {}
    
    # Configure logging
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": formatter_class,
                **formatter_args
            }
        },
        "filters": {
            "correlation_id": {
                "()": CorrelationIdFilter,
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": settings.log_level,
                "formatter": "default",
                "filters": ["correlation_id"],
                "stream": sys.stdout,
            }
        },
        "loggers": {
            # Application loggers
            "fintech_backend": {
                "level": settings.log_level,
                "handlers": ["console"],
                "propagate": False,
            },
            # FastAPI loggers
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn.access": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn.error": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            # Third-party loggers
            "httpx": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False,
            },
            "httpcore": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False,
            },
        },
        "root": {
            "level": settings.log_level,
            "handlers": ["console"],
        }
    }
    
    # Add file handler if log file is specified
    if settings.log_file:
        logging_config["handlers"]["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": settings.log_level,
            "formatter": "default",
            "filters": ["correlation_id"],
            "filename": settings.log_file,
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "encoding": "utf-8",
        }
        
        # Add file handler to all loggers
        for logger_config in logging_config["loggers"].values():
            if "file" not in logger_config["handlers"]:
                logger_config["handlers"].append("file")
        
        logging_config["root"]["handlers"].append("file")
    
    # Apply logging configuration
    logging.config.dictConfig(logging_config)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the specified name."""
    return logging.getLogger(f"fintech_backend.{name}")


# Business event logging utilities
def log_business_event(
    logger: logging.Logger,
    event_type: str,
    event_data: Dict[str, Any],
    user_id: Optional[str] = None,
    level: int = logging.INFO
) -> None:
    """Log a business event with structured data."""
    logger.log(
        level,
        f"Business event: {event_type}",
        extra={
            "event_type": event_type,
            "event_data": event_data,
            "user_id": user_id,
            "business_event": True,
        }
    )


def log_api_request(
    logger: logging.Logger,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    user_id: Optional[str] = None
) -> None:
    """Log an API request with timing information."""
    logger.info(
        f"{method} {path} - {status_code} - {duration_ms:.2f}ms",
        extra={
            "api_request": True,
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "user_id": user_id,
        }
    )


def log_external_service_call(
    logger: logging.Logger,
    service_name: str,
    operation: str,
    duration_ms: float,
    success: bool,
    error_message: Optional[str] = None
) -> None:
    """Log an external service call with timing and success information."""
    level = logging.INFO if success else logging.WARNING
    message = f"External service call: {service_name}.{operation} - {'SUCCESS' if success else 'FAILED'} - {duration_ms:.2f}ms"
    
    extra_data = {
        "external_service_call": True,
        "service_name": service_name,
        "operation": operation,
        "duration_ms": duration_ms,
        "success": success,
    }
    
    if error_message:
        extra_data["error_message"] = error_message
    
    logger.log(level, message, extra=extra_data)