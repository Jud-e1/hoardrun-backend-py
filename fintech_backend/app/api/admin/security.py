"""
Security & Audit Administration API endpoints for security monitoring and audit logs.
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
import asyncio
from datetime import datetime, timedelta
from pydantic import BaseModel

from ...database.config import get_db
from ...config.logging import get_logger
from ...core.auth import get_current_user
from ...utils.response import success_response
from ...services.audit_service import AuditService

logger = get_logger(__name__)
security = HTTPBearer()

router = APIRouter(prefix="/security", tags=["Admin Security & Audit"])


class SecurityEventFilter(BaseModel):
    event_type: Optional[str] = None
    severity: Optional[str] = None
    user_id: Optional[str] = None
    ip_address: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class AuditLogFilter(BaseModel):
    action: Optional[str] = None
    resource_type: Optional[str] = None
    user_id: Optional[str] = None
    admin_user_id: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class LockAccountRequest(BaseModel):
    user_id: str
    reason: str
    duration_hours: Optional[int] = 24


def require_admin(current_user: dict) -> dict:
    """Check if user has admin role"""
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def get_audit_service():
    """Dependency to get audit service instance"""
    return AuditService()


@router.get("/audit/logs", response_model=dict)
async def get_audit_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    filters: AuditLogFilter = Depends(),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    audit_service: AuditService = Depends(get_audit_service)
):
    """
    Get audit logs with advanced filtering (Admin only).

    Returns paginated audit logs with comprehensive filtering options.
    """
    try:
        logger.info(f"Admin API: Getting audit logs - page {page}, limit {limit}")

        token = credentials.credentials
        current_user = await get_current_user(token, db)
        require_admin(current_user)

        # Convert filters to dict
        filter_dict = filters.dict(exclude_unset=True)

        # Get audit logs
        result = await audit_service.get_audit_logs_admin(
            db=db,
            page=page,
            limit=limit,
            filters=filter_dict
        )

        return success_response(
            data={
                "audit_logs": result["logs"],
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": result["total"],
                    "pages": result["pages"]
                },
                "filters": filter_dict
            },
            message="Audit logs retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Error getting audit logs: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/events", response_model=dict)
async def get_security_events(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    event_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None, regex="^(low|medium|high|critical)$"),
    status: Optional[str] = Query(None, regex="^(active|resolved|dismissed)$"),
    user_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Get security events with filtering (Admin only).

    Returns paginated security events with severity levels and status.
    """
    try:
        logger.info(f"Admin API: Getting security events - page {page}, limit {limit}")

        token = credentials.credentials
        current_user = await get_current_user(token, db)
        require_admin(current_user)

        # Mock security events data (in real implementation, this would query security event database)
        mock_events = [
            {
                "event_id": f"sec_{i+1}",
                "event_type": "failed_login" if i % 3 == 0 else "suspicious_activity" if i % 3 == 1 else "unauthorized_access",
                "severity": "high" if i % 5 == 0 else "medium" if i % 3 == 0 else "low",
                "status": "active" if i % 4 != 0 else "resolved",
                "user_id": f"user_{1000 + (i % 50)}",
                "ip_address": f"192.168.1.{i % 255}",
                "description": f"Security event description {i+1}",
                "detected_at": (datetime.utcnow() - timedelta(hours=i)).isoformat(),
                "resolved_at": (datetime.utcnow() - timedelta(hours=i//2)).isoformat() if i % 4 == 0 else None,
                "details": {
                    "user_agent": "Mozilla/5.0...",
                    "location": "Unknown",
                    "attempts": 3 + (i % 10)
                }
            }
            for i in range(200)  # Mock 200 events
        ]

        # Apply filters
        if event_type:
            mock_events = [event for event in mock_events if event["event_type"] == event_type]
        if severity:
            mock_events = [event for event in mock_events if event["severity"] == severity]
        if status:
            mock_events = [event for event in mock_events if event["status"] == status]
        if user_id:
            mock_events = [event for event in mock_events if event["user_id"] == user_id]

        # Date filtering
        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            mock_events = [event for event in mock_events if datetime.fromisoformat(event["detected_at"]) >= start_dt]
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            mock_events = [event for event in mock_events if datetime.fromisoformat(event["detected_at"]) <= end_dt]

        # Paginate
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_events = mock_events[start_idx:end_idx]

        events_data = {
            "events": paginated_events,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": len(mock_events),
                "pages": (len(mock_events) + limit - 1) // limit
            },
            "filters": {
                "event_type": event_type,
                "severity": severity,
                "status": status,
                "user_id": user_id,
                "start_date": start_date,
                "end_date": end_date
            },
            "summary": {
                "total_events": len(mock_events),
                "active_events": len([e for e in mock_events if e["status"] == "active"]),
                "critical_events": len([e for e in mock_events if e["severity"] == "critical"]),
                "high_severity": len([e for e in mock_events if e["severity"] == "high"])
            }
        }

        return success_response(
            data=events_data,
            message="Security events retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Error getting security events: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/access-attempts", response_model=dict)
async def get_failed_login_attempts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user_id: Optional[str] = Query(None),
    ip_address: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Get failed login attempts (Admin only).

    Returns paginated list of failed authentication attempts.
    """
    try:
        logger.info(f"Admin API: Getting failed login attempts - page {page}, limit {limit}")

        token = credentials.credentials
        current_user = await get_current_user(token, db)
        require_admin(current_user)

        # Mock failed login attempts data
        mock_attempts = [
            {
                "attempt_id": f"attempt_{i+1}",
                "user_id": f"user_{1000 + (i % 30)}" if i % 5 != 0 else None,  # Some attempts without user_id
                "email": f"user{1000 + (i % 30)}@example.com" if i % 5 != 0 else f"unknown{i}@example.com",
                "ip_address": f"192.168.1.{i % 255}",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "attempted_at": (datetime.utcnow() - timedelta(minutes=i*5)).isoformat(),
                "failure_reason": "invalid_password" if i % 3 == 0 else "account_locked" if i % 3 == 1 else "invalid_email",
                "location": "Unknown",
                "consecutive_failures": 1 + (i % 5)
            }
            for i in range(150)  # Mock 150 attempts
        ]

        # Apply filters
        if user_id:
            mock_attempts = [attempt for attempt in mock_attempts if attempt["user_id"] == user_id]
        if ip_address:
            mock_attempts = [attempt for attempt in mock_attempts if attempt["ip_address"] == ip_address]

        # Date filtering
        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            mock_attempts = [attempt for attempt in mock_attempts if datetime.fromisoformat(attempt["attempted_at"]) >= start_dt]
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            mock_attempts = [attempt for attempt in mock_attempts if datetime.fromisoformat(attempt["attempted_at"]) <= end_dt]

        # Paginate
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_attempts = mock_attempts[start_idx:end_idx]

        attempts_data = {
            "attempts": paginated_attempts,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": len(mock_attempts),
                "pages": (len(mock_attempts) + limit - 1) // limit
            },
            "filters": {
                "user_id": user_id,
                "ip_address": ip_address,
                "start_date": start_date,
                "end_date": end_date
            },
            "summary": {
                "total_attempts": len(mock_attempts),
                "unique_ips": len(set(attempt["ip_address"] for attempt in mock_attempts)),
                "unique_users": len(set(attempt["user_id"] for attempt in mock_attempts if attempt["user_id"])),
                "recent_attempts": len([a for a in mock_attempts if datetime.fromisoformat(a["attempted_at"]) > datetime.utcnow() - timedelta(hours=1)])
            }
        }

        return success_response(
            data=attempts_data,
            message="Failed login attempts retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Error getting failed login attempts: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/lock-account", response_model=dict)
async def lock_user_account(
    lock_request: LockAccountRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Lock a user account for security reasons (Admin only).

    Temporarily locks a user account to prevent access.
    """
    try:
        logger.info(f"Admin API: Locking account {lock_request.user_id} for {lock_request.duration_hours} hours")

        token = credentials.credentials
        current_user = await get_current_user(token, db)
        require_admin(current_user)

        # In a real implementation, this would update the user's account status
        # For now, we'll simulate the account lock
        lock_until = datetime.utcnow() + timedelta(hours=lock_request.duration_hours)

        lock_result = {
            "user_id": lock_request.user_id,
            "locked": True,
            "locked_until": lock_until.isoformat(),
            "reason": lock_request.reason,
            "locked_by": current_user["user_id"],
            "locked_at": datetime.utcnow().isoformat(),
            "duration_hours": lock_request.duration_hours
        }

        # Log the security action
        logger.warning(f"Account {lock_request.user_id} locked by admin {current_user['user_id']}: {lock_request.reason}")

        return success_response(
            data=lock_result,
            message=f"Account locked for {lock_request.duration_hours} hours"
        )

    except Exception as e:
        logger.error(f"Error locking account {lock_request.user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/permissions", response_model=dict)
async def get_permissions_overview(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Get permissions overview (Admin only).

    Returns current permission structure and role assignments.
    """
    try:
        logger.info("Admin API: Getting permissions overview")

        token = credentials.credentials
        current_user = await get_current_user(token, db)
        require_admin(current_user)

        # Mock permissions data
        permissions_data = {
            "roles": {
                "admin": {
                    "description": "Full system access",
                    "permissions": [
                        "user_management",
                        "system_monitoring",
                        "financial_oversight",
                        "security_audit",
                        "system_configuration"
                    ],
                    "user_count": 3
                },
                "moderator": {
                    "description": "Limited administrative access",
                    "permissions": [
                        "user_support",
                        "content_moderation",
                        "basic_reporting"
                    ],
                    "user_count": 5
                },
                "user": {
                    "description": "Standard user access",
                    "permissions": [
                        "account_management",
                        "transactions",
                        "profile_settings"
                    ],
                    "user_count": 1250
                }
            },
            "permissions": {
                "user_management": {
                    "description": "Create, update, delete users",
                    "roles": ["admin"]
                },
                "system_monitoring": {
                    "description": "View system health and metrics",
                    "roles": ["admin"]
                },
                "financial_oversight": {
                    "description": "Monitor financial transactions",
                    "roles": ["admin"]
                },
                "security_audit": {
                    "description": "Access security logs and events",
                    "roles": ["admin"]
                },
                "system_configuration": {
                    "description": "Modify system settings",
                    "roles": ["admin"]
                },
                "user_support": {
                    "description": "Handle user support requests",
                    "roles": ["admin", "moderator"]
                },
                "content_moderation": {
                    "description": "Moderate user content",
                    "roles": ["admin", "moderator"]
                },
                "basic_reporting": {
                    "description": "View basic system reports",
                    "roles": ["admin", "moderator"]
                },
                "account_management": {
                    "description": "Manage personal account",
                    "roles": ["user"]
                },
                "transactions": {
                    "description": "Perform financial transactions",
                    "roles": ["user"]
                },
                "profile_settings": {
                    "description": "Update profile information",
                    "roles": ["user"]
                }
            },
            "last_updated": datetime.utcnow().isoformat()
        }

        return success_response(
            data=permissions_data,
            message="Permissions overview retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Error getting permissions overview: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health", response_model=dict)
async def admin_security_health():
    """
    Health check endpoint for admin security service.

    Returns the operational status of the admin security service.
    """
    try:
        # Simulate service checks
        await asyncio.sleep(0.01)  # Mock processing time

        return success_response(
            data={
                "service": "admin_security_service",
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0"
            },
            message="Admin security service is healthy"
        )

    except Exception as e:
        logger.error(f"Admin security service health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")
