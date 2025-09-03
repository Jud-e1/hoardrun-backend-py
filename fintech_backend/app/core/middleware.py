"""
Middleware stack for request handling, logging, rate limiting, and request tracking.
"""
import time
import uuid
from typing import Callable, Dict, Any
from collections import defaultdict, deque
from datetime import datetime, timedelta

from fastapi import Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from ..config.logging import set_correlation_id, get_logger, log_api_request
from ..config.settings import Settings
from ..models.base import ErrorResponse
from .exceptions import RateLimitExceededException

logger = get_logger("middleware")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging with timing and correlation ID tracking."""
    
    def __init__(self, app, settings: Settings):
        super().__init__(app)
        self.settings = settings
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with logging and timing."""
        
        # Generate and set correlation ID
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        set_correlation_id(correlation_id)
        
        # Store correlation ID in request state for access in handlers
        request.state.request_id = correlation_id
        
        # Log request start
        start_time = time.time()
        
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "request_start": True,
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "user_agent": request.headers.get("user-agent"),
                "client_ip": get_remote_address(request),
            }
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id
            
            # Log request completion
            log_api_request(
                logger=logger,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                user_id=getattr(request.state, 'user_id', None)
            )
            
            return response
            
        except Exception as exc:
            # Calculate duration for failed requests
            duration_ms = (time.time() - start_time) * 1000
            
            logger.error(
                f"Request failed: {request.method} {request.url.path}",
                extra={
                    "request_failed": True,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc),
                },
                exc_info=True
            )
            
            # Re-raise the exception to be handled by exception handlers
            raise


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to limit request body size."""
    
    def __init__(self, app, max_size: int):
        super().__init__(app)
        self.max_size = max_size
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check request size and process if within limits."""
        
        # Check content length if provided
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_size:
            return JSONResponse(
                status_code=413,
                content=ErrorResponse(
                    message=f"Request body too large. Maximum size: {self.max_size} bytes",
                    error_code="REQUEST_TOO_LARGE",
                    details={"max_size": self.max_size, "received_size": int(content_length)},
                    request_id=getattr(request.state, 'request_id', None)
                ).dict()
            )
        
        return await call_next(request)


class InMemoryRateLimiter:
    """In-memory rate limiter implementation."""
    
    def __init__(self):
        self.clients: Dict[str, deque] = defaultdict(deque)
    
    def is_allowed(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        """Check if request is allowed within rate limits."""
        now = datetime.now()
        window_start = now - timedelta(seconds=window_seconds)
        
        # Clean old requests
        client_requests = self.clients[key]
        while client_requests and client_requests[0] < window_start:
            client_requests.popleft()
        
        # Check if under limit
        if len(client_requests) < limit:
            client_requests.append(now)
            return True, limit - len(client_requests)
        
        # Calculate retry after time
        oldest_request = client_requests[0]
        retry_after = int((oldest_request + timedelta(seconds=window_seconds) - now).total_seconds())
        return False, retry_after


class CustomRateLimitMiddleware(BaseHTTPMiddleware):
    """Custom rate limiting middleware with in-memory storage."""
    
    def __init__(self, app, settings: Settings):
        super().__init__(app)
        self.settings = settings
        self.limiter = InMemoryRateLimiter()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Apply rate limiting to requests."""
        
        # Skip rate limiting for health check endpoints
        if request.url.path in ["/health", "/health/ready", "/health/live", "/"]:
            return await call_next(request)
        
        # Get client identifier
        client_ip = get_remote_address(request)
        user_id = getattr(request.state, 'user_id', None)
        rate_limit_key = user_id or client_ip
        
        # Check rate limit
        is_allowed, remaining_or_retry_after = self.limiter.is_allowed(
            key=rate_limit_key,
            limit=self.settings.rate_limit_requests,
            window_seconds=self.settings.rate_limit_window
        )
        
        if not is_allowed:
            logger.warning(
                f"Rate limit exceeded for {rate_limit_key}",
                extra={
                    "rate_limit_exceeded": True,
                    "client_ip": client_ip,
                    "user_id": user_id,
                    "path": request.url.path,
                    "retry_after": remaining_or_retry_after
                }
            )
            
            return JSONResponse(
                status_code=429,
                content=ErrorResponse(
                    message=f"Rate limit exceeded: {self.settings.rate_limit_requests} requests per {self.settings.rate_limit_window} seconds",
                    error_code="RATE_LIMIT_EXCEEDED",
                    details={
                        "limit": self.settings.rate_limit_requests,
                        "window_seconds": self.settings.rate_limit_window,
                        "retry_after_seconds": remaining_or_retry_after
                    },
                    request_id=getattr(request.state, 'request_id', None)
                ).dict(),
                headers={"Retry-After": str(remaining_or_retry_after)}
            )
        
        # Add rate limit headers to response
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.settings.rate_limit_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining_or_retry_after)
        response.headers["X-RateLimit-Window"] = str(self.settings.rate_limit_window)
        
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to responses."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response."""
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        
        return response


def setup_middleware(app, settings: Settings) -> None:
    """Setup all middleware for the FastAPI application."""
    
    # Security headers (applied first)
    app.add_middleware(SecurityHeadersMiddleware)
    
    # Request size limiting
    app.add_middleware(RequestSizeLimitMiddleware, max_size=settings.max_request_size)
    
    # Rate limiting
    app.add_middleware(CustomRateLimitMiddleware, settings=settings)
    
    # Request logging (applied early to capture all requests)
    app.add_middleware(RequestLoggingMiddleware, settings=settings)
    
    # CORS middleware (applied last so it can handle all responses)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )
    
    logger.info(
        "Middleware stack configured",
        extra={
            "middleware_setup": True,
            "cors_origins": settings.cors_origins,
            "rate_limit": f"{settings.rate_limit_requests}/{settings.rate_limit_window}s",
            "max_request_size": settings.max_request_size
        }
    )


# Rate limiter instance for use in endpoints
limiter = Limiter(key_func=get_remote_address)


def get_rate_limiter():
    """Get the rate limiter instance."""
    return limiter
