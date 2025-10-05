"""
Savings Management Service
Handles business logic for savings goals, contributions, and auto-save features.
"""

import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from decimal import Decimal
import calendar

from app.models.savings import (
    SavingsGoalCreateRequest,
    SavingsGoalUpdateRequest,
    ContributionRequest,
    SavingsGoalProfile,
    ContributionProfile,
    SavingsGoalHistory,
    SavingsGoalStats,
    SavingsInsights,
    AutoSaveSettings,
    SavingsGoalStatus,
    SavingsGoalType,
    ContributionFrequency,
    AutoSaveRule
)
from app.core.exceptions import ValidationError, NotFoundError, ConflictError
from app.repositories.mock_repository import MockRepository

class SavingsService:
    def __init__(self):
        self.repository = MockRepository()
        
        # Initialize mock data
        self._init_mock_data()
    
    def _init_mock_data(self):
        """Initialize mock savings data"""
        mock_goals = [
            {
                "id": "goal_001",
                "user_id": "user_001",
                "name": "Emergency Fund",
                "description": "6 months of expenses for emergencies",
                "goal_type": SavingsGoalType.EMERGENCY_FUND,
                "target_amount": Decimal("5000.00"),
                "current_amount": Decimal("1250.00"),
                "currency": "USD",
                "target_date": date(2024, 12, 31),
                "status": SavingsGoalStatus.ACTIVE,
                "auto_contribute": True,
                "contribution_amount": Decimal("200.00"),
                "contribution_frequency": ContributionFrequency.MONTHLY,
                "auto_save_rules": [AutoSaveRule.ROUND_UP, AutoSaveRule.PERCENTAGE],
                "is_private": True,
                "created_at": datetime.now() - timedelta(days=60),
                "updated_at": datetime.now() - timedelta(days=5),
                "completed_at": None
            },
            {
                "id": "goal_002",
                "user_id": "user_001",
                "name": "Vacation to Europe",
                "description": "Summer vacation trip to Europe",
                "goal_type": SavingsGoalType.VACATION,
                "target_amount": Decimal("3000.00"),
                "current_amount": Decimal("800.00"),
                "currency": "USD",
                "target_date": date(2024, 7, 15),
                "status": SavingsGoalStatus.ACTIVE,
                "auto_contribute": False,
                "contribution_amount": None,
                "contribution_frequency": None,
                "auto_save_rules": [],
                "is_private": False,
                "created_at": datetime.now() - timedelta(days=30),
                "updated_at": datetime.now() - timedelta(days=2),
                "completed_at": None
            }
        ]
        
        mock_contributions = [
            {
                "id": "contrib_001",
                "user_id": "user_001",
                "goal_id": "goal_001",
                "amount": Decimal("200.00"),
                "currency": "USD",
                "payment_method_id": "pm_001",
                "note": "Monthly automatic contribution",
                "is_recurring": True,
                "is_auto_save": False,
                "auto_save_rule": None,
                "transaction_id": "txn_001",
                "contribution_date": datetime.now() - timedelta(days=30)
            },
            {
                "id": "contrib_002",
                "user_id": "user_001",
                "goal_id": "goal_001",
                "amount": Decimal("50.00"),
                "currency": "USD",
                "payment_method_id": None,
                "note": "Round-up savings",
                "is_recurring": False,
                "is_auto_save": True,
                "auto_save_rule": AutoSaveRule.ROUND_UP,
                "transaction_id": None,
                "contribution_date": datetime.now() - timedelta(days=15)
            },
            {
                "id": "contrib_003",
                "user_id": "user_001",
                "goal_id": "goal_002",
                "amount": Decimal("300.00"),
                "currency": "USD",
                "payment_method_id": "pm_002",
                "note": "Initial vacation fund",
                "is_recurring": False,
                "is_auto_save": False,
                "auto_save_rule": None,
                "transaction_id": "txn_002",
                "contribution_date": datetime.now() - timedelta(days=25)
            }
        ]
        
        mock_history = [
            {
                "id": "hist_001",
                "user_id": "user_001",
                "goal_id": "goal_001",
                "action": "goal_created",
                "amount": None,
                "previous_amount": None,
                "new_amount": Decimal("0.00"),
                "description": "Emergency Fund goal created",
                "metadata": {"goal_type": "emergency_fund"},
                "timestamp": datetime.now() - timedelta(days=60)
            },
            {
                "id": "hist_002",
                "user_id": "user_001",
                "goal_id": "goal_001",
                "action": "contribution_added",
                "amount": Decimal("200.00"),
                "previous_amount": Decimal("0.00"),
                "new_amount": Decimal("200.00"),
                "description": "Monthly contribution added",
                "metadata": {"payment_method": "pm_001"},
                "timestamp": datetime.now() - timedelta(days=30)
            }
        ]
        
        # Store mock data
        for goal in mock_goals:
            self.repository.data.setdefault("savings_goals", {})[goal["id"]] = goal
        
        for contribution in mock_contributions:
            self.repository.data.setdefault("savings_contributions", {})[contribution["id"]] = contribution
        
        for history in mock_history:
            self.repository.data.setdefault("savings_history", {})[history["id"]] = history
        
        # Initialize auto-save settings
        auto_save_settings = {
            "user_001": {
                "enabled": True,
                "round_up_enabled": True,
                "round_up_multiplier": 2.0,
                "percentage_save_enabled": True,
                "percentage_save_rate": 5.0,
                "fixed_amount_enabled": False,
                "fixed_amount": Decimal("0.00"),
                "fixed_amount_frequency": ContributionFrequency.MONTHLY,
                "minimum_balance": Decimal("100.00"),
                "maximum_daily_auto_save": Decimal("50.00")
            }
        }
        
        for user_id, settings in auto_save_settings.items():
            self.repository.data.setdefault("auto_save_settings", {})[user_id] = settings
    
    def _calculate_progress_percentage(self, current_amount: Decimal, target_amount: Decimal) -> float:
        """Calculate progress percentage"""
        if target_amount <= 0:
            return 0.0
        return min(float((current_amount / target_amount) * 100), 100.0)
    
    def _calculate_days_remaining(self, target_date: Optional[date]) -> Optional[int]:
        """Calculate days remaining to target date"""
        if not target_date:
            return None
        
        today = date.today()
        if target_date <= today:
            return 0
        
        return (target_date - today).days
    
    def _calculate_next_contribution_date(
        self, 
        last_contribution: Optional[datetime], 
        frequency: Optional[ContributionFrequency]
    ) -> Optional[datetime]:
        """Calculate next scheduled contribution date"""
        if not frequency or frequency == ContributionFrequency.ONE_TIME:
            return None
        
        base_date = last_contribution or datetime.now()
        
        if frequency == ContributionFrequency.DAILY:
            return base_date + timedelta(days=1)
        elif frequency == ContributionFrequency.WEEKLY:
            return base_date + timedelta(weeks=1)
        elif frequency == ContributionFrequency.BIWEEKLY:
            return base_date + timedelta(weeks=2)
        elif frequency == ContributionFrequency.MONTHLY:
            # Add one month
            if base_date.month == 12:
                return base_date.replace(year=base_date.year + 1, month=1)
            else:
                return base_date.replace(month=base_date.month + 1)
        elif frequency == ContributionFrequency.QUARTERLY:
            return base_date + timedelta(days=90)
        elif frequency == ContributionFrequency.YEARLY:
            return base_date.replace(year=base_date.year + 1)
        
        return None
    
    def _convert_to_profile(self, goal_data: Dict[str, Any]) -> SavingsGoalProfile:
        """Convert database record to profile format"""
        
        # Calculate derived fields
        progress_percentage = self._calculate_progress_percentage(
            goal_data["current_amount"], 
            goal_data["target_amount"]
        )
        
        days_remaining = self._calculate_days_remaining(goal_data.get("target_date"))
        
        # Get contribution count
        total_contributions = 0
        last_contribution_date = None
        
        for contrib_data in self.repository.data.get("savings_contributions", {}).values():
            if contrib_data["goal_id"] == goal_data["id"]:
                total_contributions += 1
                if not last_contribution_date or contrib_data["contribution_date"] > last_contribution_date:
                    last_contribution_date = contrib_data["contribution_date"]
        
        # Calculate next contribution date
        next_contribution_date = self._calculate_next_contribution_date(
            last_contribution_date,
            goal_data.get("contribution_frequency")
        )
        
        return SavingsGoalProfile(
            id=goal_data["id"],
            name=goal_data["name"],
            description=goal_data.get("description"),
            goal_type=goal_data["goal_type"],
            target_amount=goal_data["target_amount"],
            current_amount=goal_data["current_amount"],
            currency=goal_data["currency"],
            progress_percentage=progress_percentage,
            target_date=goal_data.get("target_date"),
            days_remaining=days_remaining,
            status=goal_data["status"],
            auto_contribute=goal_data["auto_contribute"],
            contribution_amount=goal_data.get("contribution_amount"),
            contribution_frequency=goal_data.get("contribution_frequency"),
            auto_save_rules=goal_data.get("auto_save_rules", []),
            total_contributions=total_contributions,
            last_contribution_date=last_contribution_date,
            next_contribution_date=next_contribution_date,
            is_private=goal_data["is_private"],
            created_at=goal_data["created_at"],
            updated_at=goal_data["updated_at"]
        )
    
    async def get_user_savings_goals(
        self,
        user_id: str,
        status: Optional[SavingsGoalStatus] = None,
        goal_type: Optional[SavingsGoalType] = None,
        page: int = 1,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Get user's savings goals with filtering and pagination"""
        
        # Get all goals for user
        all_goals = []
        for goal_data in self.repository.data.get("savings_goals", {}).values():
            if goal_data["user_id"] == user_id:
                # Apply filters
                if status and goal_data["status"] != status:
                    continue
                if goal_type and goal_data["goal_type"] != goal_type:
                    continue
                
                # Convert to profile format
                profile = self._convert_to_profile(goal_data)
                all_goals.append(profile)
        
        # Sort by status (active first) then by created date
        all_goals.sort(key=lambda x: (
            x.status != SavingsGoalStatus.ACTIVE,
            -x.progress_percentage,
            x.created_at
        ))
        
        # Apply pagination
        total = len(all_goals)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        items = all_goals[start_idx:end_idx]
        
        total_pages = (total + limit - 1) // limit
        
        return {
            "items": items,
            "total": total,
            "total_pages": total_pages
        }
    
    async def get_user_goals_count(self, user_id: str) -> int:
        """Get count of user's savings goals"""
        count = 0
        for goal_data in self.repository.data.get("savings_goals", {}).values():
            if goal_data["user_id"] == user_id:
                count += 1
        return count
    
    async def get_savings_goal_by_id(
        self, 
        goal_id: str, 
        user_id: str
    ) -> Optional[SavingsGoalProfile]:
        """Get savings goal by ID for specific user"""
        goal_data = self.repository.get("savings_goals", goal_id)
        
        if not goal_data or goal_data["user_id"] != user_id:
            return None
        
        return self._convert_to_profile(goal_data)
    
    async def create_savings_goal(
        self,
        user_id: str,
        goal_data: SavingsGoalCreateRequest
    ) -> SavingsGoalProfile:
        """Create a new savings goal"""
        
        # Generate ID
        goal_id = f"goal_{uuid.uuid4().hex[:8]}"
        
        # Prepare data for storage
        goal_record = {
            "id": goal_id,
            "user_id": user_id,
            "name": goal_data.name,
            "description": goal_data.description,
            "goal_type": goal_data.goal_type,
            "target_amount": goal_data.target_amount,
            "current_amount": Decimal("0.00"),
            "currency": goal_data.currency,
            "target_date": goal_data.target_date,
            "status": SavingsGoalStatus.ACTIVE,
            "auto_contribute": goal_data.auto_contribute,
            "contribution_amount": goal_data.contribution_amount,
            "contribution_frequency": goal_data.contribution_frequency,
            "auto_save_rules": goal_data.auto_save_rules or [],
            "is_private": goal_data.is_private,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "completed_at": None
        }
        
        # Store the goal
        self.repository.data.setdefault("savings_goals", {})[goal_id] = goal_record
        
        # Add history entry
        await self._add_history_entry(
            user_id=user_id,
            goal_id=goal_id,
            action="goal_created",
            description=f"Savings goal '{goal_data.name}' created",
            new_amount=Decimal("0.00")
        )
        
        return self._convert_to_profile(goal_record)
    
    async def update_savings_goal(
        self,
        goal_id: str,
        user_id: str,
        goal_data: SavingsGoalUpdateRequest
    ) -> SavingsGoalProfile:
        """Update an existing savings goal"""
        
        # Get existing goal
        existing_data = self.repository.get("savings_goals", goal_id)
        if not existing_data or existing_data["user_id"] != user_id:
            raise NotFoundError("Savings goal not found")
        
        # Update allowed fields
        update_data = {
            "updated_at": datetime.now()
        }
        
        if goal_data.name is not None:
            update_data["name"] = goal_data.name
        
        if goal_data.description is not None:
            update_data["description"] = goal_data.description
        
        if goal_data.target_amount is not None:
            update_data["target_amount"] = goal_data.target_amount
        
        if goal_data.target_date is not None:
            update_data["target_date"] = goal_data.target_date
        
        if goal_data.auto_contribute is not None:
            update_data["auto_contribute"] = goal_data.auto_contribute
        
        if goal_data.contribution_amount is not None:
            update_data["contribution_amount"] = goal_data.contribution_amount
        
        if goal_data.contribution_frequency is not None:
            update_data["contribution_frequency"] = goal_data.contribution_frequency
        
        if goal_data.auto_save_rules is not None:
            update_data["auto_save_rules"] = goal_data.auto_save_rules
        
        if goal_data.is_private is not None:
            update_data["is_private"] = goal_data.is_private
        
        if goal_data.status is not None:
            update_data["status"] = goal_data.status
            if goal_data.status == SavingsGoalStatus.COMPLETED:
                update_data["completed_at"] = datetime.now()
        
        # Merge with existing data
        existing_data.update(update_data)
        
        # Update in repository
        self.repository.update("savings_goals", goal_id, existing_data)
        
        # Add history entry
        await self._add_history_entry(
            user_id=user_id,
            goal_id=goal_id,
            action="goal_updated",
            description="Savings goal updated"
        )
        
        return self._convert_to_profile(existing_data)
    
    async def delete_savings_goal(self, goal_id: str, user_id: str) -> None:
        """Delete a savings goal"""
        
        # Get existing goal
        existing_data = self.repository.get("savings_goals", goal_id)
        if not existing_data or existing_data["user_id"] != user_id:
            raise NotFoundError("Savings goal not found")
        
        # Delete the goal
        self.repository.delete("savings_goals", goal_id)
        
        # Delete related contributions
        contributions_to_delete = []
        for contrib_id, contrib_data in self.repository.data.get("savings_contributions", {}).items():
            if contrib_data["goal_id"] == goal_id:
                contributions_to_delete.append(contrib_id)
        
        for contrib_id in contributions_to_delete:
            self.repository.delete("savings_contributions", contrib_id)
        
        # Add history entry
        await self._add_history_entry(
            user_id=user_id,
            goal_id=goal_id,
            action="goal_deleted",
            description=f"Savings goal '{existing_data['name']}' deleted"
        )
    
    async def make_contribution(
        self,
        goal_id: str,
        user_id: str,
        contribution_data: ContributionRequest
    ) -> ContributionProfile:
        """Make a contribution to a savings goal"""
        
        # Get goal
        goal_data = self.repository.get("savings_goals", goal_id)
        if not goal_data or goal_data["user_id"] != user_id:
            raise NotFoundError("Savings goal not found")
        
        # Generate contribution ID
        contribution_id = f"contrib_{uuid.uuid4().hex[:8]}"
        
        # Create contribution record
        contribution_record = {
            "id": contribution_id,
            "user_id": user_id,
            "goal_id": goal_id,
            "amount": contribution_data.amount,
            "currency": goal_data["currency"],
            "payment_method_id": contribution_data.payment_method_id,
            "note": contribution_data.note,
            "is_recurring": contribution_data.is_recurring,
            "is_auto_save": False,
            "auto_save_rule": None,
            "transaction_id": f"txn_{uuid.uuid4().hex[:8]}",
            "contribution_date": datetime.now()
        }
        
        # Store contribution
        self.repository.data.setdefault("savings_contributions", {})[contribution_id] = contribution_record
        
        # Update goal current amount
        previous_amount = goal_data["current_amount"]
        new_amount = previous_amount + contribution_data.amount
        
        goal_data.update({
            "current_amount": new_amount,
            "updated_at": datetime.now()
        })
        
        # Check if goal is completed
        if new_amount >= goal_data["target_amount"]:
            goal_data.update({
                "status": SavingsGoalStatus.COMPLETED,
                "completed_at": datetime.now()
            })
        
        self.repository.update("savings_goals", goal_id, goal_data)
        
        # Add history entry
        await self._add_history_entry(
            user_id=user_id,
            goal_id=goal_id,
            action="contribution_added",
            amount=contribution_data.amount,
            previous_amount=previous_amount,
            new_amount=new_amount,
            description=f"Contribution of {contribution_data.amount} {goal_data['currency']} added"
        )
        
        # Get payment method name (mock)
        payment_method_name = None
        if contribution_data.payment_method_id:
            payment_method_name = f"Payment Method {contribution_data.payment_method_id[-3:]}"
        
        return ContributionProfile(
            id=contribution_record["id"],
            goal_id=contribution_record["goal_id"],
            amount=contribution_record["amount"],
            currency=contribution_record["currency"],
            payment_method_id=contribution_record["payment_method_id"],
            payment_method_name=payment_method_name,
            note=contribution_record["note"],
            is_recurring=contribution_record["is_recurring"],
            is_auto_save=contribution_record["is_auto_save"],
            auto_save_rule=contribution_record["auto_save_rule"],
            transaction_id=contribution_record["transaction_id"],
            contribution_date=contribution_record["contribution_date"]
        )
    
    async def get_goal_history(
        self,
        goal_id: str,
        user_id: str,
        page: int = 1,
        limit: int = 20
    ) -> Dict[str, Any]:
        """Get goal history with pagination"""
        
        # Get all history for goal
        all_history = []
        for history_data in self.repository.data.get("savings_history", {}).values():
            if history_data["goal_id"] == goal_id and history_data["user_id"] == user_id:
                history_entry = SavingsGoalHistory(
                    id=history_data["id"],
                    goal_id=history_data["goal_id"],
                    action=history_data["action"],
                    amount=history_data.get("amount"),
                    previous_amount=history_data.get("previous_amount"),
                    new_amount=history_data.get("new_amount"),
                    description=history_data["description"],
                    timestamp=history_data["timestamp"]
                )
                all_history.append(history_entry)
        
        # Sort by timestamp (newest first)
        all_history.sort(key=lambda x: x.timestamp, reverse=True)
        
        # Apply pagination
        total = len(all_history)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        items = all_history[start_idx:end_idx]
        
        total_pages = (total + limit - 1) // limit
        
        return {
            "items": items,
            "total": total,
            "total_pages": total_pages
        }
    
    async def get_savings_statistics(self, user_id: str) -> SavingsGoalStats:
        """Get comprehensive savings statistics"""
        
        total_goals = 0
        active_goals = 0
        completed_goals = 0
        total_saved = Decimal("0.00")
        total_target = Decimal("0.00")
        total_contributions = 0
        goal_type_counts = {}
        
        # Analyze goals
        for goal_data in self.repository.data.get("savings_goals", {}).values():
            if goal_data["user_id"] == user_id:
                total_goals += 1
                total_saved += goal_data["current_amount"]
                total_target += goal_data["target_amount"]
                
                if goal_data["status"] == SavingsGoalStatus.ACTIVE:
                    active_goals += 1
                elif goal_data["status"] == SavingsGoalStatus.COMPLETED:
                    completed_goals += 1
                
                # Track goal types
                goal_type = goal_data["goal_type"]
                if goal_type not in goal_type_counts:
                    goal_type_counts[goal_type] = {"count": 0, "completed": 0}
                goal_type_counts[goal_type]["count"] += 1
                if goal_data["status"] == SavingsGoalStatus.COMPLETED:
                    goal_type_counts[goal_type]["completed"] += 1
        
        # Count contributions
        for contrib_data in self.repository.data.get("savings_contributions", {}).values():
            if contrib_data["user_id"] == user_id:
                total_contributions += 1
        
        # Calculate average progress
        average_progress = 0.0
        if total_target > 0:
            average_progress = float((total_saved / total_target) * 100)
        
        # Find most successful goal type
        most_successful_goal_type = None
        best_success_rate = 0.0
        
        for goal_type, stats in goal_type_counts.items():
            if stats["count"] > 0:
                success_rate = stats["completed"] / stats["count"]
                if success_rate > best_success_rate:
                    best_success_rate = success_rate
                    most_successful_goal_type = goal_type
        
        # Calculate monthly savings rate (mock)
        monthly_savings_rate = total_saved / 12 if total_saved > 0 else Decimal("0.00")
        
        return SavingsGoalStats(
            total_goals=total_goals,
            active_goals=active_goals,
            completed_goals=completed_goals,
            total_saved=total_saved,
            total_target=total_target,
            average_progress=min(average_progress, 100.0),
            total_contributions=total_contributions,
            monthly_savings_rate=monthly_savings_rate,
            most_successful_goal_type=most_successful_goal_type
        )
    
    async def get_savings_insights(self, user_id: str) -> SavingsInsights:
        """Get personalized savings insights"""
        
        # Get statistics
        stats = await self.get_savings_statistics(user_id)
        
        # Calculate current savings rate (mock)
        current_savings_rate = float(stats.monthly_savings_rate)
        recommended_savings_rate = max(current_savings_rate * 1.2, 200.0)  # 20% increase or $200 minimum
        
        # Calculate projected completion dates
        projected_dates = {}
        for goal_data in self.repository.data.get("savings_goals", {}).values():
            if (goal_data["user_id"] == user_id and 
                goal_data["status"] == SavingsGoalStatus.ACTIVE):
                
                remaining = goal_data["target_amount"] - goal_data["current_amount"]
                if remaining > 0 and stats.monthly_savings_rate > 0:
                    months_remaining = float(remaining / stats.monthly_savings_rate)
                    projected_date = datetime.now() + timedelta(days=months_remaining * 30)
                    projected_dates[goal_data["id"]] = projected_date.strftime("%Y-%m-%d")
        
        # Calculate savings streak (mock)
        savings_streak = 15  # Mock 15-day streak
        
        # Find best and underperforming goals
        best_performing_goal = None
        underperforming_goals = []
        best_progress = 0.0
        
        for goal_data in self.repository.data.get("savings_goals", {}).values():
            if goal_data["user_id"] == user_id:
                progress = self._calculate_progress_percentage(
                    goal_data["current_amount"], 
                    goal_data["target_amount"]
                )
                
                if progress > best_progress:
                    best_progress = progress
                    best_performing_goal = goal_data["id"]
                
                if progress < 25.0 and goal_data["status"] == SavingsGoalStatus.ACTIVE:
                    underperforming_goals.append(goal_data["id"])
        
        # Generate recommendations
        recommendations = []
        if current_savings_rate < 200:
            recommendations.append("Consider increasing your monthly savings rate to build wealth faster")
        if len(underperforming_goals) > 0:
            recommendations.append("Focus on your underperforming goals to stay on track")
        if stats.active_goals > 5:
            recommendations.append("Consider consolidating some goals to focus your efforts")
        if stats.completed_goals == 0 and stats.total_goals > 0:
            recommendations.append("Set smaller, achievable milestones to build momentum")
        
        # Mock seasonal trends
        seasonal_trends = {
            "spring": 15.2,
            "summer": 8.7,
            "fall": 22.1,
            "winter": 18.9
        }
        
        return SavingsInsights(
            current_savings_rate=current_savings_rate,
            recommended_savings_rate=recommended_savings_rate,
            projected_completion_dates=projected_dates,
            savings_streak=savings_streak,
            best_performing_goal=best_performing_goal,
            underperforming_goals=underperforming_goals,
            recommendations=recommendations,
            seasonal_trends=seasonal_trends
        )
    
    async def get_auto_save_settings(self, user_id: str) -> AutoSaveSettings:
        """Get user's auto-save settings"""
        
        settings_data = self.repository.get("auto_save_settings", user_id)
        
        if not settings_data:
            # Return default settings
            default_settings = {
                "enabled": False,
                "round_up_enabled": False,
                "round_up_multiplier": 1.0,
                "percentage_save_enabled": False,
                "percentage_save_rate": 0.0,
                "fixed_amount_enabled": False,
                "fixed_amount": Decimal("0.00"),
                "fixed_amount_frequency": ContributionFrequency.MONTHLY,
                "minimum_balance": Decimal("0.00"),
                "maximum_daily_auto_save": Decimal("100.00")
            }
            self.repository.data.setdefault("auto_save_settings", {})[user_id] = default_settings
            settings_data = default_settings
        
        return AutoSaveSettings(**settings_data)
    
    async def update_auto_save_settings(
        self,
        user_id: str,
        settings_data: AutoSaveSettings
    ) -> AutoSaveSettings:
        """Update user's auto-save settings"""
        
        # Convert to dict for storage
        settings_dict = settings_data.dict()
        
        # Store updated settings
        self.repository.update("auto_save_settings", user_id, settings_dict)
        
        return settings_data
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for savings service"""
        
        # Count statistics
        total_goals = len(self.repository.data.get("savings_goals", {}))
        total_contributions = len(self.repository.data.get("savings_contributions", {}))
        total_history_entries = len(self.repository.data.get("savings_history", {}))
        
        # Count by status
        status_counts = {}
        for goal_data in self.repository.data.get("savings_goals", {}).values():
            status = goal_data["status"]
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Calculate total saved across all goals
        total_saved = Decimal("0.00")
        for goal_data in self.repository.data.get("savings_goals", {}).values():
            total_saved += goal_data["current_amount"]
        
        return {
            "service": "savings",
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "statistics": {
                "total_goals": total_goals,
                "total_contributions": total_contributions,
                "total_history_entries": total_history_entries,
                "total_saved_amount": float(total_saved),
                "status_distribution": status_counts
            },
            "features": {
                "auto_save_enabled": True,
                "goal_types_supported": len(SavingsGoalType),
                "contribution_frequencies": len(ContributionFrequency),
                "auto_save_rules": len(AutoSaveRule)
            }
        }
    
    async def _add_history_entry(
        self,
        user_id: str,
        goal_id: str,
        action: str,
        description: str,
        amount: Optional[Decimal] = None,
        previous_amount: Optional[Decimal] = None,
        new_amount: Optional[Decimal] = None
    ) -> None:
        """Add a history entry for a savings goal"""
        
        history_id = f"hist_{uuid.uuid4().hex[:8]}"
        
        history_entry = {
            "id": history_id,
            "user_id": user_id,
            "goal_id": goal_id,
            "action": action,
            "amount": amount,
            "previous_amount": previous_amount,
            "new_amount": new_amount,
            "description": description,
            "metadata": {},
            "timestamp": datetime.now()
        }
        
        self.repository.data.setdefault("savings_history", {})[history_id] = history_entry

    # Fixed Deposit Methods
    def _get_interest_rate_for_term(self, term):
        """Get interest rate for fixed deposit term"""
        from app.models.savings import FixedDepositTerm
        rates = {
            FixedDepositTerm.MONTHS_6: 3.5,
            FixedDepositTerm.MONTHS_12: 4.5,
            FixedDepositTerm.MONTHS_24: 4.8,
            FixedDepositTerm.MONTHS_36: 5.0,
            FixedDepositTerm.MONTHS_60: 5.5
        }
        return rates.get(term, 3.5)

    def _calculate_maturity_amount(self, amount, term):
        """Calculate maturity amount and interest rate"""
        from decimal import Decimal
        rate = self._get_interest_rate_for_term(term)
        months = int(str(term).split(".")[1])  # Extract months from enum
        interest = (amount * Decimal(str(rate)) * Decimal(str(months))) / Decimal("1200")  # (P * R * T) / 1200
        maturity_amount = amount + interest
        return maturity_amount, rate

    async def get_user_fixed_deposits(self, user_id: str):
        """Get user's fixed deposits"""
        from app.models.savings import FixedDepositProfile
        fixed_deposits = []
        for fd_data in self.repository.data.get("fixed_deposits", {}).values():
            if fd_data["user_id"] == user_id:
                maturity_amount, _ = self._calculate_maturity_amount(fd_data["amount"], fd_data["term"])
                profile = FixedDepositProfile(
                    id=fd_data["id"],
                    amount=fd_data["amount"],
                    term=fd_data["term"],
                    interest_rate=fd_data["interest_rate"],
                    maturity_amount=maturity_amount,
                    start_date=fd_data["start_date"],
                    maturity_date=fd_data["maturity_date"],
                    status=fd_data["status"],
                    auto_renew=fd_data["auto_renew"],
                    roundup_enabled=fd_data["roundup_enabled"],
                    currency=fd_data["currency"],
                    created_at=fd_data["created_at"]
                )
                fixed_deposits.append(profile)
        return fixed_deposits

    async def create_fixed_deposit(self, user_id: str, fd_data):
        """Create a new fixed deposit"""
        from app.models.savings import FixedDepositProfile, FixedDepositStatus
        import uuid
        from datetime import datetime
        fd_id = f"fd_{uuid.uuid4().hex[:8]}"
        start_date = datetime.now()
        maturity_date = start_date  # Simplified
        maturity_amount, interest_rate = self._calculate_maturity_amount(fd_data.amount, fd_data.term)

        fd_record = {
            "id": fd_id,
            "user_id": user_id,
            "amount": fd_data.amount,
            "term": fd_data.term,
            "interest_rate": interest_rate,
            "start_date": start_date,
            "maturity_date": maturity_date,
            "status": FixedDepositStatus.ACTIVE,
            "auto_renew": fd_data.auto_renew,
            "roundup_enabled": fd_data.roundup_enabled,
            "currency": fd_data.currency,
            "created_at": start_date
        }

        self.repository.data.setdefault("fixed_deposits", {})[fd_id] = fd_record

        return FixedDepositProfile(
            id=fd_record["id"],
            amount=fd_record["amount"],
            term=fd_record["term"],
            interest_rate=fd_record["interest_rate"],
            maturity_amount=maturity_amount,
            start_date=fd_record["start_date"],
            maturity_date=fd_record["maturity_date"],
            status=fd_record["status"],
            auto_renew=fd_record["auto_renew"],
            roundup_enabled=fd_record["roundup_enabled"],
            currency=fd_record["currency"],
            created_at=fd_record["created_at"]
        )

    # Automated Saving Methods
    async def get_user_automated_savings(self, user_id: str):
        """Get user's automated savings"""
        from app.models.savings import AutomatedSavingProfile
        automated_savings = []
        for as_data in self.repository.data.get("automated_savings", {}).values():
            if as_data["user_id"] == user_id:
                profile = AutomatedSavingProfile(
                    id=as_data["id"],
                    name=as_data["name"],
                    amount=as_data["amount"],
                    frequency=as_data["frequency"],
                    total_saved=as_data["total_saved"],
                    next_deduction=as_data["next_deduction"],
                    status=as_data["status"],
                    currency=as_data["currency"],
                    created_at=as_data["created_at"]
                )
                automated_savings.append(profile)
        return automated_savings

    async def create_automated_saving(self, user_id: str, as_data):
        """Create a new automated saving"""
        from app.models.savings import AutomatedSavingProfile, AutomatedSavingStatus
        import uuid
        from datetime import datetime
        as_id = f"as_{uuid.uuid4().hex[:8]}"
        start_date = as_data.start_date or datetime.now()
        next_deduction = start_date  # Simplified

        as_record = {
            "id": as_id,
            "user_id": user_id,
            "name": as_data.name,
            "amount": as_data.amount,
            "frequency": as_data.frequency,
            "total_saved": 0.0,
            "next_deduction": next_deduction,
            "status": AutomatedSavingStatus.ACTIVE,
            "currency": as_data.currency,
            "created_at": datetime.now()
        }

        self.repository.data.setdefault("automated_savings", {})[as_id] = as_record

        return AutomatedSavingProfile(
            id=as_record["id"],
            name=as_record["name"],
            amount=as_record["amount"],
            frequency=as_record["frequency"],
            total_saved=as_record["total_saved"],
            next_deduction=as_record["next_deduction"],
            status=as_record["status"],
            currency=as_record["currency"],
            created_at=as_record["created_at"]
        )

