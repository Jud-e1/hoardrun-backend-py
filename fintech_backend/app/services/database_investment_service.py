from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from ..database.config import get_db
from ..repositories.database_repository import InvestmentRepository, AccountRepository
from ..models.investment import InvestmentResponse, InvestmentCreateRequest, InvestmentUpdateRequest
from ..database.models import Investment as DBInvestment, InvestmentType, InvestmentStatus
from ..core.exceptions import NotFoundError, ValidationError
import uuid
from datetime import datetime
from decimal import Decimal

class DatabaseInvestmentService:
    def __init__(self):
        self.investment_repository = InvestmentRepository()
        self.account_repository = AccountRepository()
    
    def get_user_investments(self, user_id: str, db: Session) -> List[InvestmentResponse]:
        """Get all investments for a user"""
        investments = self.investment_repository.get_investments_by_user_id(db, user_id)
        return [self._convert_to_response(investment) for investment in investments]
    
    def get_investment_by_id(self, investment_id: str, user_id: str, db: Session) -> InvestmentResponse:
        """Get a specific investment by ID"""
        investment = self.investment_repository.get_by_id(db, investment_id)
        if not investment or investment.user_id != user_id:
            raise NotFoundError(f"Investment with ID {investment_id} not found")
        return self._convert_to_response(investment)
    
    def create_investment(self, user_id: str, investment_data: InvestmentCreateRequest, db: Session) -> InvestmentResponse:
        """Create a new investment"""
        # Verify the account exists and belongs to the user
        account = self.account_repository.get_by_id(db, investment_data.account_id)
        if not account or account.user_id != user_id:
            raise ValidationError("Invalid account ID or account does not belong to user")
        
        # Check if account has sufficient balance
        if account.balance < Decimal(str(investment_data.amount)):
            raise ValidationError("Insufficient account balance for investment")
        
        # Create investment
        investment_dict = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "account_id": investment_data.account_id,
            "investment_type": InvestmentType(investment_data.investment_type),
            "name": investment_data.name,
            "symbol": investment_data.symbol,
            "amount": Decimal(str(investment_data.amount)),
            "units": Decimal(str(investment_data.units)) if investment_data.units else None,
            "price_per_unit": Decimal(str(investment_data.price_per_unit)) if investment_data.price_per_unit else None,
            "current_value": Decimal(str(investment_data.amount)),  # Initially same as invested amount
            "expected_return": Decimal(str(investment_data.expected_return)) if investment_data.expected_return else None,
            "maturity_date": investment_data.maturity_date,
            "status": InvestmentStatus.ACTIVE,
            "metadata": investment_data.metadata or {},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        investment = self.investment_repository.create(db, investment_dict)
        
        # Deduct investment amount from account balance
        new_balance = account.balance - Decimal(str(investment_data.amount))
        self.account_repository.update(db, account.id, {
            "balance": new_balance,
            "updated_at": datetime.utcnow()
        })
        
        return self._convert_to_response(investment)
    
    def update_investment(self, investment_id: str, user_id: str, investment_data: InvestmentUpdateRequest, db: Session) -> InvestmentResponse:
        """Update investment details"""
        investment = self.investment_repository.get_by_id(db, investment_id)
        if not investment or investment.user_id != user_id:
            raise NotFoundError(f"Investment with ID {investment_id} not found")
        
        update_data = {}
        if investment_data.current_value is not None:
            update_data["current_value"] = Decimal(str(investment_data.current_value))
        if investment_data.price_per_unit is not None:
            update_data["price_per_unit"] = Decimal(str(investment_data.price_per_unit))
        if investment_data.expected_return is not None:
            update_data["expected_return"] = Decimal(str(investment_data.expected_return))
        if investment_data.maturity_date is not None:
            update_data["maturity_date"] = investment_data.maturity_date
        if investment_data.metadata is not None:
            update_data["metadata"] = investment_data.metadata
        
        if update_data:
            update_data["updated_at"] = datetime.utcnow()
            investment = self.investment_repository.update(db, investment_id, update_data)
        
        return self._convert_to_response(investment)
    
    def sell_investment(self, investment_id: str, user_id: str, sell_amount: Optional[float] = None, db: Session = None) -> InvestmentResponse:
        """Sell an investment (partial or full)"""
        investment = self.investment_repository.get_by_id(db, investment_id)
        if not investment or investment.user_id != user_id:
            raise NotFoundError(f"Investment with ID {investment_id} not found")
        
        if investment.status != InvestmentStatus.ACTIVE:
            raise ValidationError("Investment is not active and cannot be sold")
        
        # Get the account to credit the sale proceeds
        account = self.account_repository.get_by_id(db, investment.account_id)
        if not account:
            raise ValidationError("Associated account not found")
        
        if sell_amount is None:
            # Full sale
            sale_proceeds = investment.current_value
            update_data = {
                "status": InvestmentStatus.SOLD,
                "updated_at": datetime.utcnow()
            }
        else:
            # Partial sale
            sell_amount_decimal = Decimal(str(sell_amount))
            if sell_amount_decimal > investment.current_value:
                raise ValidationError("Sell amount cannot exceed current investment value")
            
            sale_proceeds = sell_amount_decimal
            remaining_value = investment.current_value - sell_amount_decimal
            
            if remaining_value <= 0:
                # If remaining value is 0 or negative, mark as sold
                update_data = {
                    "current_value": Decimal('0'),
                    "status": InvestmentStatus.SOLD,
                    "updated_at": datetime.utcnow()
                }
            else:
                # Update current value for partial sale
                update_data = {
                    "current_value": remaining_value,
                    "updated_at": datetime.utcnow()
                }
        
        # Update investment
        investment = self.investment_repository.update(db, investment_id, update_data)
        
        # Credit sale proceeds to account
        new_balance = account.balance + sale_proceeds
        self.account_repository.update(db, account.id, {
            "balance": new_balance,
            "updated_at": datetime.utcnow()
        })
        
        return self._convert_to_response(investment)
    
    def get_investment_summary(self, user_id: str, db: Session) -> Dict[str, Any]:
        """Get investment summary for a user"""
        investments = self.investment_repository.get_investments_by_user_id(db, user_id)
        
        total_investments = len(investments)
        total_invested = sum(inv.amount for inv in investments)
        total_current_value = sum(inv.current_value for inv in investments)
        total_return = total_current_value - total_invested
        
        # Group by status
        status_counts = {}
        for investment in investments:
            status = investment.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Group by type
        type_breakdown = {}
        for investment in investments:
            inv_type = investment.investment_type.value
            if inv_type not in type_breakdown:
                type_breakdown[inv_type] = {
                    "count": 0,
                    "total_invested": 0,
                    "total_current_value": 0
                }
            type_breakdown[inv_type]["count"] += 1
            type_breakdown[inv_type]["total_invested"] += float(investment.amount)
            type_breakdown[inv_type]["total_current_value"] += float(investment.current_value)
        
        return {
            "total_investments": total_investments,
            "total_invested": float(total_invested),
            "total_current_value": float(total_current_value),
            "total_return": float(total_return),
            "return_percentage": float((total_return / total_invested * 100)) if total_invested > 0 else 0,
            "status_breakdown": status_counts,
            "type_breakdown": type_breakdown
        }
    
    def get_investments_by_type(self, user_id: str, investment_type: str, db: Session) -> List[InvestmentResponse]:
        """Get investments by type for a user"""
        try:
            inv_type = InvestmentType(investment_type)
        except ValueError:
            raise ValidationError(f"Invalid investment type: {investment_type}")
        
        investments = self.investment_repository.get_investments_by_type(db, user_id, inv_type)
        return [self._convert_to_response(investment) for investment in investments]
    
    def _convert_to_response(self, investment: DBInvestment) -> InvestmentResponse:
        """Convert database investment to response model"""
        return InvestmentResponse(
            id=investment.id,
            account_id=investment.account_id,
            investment_type=investment.investment_type.value,
            name=investment.name,
            symbol=investment.symbol,
            amount=float(investment.amount),
            units=float(investment.units) if investment.units else None,
            price_per_unit=float(investment.price_per_unit) if investment.price_per_unit else None,
            current_value=float(investment.current_value),
            expected_return=float(investment.expected_return) if investment.expected_return else None,
            maturity_date=investment.maturity_date,
            status=investment.status.value,
            metadata=investment.metadata,
            created_at=investment.created_at,
            updated_at=investment.updated_at
        )
