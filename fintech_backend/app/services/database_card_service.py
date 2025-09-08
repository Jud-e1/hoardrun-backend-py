from typing import List, Optional
from sqlalchemy.orm import Session
from app.database.config import get_db
from app.repositories.database_repository import CardRepository, AccountRepository
from app.models.card import CardResponse, CardCreateRequest, CardUpdateRequest
from app.database.models import Card as DBCard, CardTypeEnum, CardStatusEnum
from app.core.exceptions import CardNotFoundException, ValidationException
import uuid
from datetime import datetime, timedelta
import random
import string

class DatabaseCardService:
    def __init__(self):
        self.card_repository = CardRepository()
        self.account_repository = AccountRepository()
    
    def _generate_card_number(self) -> str:
        """Generate a random 16-digit card number"""
        return ''.join([str(random.randint(0, 9)) for _ in range(16)])
    
    def _generate_cvv(self) -> str:
        """Generate a random 3-digit CVV"""
        return ''.join([str(random.randint(0, 9)) for _ in range(3)])
    
    def _generate_pin(self) -> str:
        """Generate a random 4-digit PIN"""
        return ''.join([str(random.randint(0, 9)) for _ in range(4)])

    def get_user_cards(self, user_id: str, db: Session) -> List[CardResponse]:
        """Get all cards for a user"""
        cards = self.card_repository.get_cards_by_user_id(db, user_id)
        return [self._convert_to_response(card) for card in cards]
    
    def get_card_by_id(self, card_id: str, user_id: str, db: Session) -> CardResponse:
        """Get a specific card by ID"""
        card = self.card_repository.get_by_id(db, card_id)
        if not card or card.user_id != user_id:
            raise CardNotFoundException(card_id)
        return self._convert_to_response(card)
    
    def create_card(self, user_id: str, card_data: CardCreateRequest, db: Session) -> CardResponse:
        """Create a new card"""
        # Verify the account exists and belongs to the user
        account = self.account_repository.get_by_id(db, card_data.account_id)
        if not account or account.user_id != user_id:
            raise ValidationException("Invalid account ID or account does not belong to user")
        
        # Create new card
        card_dict = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "account_id": card_data.account_id,
            "card_type": CardTypeEnum(card_data.card_type),
            "card_number": self._generate_card_number(),
            "cardholder_name": card_data.cardholder_name,
            "expiry_date": datetime.now() + timedelta(days=365 * 3),  # 3 years from now
            "cvv": self._generate_cvv(),
            "pin": self._generate_pin(),
            "daily_limit": card_data.daily_limit,
            "monthly_limit": card_data.monthly_limit,
            "status": CardStatusEnum.ACTIVE,
            "is_blocked": False,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        card = self.card_repository.create(db, card_dict)
        return self._convert_to_response(card)
    
    def update_card(self, card_id: str, user_id: str, card_data: CardUpdateRequest, db: Session) -> CardResponse:
        """Update card details"""
        card = self.card_repository.get_by_id(db, card_id)
        if not card or card.user_id != user_id:
            raise CardNotFoundException(card_id)
        
        update_data = {}
        if card_data.daily_limit is not None:
            update_data["daily_limit"] = card_data.daily_limit
        if card_data.monthly_limit is not None:
            update_data["monthly_limit"] = card_data.monthly_limit
        if card_data.cardholder_name is not None:
            update_data["cardholder_name"] = card_data.cardholder_name
        
        if update_data:
            update_data["updated_at"] = datetime.utcnow()
            card = self.card_repository.update(db, card_id, update_data)
        
        return self._convert_to_response(card)
    
    def block_card(self, card_id: str, user_id: str, db: Session) -> CardResponse:
        """Block a card"""
        card = self.card_repository.get_by_id(db, card_id)
        if not card or card.user_id != user_id:
            raise CardNotFoundException(card_id)
        
        update_data = {
            "is_blocked": True,
            "status": CardStatusEnum.BLOCKED,
            "updated_at": datetime.utcnow()
        }
        
        card = self.card_repository.update(db, card_id, update_data)
        return self._convert_to_response(card)
    
    def unblock_card(self, card_id: str, user_id: str, db: Session) -> CardResponse:
        """Unblock a card"""
        card = self.card_repository.get_by_id(db, card_id)
        if not card or card.user_id != user_id:
            raise CardNotFoundException(card_id)
        
        update_data = {
            "is_blocked": False,
            "status": CardStatusEnum.ACTIVE,
            "updated_at": datetime.utcnow()
        }
        
        card = self.card_repository.update(db, card_id, update_data)
        return self._convert_to_response(card)
    
    def delete_card(self, card_id: str, user_id: str, db: Session) -> bool:
        """Delete a card"""
        card = self.card_repository.get_by_id(db, card_id)
        if not card or card.user_id != user_id:
            raise CardNotFoundException(card_id)
        
        return self.card_repository.delete(db, card_id)
    
    def _convert_to_response(self, card: DBCard) -> CardResponse:
        """Convert database card to response model"""
        return CardResponse(
            id=card.id,
            account_id=card.account_id,
            card_type=card.card_type.value,
            card_number=f"****-****-****-{card.card_number[-4:]}",  # Mask card number
            cardholder_name=card.cardholder_name,
            expiry_date=card.expiry_date,
            daily_limit=float(card.daily_limit),
            monthly_limit=float(card.monthly_limit),
            status=card.status.value,
            is_blocked=card.is_blocked,
            created_at=card.created_at,
            updated_at=card.updated_at
        )
