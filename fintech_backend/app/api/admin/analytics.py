"""
Analytics & Reporting Administration API endpoints for system analytics and reports.
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
import asyncio
from datetime import datetime, timedelta

from ...database.config import get_db
from ...config.logging import get_logger
from ...core.auth import get_current_user
from ...utils.response import success_response
from ...services.analytics_service import AnalyticsService

logger = get_logger(__name__)

router = APIRouter(prefix="/analytics", tags=["Admin Analytics & Reporting"])


def require_admin(current_user: dict) -> dict:
    """Check if user has admin role"""
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def get_analytics_service():
    """Dependency to get analytics service instance"""
    return AnalyticsService()


@router.get("/overview", response_model=dict)
async def get_system_overview(
    period: str = Query("30d", regex="^(1d|7d|30d|90d|1y)$"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Get comprehensive system overview analytics (Admin only).

    Returns system-wide analytics including user metrics, transaction volumes, and performance indicators.
    """
    try:
        logger.info(f"Admin API: Getting system overview for period {period}")
        require_admin(current_user)

        # Calculate date range
        end_date = datetime.utcnow()
        if period == "1d":
            start_date = end_date - timedelta(days=1)
        elif period == "7d":
            start_date = end_date - timedelta(days=7)
        elif period == "30d":
            start_date = end_date - timedelta(days=30)
        elif period == "90d":
            start_date = end_date - timedelta(days=90)
        else:  # 1y
            start_date = end_date - timedelta(days=365)

        # Get system overview analytics
        overview_data = await analytics_service.get_system_overview_admin(
            db=db,
            start_date=start_date,
            end_date=end_date
        )

        return success_response(
            data={
                "overview": overview_data,
                "period": period,
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                },
                "generated_at": datetime.utcnow().isoformat()
            },
            message="System overview analytics retrieved successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting system overview: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/reports/users", response_model=dict)
async def get_user_reports(
    report_type: str = Query("activity", regex="^(activity|registration|engagement|retention)$"),
    period: str = Query("30d", regex="^(1d|7d|30d|90d|1y)$"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Get user activity and engagement reports (Admin only).

    Returns detailed user analytics based on the specified report type and period.
    """
    try:
        logger.info(f"Admin API: Getting user {report_type} report for period {period}")
        require_admin(current_user)

        # Calculate date range
        end_date = datetime.utcnow()
        if period == "1d":
            start_date = end_date - timedelta(days=1)
        elif period == "7d":
            start_date = end_date - timedelta(days=7)
        elif period == "30d":
            start_date = end_date - timedelta(days=30)
        elif period == "90d":
            start_date = end_date - timedelta(days=90)
        else:  # 1y
            start_date = end_date - timedelta(days=365)

        # Get user report data
        report_data = await analytics_service.get_user_report_admin(
            db=db,
            report_type=report_type,
            start_date=start_date,
            end_date=end_date
        )

        return success_response(
            data={
                "report": report_data,
                "report_type": report_type,
                "period": period,
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                },
                "generated_at": datetime.utcnow().isoformat()
            },
            message=f"User {report_type} report retrieved successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user {report_type} report: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/reports/financial", response_model=dict)
async def get_financial_reports(
    report_type: str = Query("transactions", regex="^(transactions|revenue|accounts|fraud)$"),
    period: str = Query("30d", regex="^(1d|7d|30d|90d|1y)$"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get financial reports and analytics (Admin only).

    Returns comprehensive financial analytics and reporting data.
    """
    try:
        logger.info(f"Admin API: Getting financial {report_type} report for period {period}")
        require_admin(current_user)

        # Calculate date range
        end_date = datetime.utcnow()
        if period == "1d":
            start_date = end_date - timedelta(days=1)
        elif period == "7d":
            start_date = end_date - timedelta(days=7)
        elif period == "30d":
            start_date = end_date - timedelta(days=30)
        elif period == "90d":
            start_date = end_date - timedelta(days=90)
        else:  # 1y
            start_date = end_date - timedelta(days=365)

        # Mock financial report data (in real implementation, this would query actual financial data)
        if report_type == "transactions":
            report_data = {
                "total_transactions": 15420,
                "successful_transactions": 15250,
                "failed_transactions": 170,
                "pending_transactions": 85,
                "total_volume": 2850000.00,
                "avg_transaction_value": 185.50,
                "transaction_trends": [
                    {"date": (start_date + timedelta(days=i)).isoformat(), "count": 450 + (i % 50)}
                    for i in range(min((end_date - start_date).days + 1, 30))
                ],
                "top_transaction_types": [
                    {"type": "transfer", "count": 8500, "volume": 1250000.00},
                    {"type": "payment", "count": 4200, "volume": 980000.00},
                    {"type": "deposit", "count": 2200, "volume": 520000.00},
                    {"type": "withdrawal", "count": 520, "volume": 100000.00}
                ]
            }
        elif report_type == "revenue":
            report_data = {
                "total_revenue": 142500.00,
                "transaction_fees": 98500.00,
                "service_fees": 28500.00,
                "premium_fees": 15500.00,
                "revenue_trends": [
                    {"date": (start_date + timedelta(days=i)).isoformat(), "amount": 4500.00 + (i % 500)}
                    for i in range(min((end_date - start_date).days + 1, 30))
                ],
                "revenue_by_service": [
                    {"service": "transfers", "revenue": 52000.00, "percentage": 36.5},
                    {"service": "payments", "revenue": 38500.00, "percentage": 27.0},
                    {"service": "investments", "revenue": 28500.00, "percentage": 20.0},
                    {"service": "savings", "revenue": 23500.00, "percentage": 16.5}
                ]
            }
        elif report_type == "accounts":
            report_data = {
                "total_accounts": 1250,
                "active_accounts": 1180,
                "inactive_accounts": 45,
                "suspended_accounts": 25,
                "account_balance_distribution": {
                    "0-100": 320,
                    "100-1000": 480,
                    "1000-10000": 350,
                    "10000+": 100
                },
                "account_growth": [
                    {"date": (start_date + timedelta(days=i)).isoformat(), "new_accounts": 8 + (i % 5)}
                    for i in range(min((end_date - start_date).days + 1, 30))
                ],
                "account_types": [
                    {"type": "savings", "count": 680, "percentage": 54.4},
                    {"type": "checking", "count": 420, "percentage": 33.6},
                    {"type": "investment", "count": 150, "percentage": 12.0}
                ]
            }
        else:  # fraud
            report_data = {
                "total_fraud_alerts": 45,
                "confirmed_fraud": 12,
                "false_positives": 28,
                "investigating": 5,
                "fraud_amount_prevented": 125000.00,
                "fraud_trends": [
                    {"date": (start_date + timedelta(days=i)).isoformat(), "alerts": 1 + (i % 3)}
                    for i in range(min((end_date - start_date).days + 1, 30))
                ],
                "fraud_types": [
                    {"type": "card_fraud", "count": 18, "amount": 75000.00},
                    {"type": "account_takeover", "count": 12, "amount": 35000.00},
                    {"type": "money_laundering", "count": 8, "amount": 15000.00},
                    {"type": "identity_theft", "count": 7, "amount": 0.00}
                ]
            }

        return success_response(
            data={
                "report": report_data,
                "report_type": report_type,
                "period": period,
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                },
                "generated_at": datetime.utcnow().isoformat()
            },
            message=f"Financial {report_type} report retrieved successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting financial {report_type} report: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/reports/system", response_model=dict)
async def get_system_reports(
    report_type: str = Query("performance", regex="^(performance|usage|errors|security)$"),
    period: str = Query("30d", regex="^(1d|7d|30d|90d|1y)$"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get system performance and health reports (Admin only).

    Returns system performance metrics, usage statistics, error rates, and security reports.
    """
    try:
        logger.info(f"Admin API: Getting system {report_type} report for period {period}")
        require_admin(current_user)

        # Calculate date range
        end_date = datetime.utcnow()
        if period == "1d":
            start_date = end_date - timedelta(days=1)
        elif period == "7d":
            start_date = end_date - timedelta(days=7)
        elif period == "30d":
            start_date = end_date - timedelta(days=30)
        elif period == "90d":
            start_date = end_date - timedelta(days=90)
        else:  # 1y
            start_date = end_date - timedelta(days=365)

        # Mock system report data
        if report_type == "performance":
            report_data = {
                "avg_response_time": 245.5,
                "p95_response_time": 850.0,
                "p99_response_time": 1250.0,
                "throughput": 1250,
                "error_rate": 0.85,
                "uptime_percentage": 99.95,
                "performance_trends": [
                    {
                        "date": (start_date + timedelta(days=i)).isoformat(),
                        "avg_response_time": 245.5 + (i % 50 - 25),
                        "throughput": 1250 + (i % 100 - 50),
                        "error_rate": 0.85 + (i % 0.5 - 0.25)
                    }
                    for i in range(min((end_date - start_date).days + 1, 30))
                ],
                "slowest_endpoints": [
                    {"endpoint": "/api/transactions", "avg_time": 1250.0, "calls": 15420},
                    {"endpoint": "/api/market-data", "avg_time": 890.0, "calls": 28500},
                    {"endpoint": "/api/user/profile", "avg_time": 675.0, "calls": 18200},
                    {"endpoint": "/api/notifications", "avg_time": 445.0, "calls": 9200}
                ]
            }
        elif report_type == "usage":
            report_data = {
                "total_api_calls": 285000,
                "unique_users": 1250,
                "avg_sessions_per_user": 8.5,
                "peak_concurrent_users": 185,
                "data_transfer_gb": 45.8,
                "storage_used_gb": 125.5,
                "usage_trends": [
                    {
                        "date": (start_date + timedelta(days=i)).isoformat(),
                        "api_calls": 8500 + (i % 1000),
                        "unique_users": 1150 + (i % 50),
                        "data_transfer_mb": 1450 + (i % 200)
                    }
                    for i in range(min((end_date - start_date).days + 1, 30))
                ],
                "popular_features": [
                    {"feature": "money_transfer", "usage": 45200, "percentage": 35.2},
                    {"feature": "account_balance", "usage": 38900, "percentage": 30.3},
                    {"feature": "transaction_history", "usage": 25600, "percentage": 19.9},
                    {"feature": "market_data", "usage": 15800, "percentage": 12.3},
                    {"feature": "notifications", "usage": 4200, "percentage": 3.3}
                ]
            }
        elif report_type == "errors":
            report_data = {
                "total_errors": 1250,
                "error_rate": 0.44,
                "most_common_errors": [
                    {"error": "VALIDATION_ERROR", "count": 450, "percentage": 36.0},
                    {"error": "NETWORK_ERROR", "count": 320, "percentage": 25.6},
                    {"error": "AUTHENTICATION_ERROR", "count": 280, "percentage": 22.4},
                    {"error": "DATABASE_ERROR", "count": 120, "percentage": 9.6},
                    {"error": "EXTERNAL_API_ERROR", "count": 80, "percentage": 6.4}
                ],
                "error_trends": [
                    {
                        "date": (start_date + timedelta(days=i)).isoformat(),
                        "total_errors": 35 + (i % 15),
                        "by_severity": {
                            "critical": 2 + (i % 3),
                            "high": 8 + (i % 5),
                            "medium": 15 + (i % 8),
                            "low": 10 + (i % 6)
                        }
                    }
                    for i in range(min((end_date - start_date).days + 1, 30))
                ],
                "error_by_endpoint": [
                    {"endpoint": "/api/payments", "errors": 285, "error_rate": 1.85},
                    {"endpoint": "/api/transfers", "errors": 245, "error_rate": 1.45},
                    {"endpoint": "/api/auth", "errors": 320, "error_rate": 2.25},
                    {"endpoint": "/api/market-data", "errors": 180, "error_rate": 0.85}
                ]
            }
        else:  # security
            report_data = {
                "security_incidents": 28,
                "blocked_attempts": 1250,
                "suspicious_activities": 85,
                "security_score": 92.5,
                "security_events": [
                    {
                        "date": (start_date + timedelta(days=i)).isoformat(),
                        "blocked_logins": 35 + (i % 20),
                        "suspicious_ips": 5 + (i % 8),
                        "rate_limit_hits": 120 + (i % 50)
                    }
                    for i in range(min((end_date - start_date).days + 1, 30))
                ],
                "security_threats": [
                    {"threat": "brute_force", "count": 450, "blocked": 445},
                    {"threat": "sql_injection", "count": 85, "blocked": 85},
                    {"threat": "xss_attempt", "count": 65, "blocked": 62},
                    {"threat": "unauthorized_access", "count": 120, "blocked": 118}
                ],
                "compliance_status": {
                    "gdpr_compliant": True,
                    "data_encryption": True,
                    "audit_logging": True,
                    "access_controls": True,
                    "last_audit": (datetime.utcnow() - timedelta(days=30)).isoformat()
                }
            }

        return success_response(
            data={
                "report": report_data,
                "report_type": report_type,
                "period": period,
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                },
                "generated_at": datetime.utcnow().isoformat()
            },
            message=f"System {report_type} report retrieved successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting system {report_type} report: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/dashboard", response_model=dict)
async def get_analytics_dashboard(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get analytics dashboard data (Admin only).

    Returns key metrics and KPIs for the admin dashboard.
    """
    try:
        logger.info("Admin API: Getting analytics dashboard data")
        require_admin(current_user)

        # Mock dashboard data
        dashboard_data = {
            "kpis": {
                "total_users": 1250,
                "active_users_30d": 1180,
                "total_transactions_30d": 15420,
                "total_volume_30d": 2850000.00,
                "system_uptime": 99.95,
                "avg_response_time": 245.5
            },
            "trends": {
                "user_growth": [
                    {"date": (datetime.utcnow() - timedelta(days=29-i)).isoformat(), "users": 1200 + i}
                    for i in range(30)
                ],
                "transaction_volume": [
                    {"date": (datetime.utcnow() - timedelta(days=29-i)).isoformat(), "volume": 85000 + (i * 1000)}
                    for i in range(30)
                ],
                "system_performance": [
                    {"date": (datetime.utcnow() - timedelta(days=29-i)).isoformat(), "response_time": 245 + (i % 20 - 10)}
                    for i in range(30)
                ]
            },
            "alerts": [
                {"type": "warning", "message": "High error rate on /api/payments", "timestamp": datetime.utcnow().isoformat()},
                {"type": "info", "message": "User registration peak detected", "timestamp": (datetime.utcnow() - timedelta(hours=2)).isoformat()},
                {"type": "success", "message": "Database backup completed successfully", "timestamp": (datetime.utcnow() - timedelta(hours=6)).isoformat()}
            ],
            "generated_at": datetime.utcnow().isoformat()
        }

        return success_response(
            data=dashboard_data,
            message="Analytics dashboard data retrieved successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting analytics dashboard: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health", response_model=dict)
async def admin_analytics_health():
    """
    Health check endpoint for admin analytics service.

    Returns the operational status of the admin analytics service.
    """
    try:
        # Simulate service checks
        await asyncio.sleep(0.01)  # Mock processing time

        return success_response(
            data={
                "service": "admin_analytics_service",
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0"
            },
            message="Admin analytics service is healthy"
        )

    except Exception as e:
        logger.error(f"Admin analytics service health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")