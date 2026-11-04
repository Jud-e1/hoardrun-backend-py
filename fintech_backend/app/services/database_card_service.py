import calendar
import secrets
from datetime import date, datetime
from typing import List

from sqlalchemy.orm import Session

from ..repositories.database_repository import CardRepository, AccountRepository
from ..models.flat_card import Card, CardCreateRequest, CardUpdateRequest
from ..database.models import Card as DBCard, CardTypeEnum, CardStatusEnum
from ..core.exceptions import CardNotFoundException, ValidationException

CARD_VALIDITY_YEARS = 3
MASKED_NUMBER_ATTEMPTS = 20


class DatabaseCardService:
    """Card operations backed by the database. Only masked numbers are ever stored."""

    def _generate_masked_number(self, repository: CardRepository) -> str:
        """Generate a masked card number that is not in use yet."""
        for _ in range(MASKED_NUMBER_ATTEMPTS):
            masked = f"****{secrets.randbelow(10000):04d}"
            if not repository.get_card_by_masked_number(masked):
                return masked
        raise ValidationException("Could not generate a unique card number")

    def _get_owned_card(self, repository: CardRepository, card_id: str, user_id: str) -> DBCard:
        """Get a card, reporting other users' cards as not found."""
        card = repository.get_card_by_id(card_id)
        if not card or card.user_id != user_id:
            raise CardNotFoundException(card_id)
        return card

    def get_user_cards(self, user_id: str, db: Session) -> List[Card]:
        """Get all cards for a user"""
        cards = CardRepository(db).get_cards_by_user_id(user_id)
        return [self._convert_to_response(card) for card in cards]

    def get_card_by_id(self, card_id: str, user_id: str, db: Session) -> Card:
        """Get a specific card by ID"""
        return self._convert_to_response(self._get_owned_card(CardRepository(db), card_id, user_id))

    def create_card(self, user_id: str, card_data: CardCreateRequest, db: Session) -> Card:
        """Create a new card"""
        # Verify the account exists and belongs to the user
        account = AccountRepository(db).get_account_by_id(card_data.account_id)
        if not account or account.user_id != user_id:
            raise ValidationException("Invalid account ID or account does not belong to user")

        repository = CardRepository(db)
        today = date.today()
        card = repository.create_card(
            user_id=user_id,
            account_id=card_data.account_id,
            card_type=CardTypeEnum(card_data.card_type.value),
            cardholder_name=card_data.name_on_card,
            card_number_masked=self._generate_masked_number(repository),
            expiry_month=today.month,
            expiry_year=today.year + CARD_VALIDITY_YEARS,
        )
        return self._convert_to_response(card)

    def update_card(self, card_id: str, user_id: str, card_data: CardUpdateRequest, db: Session) -> Card:
        """Update card details"""
        repository = CardRepository(db)
        card = self._get_owned_card(repository, card_id, user_id)

        if card_data.daily_limit is not None or card_data.monthly_limit is not None:
            card = repository.update_card_limits(card_id, card_data.daily_limit, card_data.monthly_limit)
        if card_data.name_on_card is not None:
            card = repository.update_cardholder_name(card_id, card_data.name_on_card)

        return self._convert_to_response(card)

    def block_card(self, card_id: str, user_id: str, db: Session) -> Card:
        """Block a card"""
        repository = CardRepository(db)
        self._get_owned_card(repository, card_id, user_id)
        return self._convert_to_response(repository.update_card_status(card_id, CardStatusEnum.BLOCKED))

    def unblock_card(self, card_id: str, user_id: str, db: Session) -> Card:
        """Unblock a card"""
        repository = CardRepository(db)
        self._get_owned_card(repository, card_id, user_id)
        return self._convert_to_response(repository.update_card_status(card_id, CardStatusEnum.ACTIVE))

    def delete_card(self, card_id: str, user_id: str, db: Session) -> bool:
        """Delete a card"""
        repository = CardRepository(db)
        self._get_owned_card(repository, card_id, user_id)
        return repository.delete_card(card_id)

    def _convert_to_response(self, card: DBCard) -> Card:
        """Convert database card to response model"""
        last_day = calendar.monthrange(card.expiry_year, card.expiry_month)[1]
        return Card(
            id=card.id,
            account_id=card.account_id,
            user_id=card.user_id,
            card_number=card.card_number_masked,
            card_type=card.card_type.value,
            name_on_card=card.cardholder_name,
            expiry_date=date(card.expiry_year, card.expiry_month, last_day),
            status=card.status.value,
            daily_limit=card.daily_limit,
            monthly_limit=card.monthly_limit,
            is_contactless=card.is_contactless_enabled,
            is_international=card.is_international_enabled,
            created_at=card.created_at or datetime.utcnow(),
            updated_at=card.updated_at or card.created_at or datetime.utcnow(),
        )
