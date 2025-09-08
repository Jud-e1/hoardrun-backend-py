"""
Audit & Compliance Service
Handles audit trails, compliance monitoring, and regulatory reporting
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import random

from app.models.audit import (
    AuditLogRequest,
    AuditLogEntry,
    ComplianceCheckRequest,
    ComplianceCheckResult,
    ComplianceReportRequest,
    ComplianceReport,
    ComplianceMetrics,
    AuditLogDB,
    ComplianceCheckDB,
    ComplianceReportDB,
    AuditEventType,
    ComplianceStatus,
    ComplianceType,
    RiskLevel
)
from app.models.base import PaginatedResponse
from app.core.exceptions import NotFoundError, ValidationError

class AuditService:
    """Service for handling audit and compliance operations"""
    
    def __init__(self):
        """Initialize the audit service with mock data"""
        self.audit_logs: Dict[str, AuditLogDB] = {}
        self.compliance_checks: Dict[str, ComplianceCheckDB] = {}
        self.compliance_reports: Dict[str, ComplianceReportDB] = {}
        self._initialize_mock_data()
    
    def _initialize_mock_data(self):
        """Initialize mock audit and compliance data"""
        # Sample audit logs
        sample_logs = [
            {
                "user_id": "user_001",
                "event_type": AuditEventType.USER_LOGIN,
                "description": "User logged in successfully",
                "ip_address": "192.168.1.100",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "metadata": {"login_method": "password", "device": "desktop"}
            },
            {
                "user_id": "user_001",
                "event_type": AuditEventType.TRANSACTION_CREATE,
                "description": "Created new transaction",
                "resource_id": "txn_001",
                "resource_type": "transaction",
                "metadata": {"amount": 1000, "currency": "UGX", "type": "transfer"}
            },
            {
                "user_id": "user_002",
                "event_type": AuditEventType.KYC_SUBMIT,
                "description": "Submitted KYC documents",
                "resource_id": "kyc_001",
                "resource_type": "kyc_verification",
                "metadata": {"documents": ["passport", "utility_bill"]}
            },
            {
                "user_id": None,
                "event_type": AuditEventType.SECURITY_ALERT,
                "description": "Multiple failed login attempts detected",
                "ip_address": "192.168.1.200",
                "metadata": {"attempts": 5, "blocked": True}
            },
            {
                "user_id": "admin_001",
                "event_type": AuditEventType.ADMIN_ACTION,
                "description": "Admin suspended user account",
                "resource_id": "user_003",
                "resource_type": "user_account",
                "metadata": {"reason": "suspicious_activity", "duration": "7_days"}
            }
        ]
        
        for i, log_data in enumerate(sample_logs):
            log_id = f"audit_{str(i+1).zfill(3)}"
            timestamp = datetime.utcnow() - timedelta(days=random.randint(0, 30))
            
            self.audit_logs[log_id] = AuditLogDB(
                id=log_id,
                user_id=log_data["user_id"],
                event_type=log_data["event_type"].value,
                description=log_data["description"],
                timestamp=timestamp,
                ip_address=log_data.get("ip_address"),
                user_agent=log_data.get("user_agent"),
                resource_id=log_data.get("resource_id"),
                resource_type=log_data.get("resource_type"),
                metadata=log_data.get("metadata"),
                session_id=f"session_{uuid.uuid4().hex[:8]}",
                created_at=timestamp,
                updated_at=timestamp
            )
        
        # Sample compliance checks
        sample_checks = [
            {
                "user_id": "user_001",
                "compliance_type": ComplianceType.KYC,
                "status": ComplianceStatus.COMPLIANT,
                "risk_level": RiskLevel.LOW,
                "score": 95.0,
                "findings": [],
                "recommendations": ["Maintain current compliance status"]
            },
            {
                "user_id": "user_002",
                "compliance_type": ComplianceType.AML,
                "status": ComplianceStatus.PENDING_REVIEW,
                "risk_level": RiskLevel.MEDIUM,
                "score": 75.0,
                "findings": ["Large transaction pattern detected"],
                "recommendations": ["Review transaction history", "Verify source of funds"]
            },
            {
                "user_id": "user_003",
                "compliance_type": ComplianceType.SANCTIONS,
                "status": ComplianceStatus.NON_COMPLIANT,
                "risk_level": RiskLevel.HIGH,
                "score": 25.0,
                "findings": ["Name match on sanctions list", "Requires immediate review"],
                "recommendations": ["Suspend account", "Conduct enhanced due diligence"]
            },
            {
                "user_id": "user_004",
                "compliance_type": ComplianceType.PEP,
                "status": ComplianceStatus.REQUIRES_ACTION,
                "risk_level": RiskLevel.HIGH,
                "score": 40.0,
                "findings": ["Politically exposed person identified"],
                "recommendations": ["Enhanced monitoring required", "Additional documentation needed"]
            }
        ]
        
        for i, check_data in enumerate(sample_checks):
            check_id = f"compliance_{str(i+1).zfill(3)}"
            checked_at = datetime.utcnow() - timedelta(days=random.randint(0, 15))
            expires_at = checked_at + timedelta(days=90)  # 90-day validity
            
            self.compliance_checks[check_id] = ComplianceCheckDB(
                id=check_id,
                user_id=check_data["user_id"],
                compliance_type=check_data["compliance_type"].value,
                status=check_data["status"].value,
                risk_level=check_data["risk_level"].value,
                score=check_data["score"],
                findings=check_data["findings"],
                recommendations=check_data["recommendations"],
                reference_id=f"ref_{uuid.uuid4().hex[:8]}",
                checked_at=checked_at,
                expires_at=expires_at,
                metadata={"automated": True, "version": "1.0"},
                created_at=checked_at,
                updated_at=checked_at
            )
    
    async def create_audit_log(
        self,
        user_id: Optional[str],
        audit_data: AuditLogRequest,
        session_id: Optional[str] = None
    ) -> AuditLogEntry:
        """Create a new audit log entry"""
        log_id = f"audit_{uuid.uuid4().hex}"
        timestamp = datetime.utcnow()
        
        audit_log = AuditLogDB(
            id=log_id,
            user_id=user_id,
            event_type=audit_data.event_type.value,
            description=audit_data.description,
            timestamp=timestamp,
            ip_address=audit_data.ip_address,
            user_agent=audit_data.user_agent,
            resource_id=audit_data.resource_id,
            resource_type=audit_data.resource_type,
            metadata=audit_data.metadata,
            session_id=session_id or f"session_{uuid.uuid4().hex[:8]}",
            created_at=timestamp,
            updated_at=timestamp
        )
        
        self.audit_logs[log_id] = audit_log
        
        return AuditLogEntry(
            id=audit_log.id,
            user_id=audit_log.user_id,
            event_type=AuditEventType(audit_log.event_type),
            description=audit_log.description,
            timestamp=audit_log.timestamp,
            ip_address=audit_log.ip_address,
            user_agent=audit_log.user_agent,
            resource_id=audit_log.resource_id,
            resource_type=audit_log.resource_type,
            metadata=audit_log.metadata,
            session_id=audit_log.session_id
        )
    
    async def get_audit_logs(
        self,
        user_id: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        limit: int = 10
    ) -> PaginatedResponse[AuditLogEntry]:
        """Get audit logs with filtering and pagination"""
        # Filter logs
        filtered_logs = []
        for log in self.audit_logs.values():
            if user_id and log.user_id != user_id:
                continue
            if event_type and log.event_type != event_type.value:
                continue
            if start_date and log.timestamp < start_date:
                continue
            if end_date and log.timestamp > end_date:
                continue
            filtered_logs.append(log)
        
        # Sort by timestamp (newest first)
        filtered_logs.sort(key=lambda x: x.timestamp, reverse=True)
        
        # Paginate
        total = len(filtered_logs)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_logs = filtered_logs[start_idx:end_idx]
        
        # Convert to response models
        log_entries = [
            AuditLogEntry(
                id=log.id,
                user_id=log.user_id,
                event_type=AuditEventType(log.event_type),
                description=log.description,
                timestamp=log.timestamp,
                ip_address=log.ip_address,
                user_agent=log.user_agent,
                resource_id=log.resource_id,
                resource_type=log.resource_type,
                metadata=log.metadata,
                session_id=log.session_id
            )
            for log in paginated_logs
        ]
        
        return PaginatedResponse(
            items=log_entries,
            total=total,
            page=page,
            limit=limit,
            pages=(total + limit - 1) // limit
        )
    
    async def perform_compliance_check(
        self,
        check_data: ComplianceCheckRequest
    ) -> ComplianceCheckResult:
        """Perform a compliance check for a user"""
        check_id = f"compliance_{uuid.uuid4().hex}"
        checked_at = datetime.utcnow()
        expires_at = checked_at + timedelta(days=90)
        
        # Simulate compliance check logic
        risk_score = random.uniform(0, 100)
        
        if risk_score >= 80:
            status = ComplianceStatus.COMPLIANT
            risk_level = RiskLevel.LOW
            findings = []
            recommendations = ["Maintain current compliance status"]
        elif risk_score >= 60:
            status = ComplianceStatus.PENDING_REVIEW
            risk_level = RiskLevel.MEDIUM
            findings = ["Minor compliance issues detected"]
            recommendations = ["Review and update documentation"]
        elif risk_score >= 40:
            status = ComplianceStatus.REQUIRES_ACTION
            risk_level = RiskLevel.HIGH
            findings = ["Significant compliance gaps identified"]
            recommendations = ["Immediate action required", "Enhanced monitoring"]
        else:
            status = ComplianceStatus.NON_COMPLIANT
            risk_level = RiskLevel.CRITICAL
            findings = ["Critical compliance violations", "Regulatory breach detected"]
            recommendations = ["Suspend operations", "Legal review required"]
        
        compliance_check = ComplianceCheckDB(
            id=check_id,
            user_id=check_data.user_id,
            compliance_type=check_data.compliance_type.value,
            status=status.value,
            risk_level=risk_level.value,
            score=risk_score,
            findings=findings,
            recommendations=recommendations,
            reference_id=check_data.reference_id or f"ref_{uuid.uuid4().hex[:8]}",
            checked_at=checked_at,
            expires_at=expires_at,
            metadata=check_data.metadata or {},
            created_at=checked_at,
            updated_at=checked_at
        )
        
        self.compliance_checks[check_id] = compliance_check
        
        return ComplianceCheckResult(
            id=compliance_check.id,
            user_id=compliance_check.user_id,
            compliance_type=ComplianceType(compliance_check.compliance_type),
            status=ComplianceStatus(compliance_check.status),
            risk_level=RiskLevel(compliance_check.risk_level),
            score=compliance_check.score,
            findings=compliance_check.findings,
            recommendations=compliance_check.recommendations,
            reference_id=compliance_check.reference_id,
            checked_at=compliance_check.checked_at,
            expires_at=compliance_check.expires_at,
            metadata=compliance_check.metadata
        )
    
    async def generate_compliance_report(
        self,
        report_data: ComplianceReportRequest
    ) -> ComplianceReport:
        """Generate a compliance report"""
        report_id = f"report_{uuid.uuid4().hex}"
        generated_at = datetime.utcnow()
        
        # Filter compliance checks for the report
        filtered_checks = []
        for check in self.compliance_checks.values():
            if check.compliance_type != report_data.report_type.value:
                continue
            if check.checked_at < report_data.start_date or check.checked_at > report_data.end_date:
                continue
            if report_data.user_ids and check.user_id not in report_data.user_ids:
                continue
            filtered_checks.append(check)
        
        # Calculate metrics
        total_checks = len(filtered_checks)
        compliant_count = len([c for c in filtered_checks if c.status == ComplianceStatus.COMPLIANT.value])
        non_compliant_count = len([c for c in filtered_checks if c.status == ComplianceStatus.NON_COMPLIANT.value])
        pending_count = len([c for c in filtered_checks if c.status in [ComplianceStatus.PENDING_REVIEW.value, ComplianceStatus.REQUIRES_ACTION.value]])
        
        # Generate summary
        summary = {
            "compliance_rate": (compliant_count / total_checks * 100) if total_checks > 0 else 0,
            "average_risk_score": sum([c.score or 0 for c in filtered_checks]) / total_checks if total_checks > 0 else 0,
            "risk_distribution": {
                RiskLevel.LOW.value: len([c for c in filtered_checks if c.risk_level == RiskLevel.LOW.value]),
                RiskLevel.MEDIUM.value: len([c for c in filtered_checks if c.risk_level == RiskLevel.MEDIUM.value]),
                RiskLevel.HIGH.value: len([c for c in filtered_checks if c.risk_level == RiskLevel.HIGH.value]),
                RiskLevel.CRITICAL.value: len([c for c in filtered_checks if c.risk_level == RiskLevel.CRITICAL.value])
            },
            "top_findings": self._get_top_findings(filtered_checks)
        }
        
        # Generate details if requested
        details = None
        if report_data.include_metadata:
            details = [
                {
                    "check_id": check.id,
                    "user_id": check.user_id,
                    "status": check.status,
                    "risk_level": check.risk_level,
                    "score": check.score,
                    "findings": check.findings,
                    "checked_at": check.checked_at.isoformat()
                }
                for check in filtered_checks
            ]
        
        report = ComplianceReportDB(
            id=report_id,
            report_type=report_data.report_type.value,
            generated_at=generated_at,
            start_date=report_data.start_date,
            end_date=report_data.end_date,
            total_checks=total_checks,
            compliant_count=compliant_count,
            non_compliant_count=non_compliant_count,
            pending_count=pending_count,
            summary=summary,
            details=details,
            created_at=generated_at,
            updated_at=generated_at
        )
        
        self.compliance_reports[report_id] = report
        
        return ComplianceReport(
            id=report.id,
            report_type=ComplianceType(report.report_type),
            generated_at=report.generated_at,
            start_date=report.start_date,
            end_date=report.end_date,
            total_checks=report.total_checks,
            compliant_count=report.compliant_count,
            non_compliant_count=report.non_compliant_count,
            pending_count=report.pending_count,
            summary=report.summary,
            details=report.details
        )
    
    async def get_compliance_metrics(self) -> ComplianceMetrics:
        """Get overall compliance metrics"""
        total_checks = len(self.compliance_checks)
        if total_checks == 0:
            return ComplianceMetrics(
                total_users=0,
                compliant_users=0,
                non_compliant_users=0,
                pending_reviews=0,
                compliance_rate=0.0,
                risk_distribution={
                    RiskLevel.LOW: 0,
                    RiskLevel.MEDIUM: 0,
                    RiskLevel.HIGH: 0,
                    RiskLevel.CRITICAL: 0
                },
                recent_violations=0,
                last_updated=datetime.utcnow()
            )
        
        # Get unique users
        unique_users = set(check.user_id for check in self.compliance_checks.values())
        total_users = len(unique_users)
        
        # Count by status
        compliant_users = len(set(
            check.user_id for check in self.compliance_checks.values()
            if check.status == ComplianceStatus.COMPLIANT.value
        ))
        
        non_compliant_users = len(set(
            check.user_id for check in self.compliance_checks.values()
            if check.status == ComplianceStatus.NON_COMPLIANT.value
        ))
        
        pending_reviews = len(set(
            check.user_id for check in self.compliance_checks.values()
            if check.status in [ComplianceStatus.PENDING_REVIEW.value, ComplianceStatus.REQUIRES_ACTION.value]
        ))
        
        # Calculate compliance rate
        compliance_rate = (compliant_users / total_users * 100) if total_users > 0 else 0
        
        # Risk distribution
        risk_distribution = {
            RiskLevel.LOW: len([c for c in self.compliance_checks.values() if c.risk_level == RiskLevel.LOW.value]),
            RiskLevel.MEDIUM: len([c for c in self.compliance_checks.values() if c.risk_level == RiskLevel.MEDIUM.value]),
            RiskLevel.HIGH: len([c for c in self.compliance_checks.values() if c.risk_level == RiskLevel.HIGH.value]),
            RiskLevel.CRITICAL: len([c for c in self.compliance_checks.values() if c.risk_level == RiskLevel.CRITICAL.value])
        }
        
        # Recent violations (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_violations = len([
            c for c in self.compliance_checks.values()
            if c.status == ComplianceStatus.NON_COMPLIANT.value and c.checked_at >= thirty_days_ago
        ])
        
        return ComplianceMetrics(
            total_users=total_users,
            compliant_users=compliant_users,
            non_compliant_users=non_compliant_users,
            pending_reviews=pending_reviews,
            compliance_rate=compliance_rate,
            risk_distribution=risk_distribution,
            recent_violations=recent_violations,
            last_updated=datetime.utcnow()
        )
    
    def _get_top_findings(self, checks: List[ComplianceCheckDB]) -> List[str]:
        """Get the most common findings from compliance checks"""
        finding_counts = {}
        for check in checks:
            for finding in check.findings:
                finding_counts[finding] = finding_counts.get(finding, 0) + 1
        
        # Sort by frequency and return top 5
        sorted_findings = sorted(finding_counts.items(), key=lambda x: x[1], reverse=True)
        return [finding for finding, count in sorted_findings[:5]]
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for audit service"""
        return {
            "service": "audit",
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {
                "total_audit_logs": len(self.audit_logs),
                "total_compliance_checks": len(self.compliance_checks),
                "total_reports": len(self.compliance_reports)
            }
        }
