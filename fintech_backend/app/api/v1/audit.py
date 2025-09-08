"""
Audit & Compliance API Routes
Handles audit trails, compliance monitoring, and regulatory reporting
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer

from app.core.auth import get_current_user
from app.models.auth import User
from app.models.audit import (
    AuditLogRequest,
    AuditLogEntry,
    ComplianceCheckRequest,
    ComplianceCheckResult,
    ComplianceReportRequest,
    ComplianceReport,
    ComplianceMetrics,
    AuditEventType,
    ComplianceType
)
from app.services.audit_service import AuditService
from app.core.exceptions import ValidationError, NotFoundError
from app.models.base import PaginatedResponse, SuccessResponse

router = APIRouter(prefix="/audit", tags=["Audit & Compliance"])
security = HTTPBearer()

# Initialize audit service
audit_service = AuditService()

@router.post("/logs", response_model=AuditLogEntry, status_code=status.HTTP_201_CREATED)
async def create_audit_log(
    audit_request: AuditLogRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new audit log entry
    
    - **event_type**: Type of event being logged
    - **description**: Detailed description of the event
    - **metadata**: Optional additional data
    - **ip_address**: IP address of the request
    - **user_agent**: User agent string
    - **resource_id**: ID of the affected resource
    - **resource_type**: Type of the affected resource
    """
    try:
        audit_log = await audit_service.create_audit_log(
            user_id=current_user.id,
            audit_data=audit_request
        )
        return audit_log
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create audit log"
        )

@router.get("/logs", response_model=PaginatedResponse[AuditLogEntry])
async def get_audit_logs(
    current_user: User = Depends(get_current_user),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    event_type: Optional[AuditEventType] = Query(None, description="Filter by event type"),
    start_date: Optional[datetime] = Query(None, description="Filter from this date"),
    end_date: Optional[datetime] = Query(None, description="Filter until this date"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page")
):
    """
    Get audit logs with optional filtering
    
    - **user_id**: Filter logs for specific user
    - **event_type**: Filter by type of event
    - **start_date**: Filter logs from this date
    - **end_date**: Filter logs until this date
    - **page**: Page number for pagination
    - **limit**: Number of items per page
    """
    try:
        # For non-admin users, only show their own logs
        filter_user_id = user_id if current_user.role == "admin" else current_user.id
        
        audit_logs = await audit_service.get_audit_logs(
            user_id=filter_user_id,
            event_type=event_type,
            start_date=start_date,
            end_date=end_date,
            page=page,
            limit=limit
        )
        return audit_logs
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audit logs"
        )

@router.post("/compliance/check", response_model=ComplianceCheckResult, status_code=status.HTTP_201_CREATED)
async def perform_compliance_check(
    check_request: ComplianceCheckRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Perform a compliance check for a user
    
    - **user_id**: ID of the user to check
    - **compliance_type**: Type of compliance check (KYC, AML, sanctions, etc.)
    - **reference_id**: Optional reference ID for the check
    - **metadata**: Optional additional data for the check
    """
    try:
        # For non-admin users, only allow checking their own compliance
        if current_user.role != "admin" and check_request.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only perform compliance checks on your own account"
            )
        
        compliance_result = await audit_service.perform_compliance_check(check_request)
        return compliance_result
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to perform compliance check"
        )

@router.post("/compliance/report", response_model=ComplianceReport, status_code=status.HTTP_201_CREATED)
async def generate_compliance_report(
    report_request: ComplianceReportRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Generate a compliance report
    
    - **report_type**: Type of compliance report to generate
    - **start_date**: Start date for the report period
    - **end_date**: End date for the report period
    - **user_ids**: Optional list of specific users to include
    - **include_metadata**: Whether to include detailed metadata
    
    Note: Only admin users can generate compliance reports
    """
    try:
        # Only admin users can generate compliance reports
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admin users can generate compliance reports"
            )
        
        compliance_report = await audit_service.generate_compliance_report(report_request)
        return compliance_report
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate compliance report"
        )

@router.get("/compliance/metrics", response_model=ComplianceMetrics)
async def get_compliance_metrics(
    current_user: User = Depends(get_current_user)
):
    """
    Get overall compliance metrics
    
    Returns comprehensive compliance statistics including:
    - Total users and compliance rates
    - Risk distribution
    - Recent violations
    - Compliance trends
    
    Note: Only admin users can access compliance metrics
    """
    try:
        # Only admin users can access compliance metrics
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admin users can access compliance metrics"
            )
        
        metrics = await audit_service.get_compliance_metrics()
        return metrics
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve compliance metrics"
        )

@router.get("/health", response_model=dict)
async def audit_health_check():
    """
    Health check endpoint for audit and compliance system
    """
    try:
        health_status = await audit_service.health_check()
        return {
            "status": "healthy",
            "service": "audit",
            "timestamp": health_status["timestamp"],
            "details": health_status
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "audit",
            "error": str(e)
        }
