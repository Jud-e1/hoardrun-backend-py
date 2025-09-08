from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.database.config import get_db
from app.repositories.database_repository import TransferRepository, AccountRepository, TransactionRepository
from app.models.transfer import TransferResponse, TransferCreateRequest, TransferStatus, TransferType
from app.models.transaction import TransactionType, TransactionStatus
from app.database.models import Transfer as DBTransfer
from app.core.exceptions import AccountNotFoundException, ValidationException
import uuid
from datetime import datetime
from decimal import Decimal

class DatabaseTransferService:
    def __init__(self):
        self.transfer_repository = TransferRepository()
        self.account_repository = AccountRepository()
        self.transaction_repository = TransactionRepository()
    
    def get_user_transfers(self, user_id: str, limit: int = 50, offset: int = 0, db: Session = None) -> List[TransferResponse]:
        """Get transfers for a user (both sent and received)"""
        transfers = self.transfer_repository.get_transfers_by_user_id(db, user_id, limit, offset)
        return [self._convert_to_response(transfer) for transfer in transfers]
    
    def get_transfer_by_id(self, transfer_id: str, user_id: str, db: Session) -> TransferResponse:
        """Get a specific transfer by ID"""
        transfer = self.transfer_repository.get_by_id(db, transfer_id)
        if not transfer:
            raise AccountNotFoundException(f"Transfer with ID {transfer_id} not found")
        
        # Verify the transfer involves the user (either as sender or recipient)
        from_account = self.account_repository.get_by_id(db, transfer.from_account_id)
        to_account = self.account_repository.get_by_id(db, transfer.to_account_id)
        
        if not ((from_account and from_account.user_id == user_id) or 
                (to_account and to_account.user_id == user_id)):
            raise AccountNotFoundException(f"Transfer with ID {transfer_id} not found")
        
        return self._convert_to_response(transfer)
    
    def create_transfer(self, user_id: str, transfer_data: TransferCreateRequest, db: Session) -> TransferResponse:
        """Create a new transfer"""
        # Verify source account exists and belongs to the user
        from_account = self.account_repository.get_by_id(db, transfer_data.source_account_id)
        if not from_account or from_account.user_id != user_id:
            raise ValidationException("Invalid source account ID or account does not belong to user")
        
        # Verify destination account exists
        to_account = self.account_repository.get_by_id(db, transfer_data.destination_account_id)
        if not to_account:
            raise ValidationException("Invalid destination account ID")
        
        # Check if source account has sufficient balance
        transfer_amount = Decimal(str(transfer_data.amount))
        if from_account.balance < transfer_amount:
            raise ValidationException("Insufficient balance in source account")
        
        # Use the transfer type from the request or default to instant transfer
        transfer_type = transfer_data.transfer_type
        
        # Create transfer
        transfer_dict = {
            "id": str(uuid.uuid4()),
            "from_account_id": transfer_data.source_account_id,
            "to_account_id": transfer_data.destination_account_id,
            "amount": transfer_amount,
            "currency": transfer_data.currency,
            "description": transfer_data.description,
            "reference": transfer_data.reference or f"TRF-{datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8]}",
            "transfer_type": transfer_type,
            "status": TransferStatus.PENDING,
            "metadata": getattr(transfer_data, 'metadata', {}) or {},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        transfer = self.transfer_repository.create(db, transfer_dict)
        
        # Process the transfer
        self._process_transfer(transfer, from_account, to_account, db)
        
        # Update transfer status to completed
        transfer = self.transfer_repository.update(db, transfer.id, {
            "status": TransferStatus.COMPLETED,
            "updated_at": datetime.utcnow()
        })
        
        return self._convert_to_response(transfer)
    
    def get_account_transfers(self, account_id: str, user_id: str, limit: int = 50, offset: int = 0, db: Session = None) -> List[TransferResponse]:
        """Get transfers for a specific account"""
        # Verify account belongs to user
        account = self.account_repository.get_by_id(db, account_id)
        if not account or account.user_id != user_id:
            raise AccountNotFoundException(f"Account with ID {account_id} not found")
        
        transfers = self.transfer_repository.get_transfers_by_account_id(db, account_id, limit, offset)
        return [self._convert_to_response(transfer) for transfer in transfers]
    
    def get_sent_transfers(self, user_id: str, limit: int = 50, offset: int = 0, db: Session = None) -> List[TransferResponse]:
        """Get transfers sent by the user"""
        transfers = self.transfer_repository.get_sent_transfers(db, user_id, limit, offset)
        return [self._convert_to_response(transfer) for transfer in transfers]
    
    def get_received_transfers(self, user_id: str, limit: int = 50, offset: int = 0, db: Session = None) -> List[TransferResponse]:
        """Get transfers received by the user"""
        transfers = self.transfer_repository.get_received_transfers(db, user_id, limit, offset)
        return [self._convert_to_response(transfer) for transfer in transfers]
    
    def cancel_transfer(self, transfer_id: str, user_id: str, db: Session) -> TransferResponse:
        """Cancel a pending transfer"""
        transfer = self.transfer_repository.get_by_id(db, transfer_id)
        if not transfer:
            raise AccountNotFoundException(f"Transfer with ID {transfer_id} not found")
        
        # Verify the transfer belongs to the user (sender)
        from_account = self.account_repository.get_by_id(db, transfer.from_account_id)
        if not from_account or from_account.user_id != user_id:
            raise AccountNotFoundException(f"Transfer with ID {transfer_id} not found")
        
        # Can only cancel pending transfers
        if transfer.status != TransferStatus.PENDING:
            raise ValidationException("Only pending transfers can be cancelled")
        
        # Update transfer status
        transfer = self.transfer_repository.update(db, transfer_id, {
            "status": TransferStatus.CANCELLED,
            "updated_at": datetime.utcnow()
        })
        
        return self._convert_to_response(transfer)
    
    def get_transfer_summary(self, user_id: str, db: Session) -> Dict[str, Any]:
        """Get transfer summary for a user"""
        sent_transfers = self.transfer_repository.get_sent_transfers(db, user_id)
        received_transfers = self.transfer_repository.get_received_transfers(db, user_id)
        
        total_sent = sum(t.amount for t in sent_transfers)
        total_received = sum(t.amount for t in received_transfers)
        
        # Group by status
        status_counts = {"sent": {}, "received": {}}
        for transfer in sent_transfers:
            status = transfer.status.value
            status_counts["sent"][status] = status_counts["sent"].get(status, 0) + 1
        
        for transfer in received_transfers:
            status = transfer.status.value
            status_counts["received"][status] = status_counts["received"].get(status, 0) + 1
        
        # Group by type
        type_counts = {}
        all_transfers = sent_transfers + received_transfers
        for transfer in all_transfers:
            transfer_type = transfer.transfer_type.value
            type_counts[transfer_type] = type_counts.get(transfer_type, 0) + 1
        
        return {
            "total_sent_transfers": len(sent_transfers),
            "total_received_transfers": len(received_transfers),
            "total_sent_amount": float(total_sent),
            "total_received_amount": float(total_received),
            "net_transfer_amount": float(total_received - total_sent),
            "status_breakdown": status_counts,
            "type_breakdown": type_counts
        }
    
    def _process_transfer(self, transfer: DBTransfer, from_account, to_account, db: Session):
        """Process the actual transfer by updating account balances and creating transactions"""
        # Debit from source account
        new_from_balance = from_account.balance - transfer.amount
        self.account_repository.update(db, from_account.id, {
            "balance": new_from_balance,
            "updated_at": datetime.utcnow()
        })
        
        # Credit to destination account
        new_to_balance = to_account.balance + transfer.amount
        self.account_repository.update(db, to_account.id, {
            "balance": new_to_balance,
            "updated_at": datetime.utcnow()
        })
        
        # Create debit transaction for source account
        debit_transaction = {
            "id": str(uuid.uuid4()),
            "account_id": from_account.id,
            "transaction_type": TransactionType.TRANSFER_OUT,
            "amount": transfer.amount,
            "currency": transfer.currency,
            "description": f"Transfer to {to_account.account_number}: {transfer.description}",
            "reference": f"{transfer.reference}-OUT",
            "status": TransactionStatus.COMPLETED,
            "metadata": {
                "transfer_id": transfer.id,
                "transfer_type": "outgoing",
                "destination_account": to_account.account_number
            },
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        self.transaction_repository.create(db, debit_transaction)
        
        # Create credit transaction for destination account
        credit_transaction = {
            "id": str(uuid.uuid4()),
            "account_id": to_account.id,
            "transaction_type": TransactionType.TRANSFER_IN,
            "amount": transfer.amount,
            "currency": transfer.currency,
            "description": f"Transfer from {from_account.account_number}: {transfer.description}",
            "reference": f"{transfer.reference}-IN",
            "status": TransactionStatus.COMPLETED,
            "metadata": {
                "transfer_id": transfer.id,
                "transfer_type": "incoming",
                "source_account": from_account.account_number
            },
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        self.transaction_repository.create(db, credit_transaction)
    
    def _convert_to_response(self, transfer: DBTransfer) -> TransferResponse:
        """Convert database transfer to response model"""
        return TransferResponse(
            id=transfer.id,
            from_account_id=transfer.from_account_id,
            to_account_id=transfer.to_account_id,
            amount=float(transfer.amount),
            currency=transfer.currency,
            description=transfer.description,
            reference=transfer.reference,
            transfer_type=transfer.transfer_type.value,
            status=transfer.status.value,
            metadata=transfer.metadata,
            created_at=transfer.created_at,
            updated_at=transfer.updated_at
        )
