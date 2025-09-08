"""
Audit & Compliance Data Models
Handles audit trails, compliance monitoring, and regulatory reporting
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, validator
from app.models.base import BaseResponse

# Enums for audit and compliance
class AuditEventType(str, Enum):
    """Types of audit events"""
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    PASSWORD_CHANGE = "password_change"
    PROFILE_UPDATE = "profile_update"
    TRANSACTION_CREATE = "transaction_create"
    TRANSACTION_UPDATE = "transaction_update"
    PAYMENT_INITIATE = "payment_initiate"
    PAYMENT_COMPLETE = "payment_complete"
    PAYMENT_FAIL = "payment_fail"
    KYC_SUBMIT = "kyc_submit"
    KYC_APPROVE = "kyc_approve"
    KYC_REJECT = "kyc_reject"
    ACCOUNT_CREATE = "account_create"
    ACCOUNT_SUSPEND = "account_suspend"
    ACCOUNT_ACTIVATE = "account_activate"
    DATA_EXPORT = "data_export"
    ADMIN_ACTION = "admin_action"
    SECURITY_ALERT = "security_alert"
    COMPLIANCE_CHECK = "compliance_check"

class ComplianceStatus(str, Enum):
    """Compliance check status"""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PENDING_REVIEW = "pending_review"
    REQUIRES_ACTION = "requires_action"
    EXEMPTED = "exempted"

class RiskLevel(str, Enum):
    """Risk assessment levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ComplianceType(str, Enum):
    """Types of compliance checks"""
    AML = "aml"  # Anti-Money Laundering
    KYC = "kyc"  # Know Your Customer
    SANCTIONS = "sanctions"
    PEP = "pep"  # Politically Exposed Person
    TRANSACTION_MONITORING = "transaction_monitoring"
    REGULATORY_REPORTING = "regulatory_reporting"
    DATA_PRIVACY = "data_privacy"
    FRAUD_DETECTION = "fraud_detection"

# Request Models
class AuditLogRequest(BaseModel):
    """Request model for creating audit logs"""
    event_type: AuditEventType
    description: str = Field(..., min_length=1, max_length=500)
    metadata: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    resource_id: Optional[str] = None
    resource_type: Optional[str] = None

class ComplianceCheckRequest(BaseModel):
    """Request model for compliance checks"""
    user_id: str = Field(..., min_length=1)
    compliance_type: ComplianceType
    reference_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class ComplianceReportRequest(BaseModel):
    """Request model for generating compliance reports"""
    report_type: ComplianceType
    start_date: datetime
    end_date: datetime
    user_ids: Optional[List[str]] = None
    include_metadata: bool = False

    @validator('end_date')
    def validate_date_range(cls, v, values):
        if 'start_date' in values and v <= values['start_date']:
            raise ValueError('End date must be after start date')
        return v

# Response Models
class AuditLogEntry(BaseResponse):
    """Audit log entry response model"""
    id: str
    user_id: Optional[str]
    event_type: AuditEventType
    description: str
    timestamp: datetime
    ip_address: Optional[str]
    user_agent: Optional[str]
    resource_id: Optional[str]
    resource_type: Optional[str]
    metadata: Optional[Dict[str, Any]]
    session_id: Optional[str]

class ComplianceCheckResult(BaseResponse):
    """Compliance check result response model"""
    id: str
    user_id: str
    compliance_type: ComplianceType
    status: ComplianceStatus
    risk_level: RiskLevel
    score: Optional[float] = Field(None, ge=0, le=100)
    findings: List[str] = []
    recommendations: List[str] = []
    reference_id: Optional[str]
    checked_at: datetime
    expires_at: Optional[datetime]
    metadata: Optional[Dict[str, Any]]

class ComplianceReport(BaseResponse):
    """Compliance report response model"""
    id: str
    report_type: ComplianceType
    generated_at: datetime
    start_date: datetime
    end_date: datetime
    total_checks: int
    compliant_count: int
    non_compliant_count: int
    pending_count: int
    summary: Dict[str, Any]
    details: Optional[List[Dict[str, Any]]] = None

class ComplianceMetrics(BaseResponse):
    """Compliance metrics response model"""
    total_users: int
    compliant_users: int
    non_compliant_users: int
    pending_reviews: int
    compliance_rate: float = Field(..., ge=0, le=100)
    risk_distribution: Dict[RiskLevel, int]
    recent_violations: int
    last_updated: datetime

# Database Models (for mock repository)
class AuditLogDB(BaseModel):
    """Database model for audit logs"""
    id: str
    user_id: Optional[str]
    event_type: str
    description: str
    timestamp: datetime
    ip_address: Optional[str]
    user_agent: Optional[str]
    resource_id: Optional[str]
    resource_type: Optional[str]
    metadata: Optional[Dict[str, Any]]
    session_id: Optional[str]
    created_at: datetime
    updated_at: datetime

class ComplianceCheckDB(BaseModel):
    """Database model for compliance checks"""
    id: str
    user_id: str
    compliance_type: str
    status: str
    risk_level: str
    score: Optional[float]
    findings: List[str]
    recommendations: List[str]
    reference_id: Optional[str]
    checked_at: datetime
    expires_at: Optional[datetime]
    metadata: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

class ComplianceReportDB(BaseModel):
    """Database model for compliance reports"""
    id: str
    report_type: str
    generated_at: datetime
    start_date: datetime
    end_date: datetime
    total_checks: int
    compliant_count: int
    non_compliant_count: int
    pending_count: int
    summary: Dict[str, Any]
    details: Optional[List[Dict[str, Any]]]
    created_at: datetime
    updated_at: datetime
