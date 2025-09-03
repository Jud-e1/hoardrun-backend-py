"""
Global exception handlers for structured error responses.
"""
import logging
from datetime import datetime
from typing import Union

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .exceptions import FintechException
from ..models.base import ErrorResponse

logger = logging.getLogger(__name__)


async def fintech_exception_handler(request: Request, exc: FintechException) -> JSONResponse:
    """Handle custom fintech exceptions with structured responses."""
    
    # Get request ID from request state if available
    request_id = getattr(request.state, 'request_id', None)
    
    # Log the exception
    logger.error(
        f"FintechException occurred: {exc.error_code} - {exc.message}",
        extra={
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "details": exc.details,
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method
        }
    )
    
    # Create structured error response
    error_response = ErrorResponse(
        message=exc.message,
        error_code=exc.error_code,
        details=exc.details,
        request_id=request_id
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.dict()
    )


async def validation_exception_handler(
    request: Request, 
    exc: Union[RequestValidationError, ValidationError]
) -> JSONResponse:
    """Handle Pydantic validation errors with structured responses."""
    
    request_id = getattr(request.state, 'request_id', None)
    
    # Extract validation error details
    errors = []
    for error in exc.errors():
        field_path = " -> ".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field_path,
            "message": error["msg"],
            "type": error["type"],
            "input": error.get("input")
        })
    
    logger.warning(
        f"Validation error occurred: {len(errors)} validation errors",
        extra={
            "validation_errors": errors,
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method
        }
    )
    
    error_response = ErrorResponse(
        message="Validation failed",
        error_code="VALIDATION_ERROR",
        details={"validation_errors": errors},
        request_id=request_id
    )
    
    return JSONResponse(
        status_code=422,
        content=error_response.dict()
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTP exceptions with structured responses."""
    
    request_id = getattr(request.state, 'request_id', None)
    
    logger.warning(
        f"HTTP exception occurred: {exc.status_code} - {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "detail": exc.detail,
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method
        }
    )
    
    # Map common HTTP status codes to error codes
    error_code_mapping = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_SERVER_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE"
    }
    
    error_code = error_code_mapping.get(exc.status_code, "HTTP_ERROR")
    
    error_response = ErrorResponse(
        message=str(exc.detail),
        error_code=error_code,
        request_id=request_id
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.dict()
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions with structured responses."""
    
    request_id = getattr(request.state, 'request_id', None)
    
    logger.error(
        f"Unexpected exception occurred: {type(exc).__name__} - {str(exc)}",
        extra={
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method
        },
        exc_info=True
    )
    
    error_response = ErrorResponse(
        message="An unexpected error occurred",
        error_code="INTERNAL_SERVER_ERROR",
        details={"exception_type": type(exc).__name__} if logger.level <= logging.DEBUG else None,
        request_id=request_id
    )
    
    return JSONResponse(
        status_code=500,
        content=error_response.dict()
    )


def register_exception_handlers(app):
    """Register all exception handlers with the FastAPI app."""
    
    # Custom fintech exceptions
    app.add_exception_handler(FintechException, fintech_exception_handler)
    
    # Validation errors
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, validation_exception_handler)
    
    # HTTP exceptions
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    
    # Generic exception handler (catch-all)
    app.add_exception_handler(Exception, generic_exception_handler)