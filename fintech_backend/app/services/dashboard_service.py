"""
Dashboard service with financial summaries, analytics, and notification management.
"""
import random
from decimal import Decimal
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Optional, Any

from ..config.logging import get_logger, log_business_event
from ..repositories.mock_repository import (
    get_accounts_repository, 
    get_transactions_repository,
    get_investments_repository,
    get_notifications_repository,
    get_cards_repository,
    get_repository_manager
)
from ..utils.calculations import AnalyticsCalculator, RiskCalculator
from ..utils.formatters import (
    DashboardFormatter, 
    FinancialFormatter, 
    NotificationFormatter,
    ResponseFormatter
)
from ..core.exceptions import ValidationException

logger = get_logger("dashboard_service")


class DashboardService:
    """Service for dashboard data aggregation and analytics."""
    
    def __init__(self):
        self.accounts_repo = get_accounts_repository()
        self.transactions_repo = get_transactions_repository()
        self.investments_repo = get_investments_repository()
        self.notifications_repo = get_notifications_repository()
        self.cards_repo = get_cards_repository()
    
    async def get_dashboard_summary(
        self, 
        user_id: str, 
        include_pending: bool = True,
        date_range_days: int = 30
    ) -> Dict[str, Any]:
        """Get comprehensive dashboard summary for a user."""
        
        try:
            # Ensure mock data is initialized
            repo_manager = get_repository_manager()
            await repo_manager.ensure_mock_data_initialized()
            
            # Log business event
            log_business_event(
                logger=logger,
                event_type="dashboard_summary_requested",
                event_data={"user_id": user_id, "date_range_days": date_range_days},
                user_id=user_id
            )
            
            # Get user accounts
            user_accounts = await self.accounts_repo.get_by_user_id(user_id)
            if not user_accounts:
                logger.warning(f"No accounts found for user {user_id}")
                user_accounts = []
            
            # Calculate balance totals
            total_balance = sum(Decimal(str(acc.get("balance", 0))) for acc in user_accounts)
            available_balance = sum(Decimal(str(acc.get("available_balance", 0))) for acc in user_accounts)
            
            # Get investment portfolio value
            user_investments = await self.investments_repo.get_by_user_id(user_id)
            investment_value = sum(
                Decimal(str(inv.get("market_value", 0))) for inv in user_investments
            )
            
            # Calculate total assets and liabilities (simplified)
            total_assets = total_balance + investment_value
            total_liabilities = Decimal("0.00")  # Mock - would include credit card debt, loans, etc.
            
            # Format financial summary
            financial_summary = DashboardFormatter.format_financial_summary(
                total_balance=total_balance,
                available_balance=available_balance,
                total_assets=total_assets,
                total_liabilities=total_liabilities
            )
            
            # Get recent transactions
            cutoff_date = datetime.now(UTC) - timedelta(days=date_range_days)
            recent_transactions_data = await self.transactions_repo.get_by_date_range(
                user_id=user_id,
                start_date=cutoff_date,
                end_date=datetime.now(UTC),
                limit=10
            )
            
            # Filter pending transactions if requested
            if not include_pending:
                recent_transactions_data = [
                    tx for tx in recent_transactions_data 
                    if tx.get("status") != "pending"
                ]
            
            recent_activity = DashboardFormatter.format_recent_activity(
                recent_transactions_data, limit=5
            )
            
            # Get unread notifications count
            unread_notifications = await self.notifications_repo.find_by_criteria(
                {"user_id": user_id, "is_read": False}
            )
            notifications_count = len(unread_notifications)
            
            # Get account alerts (low balance, etc.)
            account_alerts = await self._generate_account_alerts(user_accounts)
            
            # Calculate quick stats
            monthly_spending = await self._calculate_monthly_spending(user_id)
            spending_velocity = RiskCalculator.calculate_spending_velocity(
                recent_transactions_data, days=7
            )
            
            dashboard_data = {
                "financial_summary": financial_summary,
                "recent_activity": recent_activity,
                "notifications_count": notifications_count,
                "account_alerts": account_alerts,
                "quick_stats": {
                    "monthly_spending": FinancialFormatter.format_currency_amount(monthly_spending),
                    "weekly_spending": FinancialFormatter.format_currency_amount(
                        spending_velocity["total_spending"]
                    ),
                    "avg_transaction": FinancialFormatter.format_currency_amount(
                        spending_velocity["avg_transaction_amount"]
                    ),
                    "total_accounts": len(user_accounts),
                    "active_cards": len([
                        card for card in await self.cards_repo.get_by_user_id(user_id)
                        if card.get("status") == "active" and not card.get("is_frozen")
                    ])
                }
            }
            
            logger.info(
                f"Dashboard summary generated for user {user_id}",
                extra={
                    "user_id": user_id,
                    "accounts_count": len(user_accounts),
                    "transactions_count": len(recent_transactions_data),
                    "notifications_count": notifications_count
                }
            )
            
            return ResponseFormatter.success_response(
                data=dashboard_data,
                message="Dashboard summary retrieved successfully"
            )
            
        except Exception as e:
            logger.error(
                f"Failed to get dashboard summary for user {user_id}: {str(e)}",
                extra={"user_id": user_id, "error": str(e)},
                exc_info=True
            )
            raise
    
    async def get_spending_analytics(
        self,
        user_id: str,
        period_days: int = 30,
        category_filter: Optional[List[str]] = None,
        include_trends: bool = True
    ) -> Dict[str, Any]:
        """Get detailed spending analytics for a user."""
        
        try:
            # Log business event
            log_business_event(
                logger=logger,
                event_type="analytics_requested",
                event_data={
                    "user_id": user_id, 
                    "period_days": period_days,
                    "category_filter": category_filter
                },
                user_id=user_id
            )
            
            # Get transactions for the period
            cutoff_date = datetime.now(UTC) - timedelta(days=period_days)
            transactions = await self.transactions_repo.get_by_date_range(
                user_id=user_id,
                start_date=cutoff_date,
                end_date=datetime.now(UTC),
                limit=1000  # Large limit for analytics
            )
            
            # Filter by category if specified
            if category_filter:
                transactions = [
                    tx for tx in transactions 
                    if tx.get("category") in category_filter
                ]
            
            # Calculate spending by category
            category_breakdown = AnalyticsCalculator.calculate_spending_by_category(
                transactions, days=period_days
            )
            
            # Calculate monthly trends
            monthly_trends = []
            if include_trends:
                monthly_trends = AnalyticsCalculator.calculate_monthly_trends(
                    transactions, months=6
                )
            
            # Calculate total spending for the period
            total_spending = sum(
                Decimal(str(tx.get("amount", 0))) 
                for tx in transactions 
                if tx.get("transaction_type") == "debit"
            )
            
            # Format analytics data
            analytics_data = DashboardFormatter.format_spending_analytics(
                monthly_spending=total_spending,
                category_breakdown=category_breakdown,
                spending_trends=monthly_trends
            )
            
            # Add insights
            insights = await self._generate_spending_insights(
                transactions, category_breakdown, total_spending
            )
            analytics_data["insights"] = insights
            
            logger.info(
                f"Spending analytics generated for user {user_id}",
                extra={
                    "user_id": user_id,
                    "period_days": period_days,
                    "transactions_analyzed": len(transactions),
                    "categories_count": len(category_breakdown)
                }
            )
            
            return ResponseFormatter.success_response(
                data=analytics_data,
                message="Spending analytics retrieved successfully"
            )
            
        except Exception as e:
            logger.error(
                f"Failed to get spending analytics for user {user_id}: {str(e)}",
                extra={"user_id": user_id, "error": str(e)},
                exc_info=True
            )
            raise
    
    async def get_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        notification_type: Optional[str] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        """Get user notifications."""
        
        try:
            # Build filter criteria
            criteria = {"user_id": user_id}
            
            if unread_only:
                criteria["is_read"] = False
            
            if notification_type:
                criteria["type"] = notification_type
            
            # Get notifications
            notifications_data = await self.notifications_repo.find_by_criteria(
                criteria=criteria,
                limit=limit
            )
            
            # Format notifications
            notifications = [
                NotificationFormatter.format_notification(notif)
                for notif in notifications_data
            ]
            
            # Count unread notifications
            unread_count = await self.notifications_repo.count_by_user(
                user_id=user_id,
                criteria={"is_read": False}
            )
            
            # Sort by priority and creation date
            notifications.sort(
                key=lambda x: (
                    {"urgent": 0, "high": 1, "normal": 2, "low": 3}.get(x["priority"], 2),
                    x["created_at"]
                ),
                reverse=True
            )
            
            logger.info(
                f"Retrieved {len(notifications)} notifications for user {user_id}",
                extra={"user_id": user_id, "total_notifications": len(notifications), "unread_count": unread_count}
            )
            
            return ResponseFormatter.success_response(
                data={
                    "notifications": notifications,
                    "unread_count": unread_count,
                    "total_count": len(notifications)
                },
                message="Notifications retrieved successfully"
            )
            
        except Exception as e:
            logger.error(
                f"Failed to get notifications for user {user_id}: {str(e)}",
                extra={"user_id": user_id, "error": str(e)},
                exc_info=True
            )
            raise
    
    async def mark_notifications_read(self, user_id: str, notification_ids: List[str]) -> Dict[str, Any]:
        """Mark notifications as read."""
        
        try:
            marked_read = 0
            not_found = 0
            already_read = 0
            
            for notification_id in notification_ids:
                # Get the notification
                notification = await self.notifications_repo.get_user_record(user_id, notification_id)
                
                if not notification:
                    not_found += 1
                    continue
                
                if notification.get("is_read", False):
                    already_read += 1
                    continue
                
                # Mark as read
                await self.notifications_repo.update(notification_id, {
                    "is_read": True,
                    "read_at": datetime.now(UTC)
                })
                marked_read += 1
            
            # Log business event
            log_business_event(
                logger=logger,
                event_type="notifications_marked_read",
                event_data={
                    "user_id": user_id,
                    "marked_read": marked_read,
                    "not_found": not_found,
                    "already_read": already_read
                },
                user_id=user_id
            )
            
            return ResponseFormatter.success_response(
                data={
                    "marked_read": marked_read,
                    "not_found": not_found,
                    "already_read": already_read
                },
                message=f"Successfully marked {marked_read} notifications as read"
            )
            
        except Exception as e:
            logger.error(
                f"Failed to mark notifications as read for user {user_id}: {str(e)}",
                extra={"user_id": user_id, "notification_ids": notification_ids, "error": str(e)},
                exc_info=True
            )
            raise
    
    async def _calculate_monthly_spending(self, user_id: str) -> Decimal:
        """Calculate current month spending."""
        # Get start of current month
        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Get transactions for current month
        transactions = await self.transactions_repo.get_by_date_range(
            user_id=user_id,
            start_date=month_start,
            end_date=now,
            limit=1000
        )
        
        # Sum debit transactions
        monthly_spending = sum(
            Decimal(str(tx.get("amount", 0)))
            for tx in transactions
            if tx.get("transaction_type") == "debit"
        )
        
        return monthly_spending
    
    async def _generate_account_alerts(self, accounts: List[Dict]) -> List[Dict[str, Any]]:
        """Generate alerts for account conditions."""
        alerts = []
        
        for account in accounts:
            balance = Decimal(str(account.get("balance", 0)))
            account_type = account.get("account_type", "")
            
            # Low balance alert
            if balance < Decimal("100.00"):
                alerts.append({
                    "type": "low_balance",
                    "severity": "high",
                    "message": f"Low balance in {account.get('account_name', 'account')}: {FinancialFormatter.format_currency_amount(balance)['formatted']}",
                    "account_id": account.get("id"),
                    "action_suggested": "Consider transferring funds or reviewing spending"
                })
            elif balance < Decimal("500.00") and account_type == "checking":
                alerts.append({
                    "type": "low_balance_warning", 
                    "severity": "medium",
                    "message": f"Balance getting low in {account.get('account_name', 'account')}: {FinancialFormatter.format_currency_amount(balance)['formatted']}",
                    "account_id": account.get("id"),
                    "action_suggested": "Monitor spending or add funds"
                })
        
        return alerts
    
    async def _generate_spending_insights(
        self,
        transactions: List[Dict],
        category_breakdown: List[Dict],
        total_spending: Decimal
    ) -> List[Dict[str, Any]]:
        """Generate spending insights and recommendations."""
        insights = []
        
        # Top spending category insight
        if category_breakdown:
            top_category = category_breakdown[0]
            if top_category["percentage"] > 30:  # More than 30% in one category
                insights.append({
                    "type": "spending_concentration",
                    "message": f"You spent {top_category['percentage']:.1f}% of your budget on {top_category['category']}",
                    "recommendation": f"Consider reviewing your {top_category['category']} expenses for potential savings",
                    "priority": "medium"
                })
        
        # Spending velocity insight
        velocity = RiskCalculator.calculate_spending_velocity(transactions, days=7)
        if velocity["avg_daily_spending"] > total_spending / 30 * Decimal("1.5"):
            insights.append({
                "type": "high_spending_velocity",
                "message": "Your recent spending is higher than your monthly average",
                "recommendation": "Review recent transactions and consider reducing discretionary spending",
                "priority": "medium"
            })
        
        # Transaction frequency insight
        if velocity["transaction_count"] > 50:  # More than 50 transactions in 7 days
            insights.append({
                "type": "high_transaction_frequency",
                "message": f"You made {velocity['transaction_count']} transactions in the last week",
                "recommendation": "Consider consolidating purchases to reduce transaction fees",
                "priority": "low"
            })
        
        # Weekend spending pattern
        weekend_spending = sum(
            Decimal(str(tx.get("amount", 0)))
            for tx in transactions
            if (tx.get("transaction_date") and 
                isinstance(tx.get("transaction_date"), datetime) and
                tx.get("transaction_date").weekday() >= 5 and  # Saturday = 5, Sunday = 6
                tx.get("transaction_type") == "debit")
        )
        
        if weekend_spending > total_spending * Decimal("0.4"):  # More than 40% on weekends
            insights.append({
                "type": "weekend_spending_pattern",
                "message": "High weekend spending detected",
                "recommendation": "Consider planning weekend activities with a budget in mind",
                "priority": "low"
            })
        
        return insights


class NotificationService:
    """Service for managing user notifications."""
    
    def __init__(self):
        self.notifications_repo = get_notifications_repository()
    
    async def create_notification(
        self,
        user_id: str,
        notification_type: str,
        title: str,
        message: str,
        priority: str = "normal",
        data: Optional[Dict[str, Any]] = None,
        action_required: bool = False
    ) -> Dict[str, Any]:
        """Create a new notification for a user."""
        
        try:
            notification_data = {
                "user_id": user_id,
                "type": notification_type,
                "title": title,
                "message": message,
                "priority": priority,
                "is_read": False,
                "data": data or {},
                "action_required": action_required
            }
            
            created_notification = await self.notifications_repo.create(notification_data)
            
            log_business_event(
                logger=logger,
                event_type="notification_created",
                event_data={
                    "notification_id": created_notification["id"],
                    "type": notification_type,
                    "priority": priority
                },
                user_id=user_id
            )
            
            return created_notification
            
        except Exception as e:
            logger.error(
                f"Failed to create notification for user {user_id}: {str(e)}",
                extra={"user_id": user_id, "notification_type": notification_type, "error": str(e)},
                exc_info=True
            )
            raise
    
    async def create_transaction_alert(self, user_id: str, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Create a transaction alert notification."""
        
        notification_data = NotificationFormatter.create_transaction_notification(
            transaction=transaction,
            notification_type="transaction_alert"
        )
        
        return await self.create_notification(
            user_id=user_id,
            notification_type=notification_data["type"],
            title=notification_data["title"],
            message=notification_data["message"],
            priority=notification_data["priority"],
            data=notification_data["data"],
            action_required=notification_data["action_required"]
        )
    
    async def create_spending_limit_alert(
        self,
        user_id: str,
        current_spent: Decimal,
        limit: Decimal,
        limit_type: str,
        currency: str = "USD"
    ) -> Dict[str, Any]:
        """Create a spending limit alert notification."""
        
        notification_data = NotificationFormatter.create_limit_alert(
            current_spent=current_spent,
            limit=limit,
            limit_type=limit_type,
            currency=currency
        )
        
        return await self.create_notification(
            user_id=user_id,
            notification_type=notification_data["type"],
            title=notification_data["title"],
            message=notification_data["message"],
            priority=notification_data["priority"],
            data=notification_data["data"],
            action_required=notification_data["action_required"]
        )


# Service instances for dependency injection
def get_dashboard_service() -> DashboardService:
    """Get dashboard service instance."""
    return DashboardService()


def get_notification_service() -> NotificationService:
    """Get notification service instance."""
    return NotificationService()
