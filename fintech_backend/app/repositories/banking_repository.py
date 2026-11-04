"""
Database storage for beneficiaries, Plaid data and bank transfers.

Mixed into RepositoryManager, which is what the services hold as self.repo.
"""

from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from ..database.banking_models import (
    BankBeneficiary, BankTransfer, BankTransferQuote, PlaidAccountRecord, PlaidConnectionRecord,
    PlaidLinkTokenRecord, PlaidTransactionRecord, TransactionMetadata
)
from ..database.config import SessionLocal
from ..database.models import User
from ..models.plaid import PlaidAccount, PlaidConnection, PlaidTransaction
from ..models.transfer import Beneficiary, MoneyTransfer, TransferStatus

# Transfers in these states don't count towards a user's limits
_EXCLUDED_FROM_VOLUME = {
    TransferStatus.FAILED.value, TransferStatus.CANCELLED.value, TransferStatus.RETURNED.value
}


@contextmanager
def _session():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _plain(value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value


def _row_values(record_class, model) -> Dict[str, Any]:
    """Values from a Pydantic model for the columns its table has."""
    columns = record_class.__table__.columns.keys()
    return {
        name: _plain(getattr(model, name))
        for name in columns
        if hasattr(model, name)
    }


def _to_model(model_class, row):
    """Build a Pydantic model from a table row."""
    return model_class(**{
        name: getattr(row, name)
        for name in model_class.model_fields
        if hasattr(row, name)
    })


class BankingRepositoryMixin:
    """Beneficiary, Plaid and transfer storage."""

    # Users
    async def get_user_legal_name(self, user_id: str) -> Optional[str]:
        with _session() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return None
            return f"{user.first_name or ''} {user.last_name or ''}".strip() or None

    # Beneficiaries
    async def get_user_beneficiaries(self, user_id: str) -> List[Beneficiary]:
        with _session() as db:
            rows = (
                db.query(BankBeneficiary)
                .filter(BankBeneficiary.user_id == user_id)
                .order_by(BankBeneficiary.created_at.desc())
                .all()
            )
            return [_to_model(Beneficiary, row) for row in rows]

    async def get_beneficiary_by_id(self, beneficiary_id: str) -> Optional[Beneficiary]:
        with _session() as db:
            row = db.get(BankBeneficiary, beneficiary_id)
            return _to_model(Beneficiary, row) if row else None

    async def create_beneficiary(self, beneficiary: Beneficiary) -> None:
        with _session() as db:
            db.add(BankBeneficiary(**_row_values(BankBeneficiary, beneficiary)))

    async def update_beneficiary(self, beneficiary: Beneficiary) -> None:
        with _session() as db:
            db.merge(BankBeneficiary(**_row_values(BankBeneficiary, beneficiary)))

    async def delete_beneficiary(self, beneficiary_id: str) -> None:
        with _session() as db:
            db.query(BankBeneficiary).filter(BankBeneficiary.beneficiary_id == beneficiary_id).delete()

    # Plaid link tokens
    async def create_plaid_link_token(self, data: Dict[str, Any]) -> None:
        with _session() as db:
            db.add(PlaidLinkTokenRecord(**data))

    async def update_plaid_link_token_used(self, link_token_id: str) -> None:
        with _session() as db:
            db.query(PlaidLinkTokenRecord).filter(
                PlaidLinkTokenRecord.link_token_id == link_token_id
            ).update({"used": True})

    # Plaid connections
    async def create_plaid_connection(self, connection: PlaidConnection) -> None:
        with _session() as db:
            db.add(PlaidConnectionRecord(**_row_values(PlaidConnectionRecord, connection)))

    async def update_plaid_connection(self, connection: PlaidConnection) -> None:
        with _session() as db:
            db.merge(PlaidConnectionRecord(**_row_values(PlaidConnectionRecord, connection)))

    async def get_plaid_connection(self, connection_id: str) -> Optional[PlaidConnection]:
        with _session() as db:
            row = db.get(PlaidConnectionRecord, connection_id)
            return _to_model(PlaidConnection, row) if row else None

    async def get_plaid_connection_by_item_id(self, item_id: str) -> Optional[PlaidConnection]:
        with _session() as db:
            row = db.query(PlaidConnectionRecord).filter(PlaidConnectionRecord.item_id == item_id).first()
            return _to_model(PlaidConnection, row) if row else None

    async def get_user_plaid_connections(self, user_id: str) -> List[PlaidConnection]:
        with _session() as db:
            rows = db.query(PlaidConnectionRecord).filter(PlaidConnectionRecord.user_id == user_id).all()
            return [_to_model(PlaidConnection, row) for row in rows]

    # Plaid accounts
    async def upsert_plaid_account(self, account: PlaidAccount) -> None:
        with _session() as db:
            existing = db.get(PlaidAccountRecord, account.account_id)
            values = _row_values(PlaidAccountRecord, account)
            if existing:
                values["created_at"] = existing.created_at
            db.merge(PlaidAccountRecord(**values))

    async def get_plaid_accounts(self, connection_id: str) -> List[PlaidAccount]:
        with _session() as db:
            rows = db.query(PlaidAccountRecord).filter(PlaidAccountRecord.connection_id == connection_id).all()
            return [_to_model(PlaidAccount, row) for row in rows]

    async def get_plaid_account(self, account_id: str) -> Optional[PlaidAccount]:
        with _session() as db:
            row = db.get(PlaidAccountRecord, account_id)
            return _to_model(PlaidAccount, row) if row else None

    # Plaid transactions
    async def upsert_plaid_transaction(self, transaction: PlaidTransaction) -> None:
        with _session() as db:
            existing = db.get(PlaidTransactionRecord, transaction.transaction_id)
            values = _row_values(PlaidTransactionRecord, transaction)
            if existing:
                values["created_at"] = existing.created_at
            db.merge(PlaidTransactionRecord(**values))

    async def get_plaid_transaction(self, transaction_id: str) -> Optional[PlaidTransaction]:
        with _session() as db:
            row = db.get(PlaidTransactionRecord, transaction_id)
            return _to_model(PlaidTransaction, row) if row else None

    async def get_plaid_transactions_by_date_range(
        self, connection_id: str, start_date: date, end_date: date
    ) -> List[PlaidTransaction]:
        with _session() as db:
            rows = (
                db.query(PlaidTransactionRecord)
                .filter(
                    PlaidTransactionRecord.connection_id == connection_id,
                    PlaidTransactionRecord.date >= str(start_date),
                    PlaidTransactionRecord.date <= str(end_date),
                )
                .order_by(PlaidTransactionRecord.date.desc())
                .all()
            )
            return [_to_model(PlaidTransaction, row) for row in rows]

    # Transaction notes and tags
    async def get_transaction_metadata(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        with _session() as db:
            row = db.get(TransactionMetadata, transaction_id)
            return dict(row.data) if row else None

    async def save_transaction_metadata(self, transaction_id: str, metadata: Dict[str, Any]) -> None:
        with _session() as db:
            db.merge(TransactionMetadata(transaction_id=transaction_id, data=metadata))

    # Transfer quotes
    async def create_quote_record(self, values: Dict[str, Any]) -> None:
        with _session() as db:
            db.add(BankTransferQuote(**{name: _plain(value) for name, value in values.items()}))

    async def get_quote_by_id(self, quote_id: str) -> Optional[Dict[str, Any]]:
        with _session() as db:
            row = db.get(BankTransferQuote, quote_id)
            if not row:
                return None
            return {name: getattr(row, name) for name in BankTransferQuote.__table__.columns.keys()}

    async def claim_quote(self, quote_id: str) -> bool:
        """Mark a quote used. Only the first caller gets True, so a quote can't pay out twice."""
        with _session() as db:
            claimed = db.query(BankTransferQuote).filter(
                BankTransferQuote.quote_id == quote_id,
                BankTransferQuote.used_at.is_(None),
            ).update({"used_at": datetime.utcnow()}, synchronize_session=False)
            return claimed == 1

    # Transfers
    async def create_transfer(self, transfer: MoneyTransfer) -> None:
        with _session() as db:
            db.add(BankTransfer(**_row_values(BankTransfer, transfer)))

    async def update_transfer(self, transfer: MoneyTransfer) -> None:
        with _session() as db:
            db.merge(BankTransfer(**_row_values(BankTransfer, transfer)))

    async def get_transfer_by_id(self, transfer_id: str) -> Optional[MoneyTransfer]:
        with _session() as db:
            row = db.get(BankTransfer, transfer_id)
            return _to_model(MoneyTransfer, row) if row else None

    async def get_user_transfers(self, user_id: str) -> List[MoneyTransfer]:
        with _session() as db:
            rows = (
                db.query(BankTransfer)
                .filter(BankTransfer.user_id == user_id)
                .order_by(BankTransfer.created_at.desc())
                .all()
            )
            return [_to_model(MoneyTransfer, row) for row in rows]

    async def get_user_transfer_volume(self, user_id: str, period: str = "daily") -> Decimal:
        """Total sent by a user in the current day, month or year (UTC)."""
        now = datetime.utcnow()
        starts = {
            "daily": now.replace(hour=0, minute=0, second=0, microsecond=0),
            "monthly": now.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
            "annual": now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0),
        }
        with _session() as db:
            rows = (
                db.query(BankTransfer)
                .filter(BankTransfer.user_id == user_id, BankTransfer.created_at >= starts[period])
                .all()
            )
            return sum(
                (Decimal(row.source_amount) for row in rows if row.status not in _EXCLUDED_FROM_VOLUME),
                Decimal("0"),
            )
