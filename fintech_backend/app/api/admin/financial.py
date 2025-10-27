"""
Financial Administration API endpoints for transaction and account management.
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
import asyncio
from datetime import datetime, timedelta
from pydantic import BaseModel

from ..database.config import get_db
from ..config.logging import get_logger
from ..core.auth import get_current_user
from ..utils.response import success_response
from ..services.transaction_service import TransactionService
from ..services.database_transaction_service import DatabaseTransactionService
from ..services.database_account_service import DatabaseAccountService

logger = get_logger(__name__)
security = HTTPBearer()

router = APIRouter(prefix="/financial", tags=["Admin Financial Administration"])


class TransactionStatusUpdateRequest(BaseModel):
    status: str
    reason: Optional[str] = None
    notes: Optional[str] = None


class AccountStatusUpdateRequest(BaseModel):
    status: str
    reason: Optional[str] = None
    freeze_funds: bool = False


def require_admin(current_user: dict) -> dict:
    """Check if user has admin role"""
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def get_transaction_service():
    """Dependency to get transaction service instance"""
    return TransactionService()


def get_database_transaction_service():
    """Dependency to get database transaction service instance"""
    return DatabaseTransactionService()


def get_database_account_service():
    """Dependency to get database account service instance"""
    return DatabaseAccountService()


@router.get("/transactions", response_model=dict)
async def get_all_transactions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    transaction_type: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    min_amount: Optional[float] = Query(None),
    max_amount: Optional[float] = Query(None),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    transaction_service: DatabaseTransactionService = Depends(get_database_transaction_service)
):
    """
    Get all transactions with advanced filtering (Admin only).

    Returns paginated list of all transactions with comprehensive filtering options.
    """
    try:
        logger.info(f"Admin API: Getting transactions - page {page}, limit {limit}")

        token = credentials.credentials
        current_user = await get_current_user(token, db)
        require_admin(current_user)

        # Build filters
        filters = {}
        if status:
            filters["status"] = status
        if transaction_type:
            filters["type"] = transaction_type
        if user_id:
            filters["user_id"] = user_id
        if start_date:
            filters["start_date"] = start_date
        if end_date:
            filters["end_date"] = end_date
        if min_amount is not None:
            filters["min_amount"] = min_amount
        if max_amount is not None:
            filters["max_amount"] = max_amount

        # Get transactions with filters
        result = await transaction_service.get_transactions_admin(
            db=db,
            page=page,
            limit=limit,
            filters=filters
        )

        return success_response(
            data={
                "transactions": result["transactions"],
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": result["total"],
                    "pages": result["pages"]
                },
                "filters": filters,
                "summary": result.get("summary", {})
            },
            message="Transactions retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Error getting transactions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/transactions/{transaction_id}", response_model=dict)
async def get_transaction_details(
    transaction_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    transaction_service: DatabaseTransactionService = Depends(get_database_transaction_service)
):
    """
    Get detailed transaction information (Admin only).

    Returns complete transaction details including audit trail.
    """
    try:
        logger.info(f"Admin API: Getting transaction details {transaction_id}")

        token = credentials.credentials
        current_user = await get_current_user(token, db)
        require_admin(current_user)

        transaction = await transaction_service.get_transaction_by_id_admin(
            transaction_id=transaction_id,
            db=db
        )

        return success_response(
            data={"transaction": transaction},
            message="Transaction details retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Error getting transaction {transaction_id}: {e}")
        raise HTTPException(status_code=404, detail="Transaction not found")


@router.put("/transactions/{transaction_id}/status", response_model=dict)
async def update_transaction_status(
    transaction_id: str,
    status_update: TransactionStatusUpdateRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    transaction_service: DatabaseTransactionService = Depends(get_database_transaction_service)
):
    """
    Update transaction status (Admin only).

    Allows admins to approve, reject, or modify transaction status.
    """
    try:
        logger.info(f"Admin API: Updating transaction {transaction_id} status to {status_update.status}")

        token = credentials.credentials
        current_user = await get_current_user(token, db)
        require_admin(current_user)

        # Validate status
        valid_statuses = ["pending", "processing", "completed", "failed", "cancelled", "refunded"]
        if status_update.status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )

        updated_transaction = await transaction_service.update_transaction_status_admin(
            transaction_id=transaction_id,
            new_status=status_update.status,
            reason=status_update.reason,
            notes=status_update.notes,
            updated_by=current_user["user_id"],
            db=db
        )

        return success_response(
            data={"transaction": updated_transaction},
            message=f"Transaction status updated to {status_update.status}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating transaction {transaction_id} status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/accounts", response_model=dict)
async def get_all_accounts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    account_type: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    min_balance: Optional[float] = Query(None),
    max_balance: Optional[float] = Query(None),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    account_service: DatabaseAccountService = Depends(get_database_account_service)
):
    """
    Get all user accounts with filtering (Admin only).

    Returns paginated list of all accounts with balance and status information.
    """
    try:
        logger.info(f"Admin API: Getting accounts - page {page}, limit {limit}")

        token = credentials.credentials
        current_user = await get_current_user(token, db)
        require_admin(current_user)

        # Build filters
        filters = {}
        if status:
            filters["status"] = status
        if account_type:
            filters["type"] = account_type
        if user_id:
            filters["user_id"] = user_id
        if min_balance is not None:
            filters["min_balance"] = min_balance
        if max_balance is not None:
            filters["max_balance"] = max_balance

        # Get accounts with filters
        result = await account_service.get_accounts_admin(
            db=db,
            page=page,
            limit=limit,
            filters=filters
        )

        return success_response(
            data={
                "accounts": result["accounts"],
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": result["total"],
                    "pages": result["pages"]
                },
                "filters": filters,
                "summary": result.get("summary", {})
            },
            message="Accounts retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Error getting accounts: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/accounts/{account_id}", response_model=dict)
async def get_account_details(
    account_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    account_service: DatabaseAccountService = Depends(get_database_account_service)
):
    """
    Get detailed account information (Admin only).

    Returns complete account details including transaction history summary.
    """
    try:
        logger.info(f"Admin API: Getting account details {account_id}")

        token = credentials.credentials
        current_user = await get_current_user(token, db)
        require_admin(current_user)

        account = await account_service.get_account_by_id_admin(
            account_id=account_id,
            db=db
        )

        return success_response(
            data={"account": account},
            message="Account details retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Error getting account {account_id}: {e}")
        raise HTTPException(status_code=404, detail="Account not found")


@router.put("/accounts/{account_id}/status", response_model=dict)
async def update_account_status(
    account_id: str,
    status_update: AccountStatusUpdateRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    account_service: DatabaseAccountService = Depends(get_database_account_service)
):
    """
    Update account status (Admin only).

    Allows admins to activate, suspend, or freeze accounts.
    """
    try:
        logger.info(f"Admin API: Updating account {account_id} status to {status_update.status}")

        token = credentials.credentials
        current_user = await get_current_user(token, db)
        require_admin(current_user)

        # Validate status
        valid_statuses = ["active", "suspended", "frozen", "closed"]
        if status_update.status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )

        updated_account = await account_service.update_account_status_admin(
            account_id=account_id,
            new_status=status_update.status,
            reason=status_update.reason,
            freeze_funds=status_update.freeze_funds,
            updated_by=current_user["user_id"],
            db=db
        )

        return success_response(
            data={"account": updated_account},
            message=f"Account status updated to {status_update.status}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating account {account_id} status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/summary", response_model=dict)
async def get_financial_summary(
    period: str = Query("30d", regex="^(1d|7d|30d|90d|1y)$"),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    transaction_service: DatabaseTransactionService = Depends(get_database_transaction_service),
    account_service: DatabaseAccountService = Depends(get_database_account_service)
):
    """
    Get financial system summary (Admin only).

    Returns comprehensive financial metrics and statistics.
    """
    try:
        logger.info(f"Admin API: Getting financial summary for period {period}")

        token = credentials.credentials
        current_user = await get_current_user(token, db)
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

        # Get transaction summary
        transaction_summary = await transaction_service.get_transaction_summary_admin(
            db=db,
            start_date=start_date,
            end_date=end_date
        )

        # Get account summary
        account_summary = await account_service.get_account_summary_admin(db=db)

        # Combine summaries
        financial_summary = {
            "period": period,
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "transactions": transaction_summary,
            "accounts": account_summary,
            "generated_at": datetime.utcnow().isoformat()
        }

        return success_response(
            data=financial_summary,
            message="Financial summary retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Error getting financial summary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/fraud-alerts", response_model=dict)
async def get_fraud_alerts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, regex="^(active|resolved|dismissed)$"),
    severity: Optional[str] = Query(None, regex="^(low|medium|high|critical)$"),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Get fraud detection alerts (Admin only).

    Returns paginated list of fraud alerts with severity levels.
    """
    try:
        logger.info(f"Admin API: Getting fraud alerts - page {page}, limit {limit}")

        token = credentials.credentials
        current_user = await get_current_user(token, db)
        require_admin(current_user)

        # Mock fraud alerts data (in real implementation, this would query fraud detection system)
        mock_alerts = [
            {
                "alert_id": f"alert_{i+1}",
                "type": "unusual_transaction_pattern",
                "severity": "medium",
                "status": "active",
                "user_id": f"user_{1000 + i}",
                "description": f"Unusual transaction pattern detected for user {1000 + i}",
                "amount": 5000.00 + (i * 100),
                "detected_at": (datetime.utcnow() - timedelta(hours=i)).isoformat(),
                "risk_score": 75 + (i % 25)
            }
            for i in range(min(limit * page, 100))  # Mock up to 100 alerts
        ]

        # Apply filters
        if status:
            mock_alerts = [alert for alert in mock_alerts if alert["status"] == status]
        if severity:
            mock_alerts = [alert for alert in mock_alerts if alert["severity"] == severity]

        # Paginate
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_alerts = mock_alerts[start_idx:end_idx]

        alerts_data = {
            "alerts": paginated_alerts,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": len(mock_alerts),
                "pages": (len(mock_alerts) + limit - 1) // limit
            },
            "filters": {
                "status": status,
                "severity": severity
            },
            "summary": {
                "total_active": len([a for a in mock_alerts if a["status"] == "active"]),
                "high_severity": len([a for a in mock_alerts if a["severity"] in ["high", "critical"]])
            }
        }

        return success_response(
            data=alerts_data,
            message="Fraud alerts retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Error getting fraud alerts: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health", response_model=dict)
async def admin_financial_health():
    """
    Health check endpoint for admin financial service.

    Returns the operational status of the admin financial service.
    """
    try:
        # Simulate service checks
        await asyncio.sleep(0.01)  # Mock processing time

        return success_response(
            data={
                "service": "admin_financial_service",
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0"
            },
            message="Admin financial service is healthy"
        )

    except Exception as e:
        logger.error(f"Admin financial service health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")
