"""
Mobile Money service for mobile payment integration.
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from decimal import Decimal

from app.models.mobile_money import (
    MobileMoneyTransferRequest, MobileMoneyReceiveRequest, MobileMoneyAccountRequest,
    MobileMoneyDepositRequest, MobileMoneyTransaction, MobileMoneyAccount,
    MobileMoneyProvider_Info, MobileMoneyTransactionFilter, MobileMoneyStats,
    MobileMoneyFeeCalculation, MobileMoneyTransactionCreate, MobileMoneyTransactionUpdate,
    MobileMoneyAccountCreate, MobileMoneyAccountUpdate, MobileMoneyProvider,
    TransactionType, TransactionStatus, Currency
)
from app.services.auth_service import AuthService
from app.core.exceptions import (
    ValidationException, AuthenticationException, NotFoundError, BusinessLogicError
)
from app.config.settings import get_settings
from app.config.logging import get_logger
from app.external.mtn_momo_api import get_mtn_momo_client

logger = get_logger(__name__)
settings = get_settings()


class MobileMoneyService:
    """Mobile Money service for handling mobile payment operations."""
    
    def __init__(self):
        self.auth_service = AuthService()
        self.mtn_momo_client = get_mtn_momo_client()
    
    async def send_money(self, token: str, request: MobileMoneyTransferRequest, db: Session) -> MobileMoneyTransaction:
        """
        Send money via mobile money.
        
        Args:
            token: Access token
            request: Transfer request
            db: Database session
            
        Returns:
            MobileMoneyTransaction: Created transaction
        """
        try:
            logger.info(f"Sending mobile money: {request.provider} - {request.amount} {request.currency}")
            
            # Get current user
            current_user = await self.auth_service.get_current_user(token, db)
            
            # Validate provider and amount limits
            provider_info = await self._get_provider_info(request.provider, db)
            if not provider_info.is_active:
                raise BusinessLogicError(f"Provider {request.provider} is not available")
            
            if request.amount < provider_info.min_amount or request.amount > provider_info.max_amount:
                raise ValidationException(f"Amount must be between {provider_info.min_amount} and {provider_info.max_amount}")
            
            # Calculate fees
            fee_calculation = await self._calculate_transaction_fees(
                request.provider, request.amount, request.currency, TransactionType.SEND
            )
            
            # Generate transaction ID
            transaction_id = self._generate_transaction_id()
            
            # Create transaction data
            transaction_data = MobileMoneyTransactionCreate(
                user_id=current_user.id,
                provider=request.provider,
                transaction_type=TransactionType.SEND,
                amount=request.amount,
                currency=request.currency,
                recipient_phone=request.recipient_phone,
                reference=request.reference,
                description=request.description
            )
            
            # Save transaction to database (mock implementation)
            transaction = await self._save_transaction_to_db(transaction_id, transaction_data, fee_calculation, db)
            
            # Initiate provider transaction (mock implementation)
            await self._initiate_provider_transaction(transaction, db)
            
            logger.info(f"Mobile money transfer initiated: {transaction_id}")
            return transaction
            
        except (ValidationException, BusinessLogicError):
            raise
        except Exception as e:
            logger.error(f"Error sending mobile money: {e}")
            raise ValidationException(f"Mobile money transfer failed: {str(e)}")
    
    async def receive_money(self, token: str, request: MobileMoneyReceiveRequest, db: Session) -> MobileMoneyTransaction:
        """
        Receive money via mobile money.
        
        Args:
            token: Access token
            request: Receive request
            db: Database session
            
        Returns:
            MobileMoneyTransaction: Created transaction
        """
        try:
            logger.info(f"Receiving mobile money: {request.provider} - {request.amount} {request.currency}")
            
            # Get current user
            current_user = await self.auth_service.get_current_user(token, db)
            
            # Validate provider
            provider_info = await self._get_provider_info(request.provider, db)
            if not provider_info.is_active:
                raise BusinessLogicError(f"Provider {request.provider} is not available")
            
            # Calculate fees
            fee_calculation = await self._calculate_transaction_fees(
                request.provider, request.amount, request.currency, TransactionType.RECEIVE
            )
            
            # Generate transaction ID
            transaction_id = self._generate_transaction_id()
            
            # Create transaction data
            transaction_data = MobileMoneyTransactionCreate(
                user_id=current_user.id,
                provider=request.provider,
                transaction_type=TransactionType.RECEIVE,
                amount=request.amount,
                currency=request.currency,
                sender_phone=request.sender_phone,
                reference=request.reference
            )
            
            # Save transaction to database (mock implementation)
            transaction = await self._save_transaction_to_db(transaction_id, transaction_data, fee_calculation, db)
            
            # Initiate provider collection request (mock implementation)
            await self._initiate_provider_collection(transaction, db)
            
            logger.info(f"Mobile money collection initiated: {transaction_id}")
            return transaction
            
        except (ValidationException, BusinessLogicError):
            raise
        except Exception as e:
            logger.error(f"Error receiving mobile money: {e}")
            raise ValidationException(f"Mobile money collection failed: {str(e)}")
    
    async def deposit_money(self, token: str, request: MobileMoneyDepositRequest, db: Session) -> MobileMoneyTransaction:
        """
        Deposit money to mobile money account.
        
        Args:
            token: Access token
            request: Deposit request
            db: Database session
            
        Returns:
            MobileMoneyTransaction: Created transaction
        """
        try:
            logger.info(f"Depositing to mobile money: {request.provider} - {request.amount} {request.currency}")
            
            # Get current user
            current_user = await self.auth_service.get_current_user(token, db)
            
            # Validate provider
            provider_info = await self._get_provider_info(request.provider, db)
            if not provider_info.is_active:
                raise BusinessLogicError(f"Provider {request.provider} is not available")
            
            # Calculate fees
            fee_calculation = await self._calculate_transaction_fees(
                request.provider, request.amount, request.currency, TransactionType.DEPOSIT
            )
            
            # Generate transaction ID
            transaction_id = self._generate_transaction_id()
            
            # Create transaction data
            transaction_data = MobileMoneyTransactionCreate(
                user_id=current_user.id,
                provider=request.provider,
                transaction_type=TransactionType.DEPOSIT,
                amount=request.amount,
                currency=request.currency,
                recipient_phone=request.phone_number
            )
            
            # Save transaction to database (mock implementation)
            transaction = await self._save_transaction_to_db(transaction_id, transaction_data, fee_calculation, db)
            
            # Initiate provider deposit (mock implementation)
            await self._initiate_provider_deposit(transaction, db)
            
            logger.info(f"Mobile money deposit initiated: {transaction_id}")
            return transaction
            
        except (ValidationException, BusinessLogicError):
            raise
        except Exception as e:
            logger.error(f"Error depositing mobile money: {e}")
            raise ValidationException(f"Mobile money deposit failed: {str(e)}")
    
    async def get_providers(self, token: str, country: Optional[str], currency: Optional[Currency], is_active: Optional[bool], db: Session) -> List[MobileMoneyProvider_Info]:
        """
        Get available mobile money providers.
        
        Args:
            token: Access token
            country: Country filter
            currency: Currency filter
            is_active: Active status filter
            db: Database session
            
        Returns:
            List[MobileMoneyProvider_Info]: Available providers
        """
        try:
            logger.info("Getting mobile money providers")
            
            # Get current user (for authentication)
            await self.auth_service.get_current_user(token, db)
            
            # Get providers from database (mock implementation)
            providers = await self._get_providers_from_db(country, currency, is_active, db)
            
            logger.info(f"Retrieved {len(providers)} mobile money providers")
            return providers
            
        except Exception as e:
            logger.error(f"Error getting providers: {e}")
            raise
    
    async def verify_account(self, token: str, request: MobileMoneyAccountRequest, db: Session) -> MobileMoneyAccount:
        """
        Verify mobile money account.
        
        Args:
            token: Access token
            request: Account verification request
            db: Database session
            
        Returns:
            MobileMoneyAccount: Verified account
        """
        try:
            logger.info(f"Verifying mobile money account: {request.provider}")
            
            # Get current user
            current_user = await self.auth_service.get_current_user(token, db)
            
            # Validate provider
            provider_info = await self._get_provider_info(request.provider, db)
            if not provider_info.is_active:
                raise BusinessLogicError(f"Provider {request.provider} is not available")
            
            # Verify account with provider (mock implementation)
            account_info = await self._verify_account_with_provider(request, db)
            if not account_info:
                raise NotFoundError("Mobile money account not found or invalid")
            
            # Generate account ID
            account_id = self._generate_account_id()
            
            # Create account data
            account_data = MobileMoneyAccountCreate(
                user_id=current_user.id,
                provider=request.provider,
                phone_number_encrypted=self._encrypt_phone_number(request.phone_number),
                country_code=request.country_code,
                account_name=account_info.get("account_name"),
                currency=provider_info.currency
            )
            
            # Save account to database (mock implementation)
            account = await self._save_account_to_db(account_id, account_data, db)
            
            logger.info(f"Mobile money account verified: {account_id}")
            return account
            
        except (NotFoundError, BusinessLogicError):
            raise
        except Exception as e:
            logger.error(f"Error verifying account: {e}")
            raise ValidationException(f"Account verification failed: {str(e)}")
    
    async def get_transactions(self, token: str, filter_params: MobileMoneyTransactionFilter, db: Session) -> Dict[str, Any]:
        """
        Get mobile money transactions.
        
        Args:
            token: Access token
            filter_params: Filter parameters
            db: Database session
            
        Returns:
            Dict: Paginated transactions
        """
        try:
            logger.info("Getting mobile money transactions")
            
            # Get current user
            current_user = await self.auth_service.get_current_user(token, db)
            
            # Get transactions from database (mock implementation)
            transactions = await self._get_user_transactions(current_user.id, filter_params, db)
            
            logger.info(f"Retrieved {len(transactions)} mobile money transactions")
            return {
                "transactions": transactions,
                "total": len(transactions),
                "page": filter_params.page,
                "per_page": filter_params.per_page
            }
            
        except Exception as e:
            logger.error(f"Error getting transactions: {e}")
            raise
    
    async def get_transaction(self, token: str, transaction_id: str, db: Session) -> MobileMoneyTransaction:
        """
        Get a specific mobile money transaction.
        
        Args:
            token: Access token
            transaction_id: Transaction ID
            db: Database session
            
        Returns:
            MobileMoneyTransaction: Transaction details
        """
        try:
            logger.info(f"Getting mobile money transaction: {transaction_id}")
            
            # Get current user
            current_user = await self.auth_service.get_current_user(token, db)
            
            # Get transaction from database (mock implementation)
            transaction = await self._get_transaction_from_db(transaction_id, current_user.id, db)
            if not transaction:
                raise NotFoundError(f"Transaction {transaction_id} not found")
            
            logger.info(f"Mobile money transaction retrieved: {transaction_id}")
            return transaction
            
        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error getting transaction: {e}")
            raise
    
    async def cancel_transaction(self, token: str, transaction_id: str, db: Session) -> Dict[str, Any]:
        """
        Cancel a mobile money transaction.
        
        Args:
            token: Access token
            transaction_id: Transaction ID
            db: Database session
            
        Returns:
            Dict: Cancellation result
        """
        try:
            logger.info(f"Cancelling mobile money transaction: {transaction_id}")
            
            # Get current user
            current_user = await self.auth_service.get_current_user(token, db)
            
            # Get transaction
            transaction = await self._get_transaction_from_db(transaction_id, current_user.id, db)
            if not transaction:
                raise NotFoundError(f"Transaction {transaction_id} not found")
            
            # Check if transaction can be cancelled
            if transaction.status not in [TransactionStatus.PENDING, TransactionStatus.PROCESSING]:
                raise BusinessLogicError(f"Transaction {transaction_id} cannot be cancelled (status: {transaction.status})")
            
            # Cancel with provider (mock implementation)
            await self._cancel_provider_transaction(transaction, db)
            
            # Update transaction status
            await self._update_transaction_status(transaction_id, TransactionStatus.CANCELLED, db)
            
            logger.info(f"Mobile money transaction cancelled: {transaction_id}")
            return {
                "transaction_id": transaction_id,
                "status": TransactionStatus.CANCELLED.value,
                "cancelled_at": datetime.utcnow().isoformat()
            }
            
        except (NotFoundError, BusinessLogicError):
            raise
        except Exception as e:
            logger.error(f"Error cancelling transaction: {e}")
            raise ValidationException(f"Transaction cancellation failed: {str(e)}")
    
    async def get_user_accounts(self, token: str, provider: Optional[MobileMoneyProvider], is_verified: Optional[bool], is_active: Optional[bool], db: Session) -> List[MobileMoneyAccount]:
        """
        Get user's mobile money accounts.
        
        Args:
            token: Access token
            provider: Provider filter
            is_verified: Verification status filter
            is_active: Active status filter
            db: Database session
            
        Returns:
            List[MobileMoneyAccount]: User accounts
        """
        try:
            logger.info("Getting user mobile money accounts")
            
            # Get current user
            current_user = await self.auth_service.get_current_user(token, db)
            
            # Get accounts from database (mock implementation)
            accounts = await self._get_user_accounts_from_db(current_user.id, provider, is_verified, is_active, db)
            
            logger.info(f"Retrieved {len(accounts)} mobile money accounts")
            return accounts
            
        except Exception as e:
            logger.error(f"Error getting user accounts: {e}")
            raise
    
    async def calculate_fees(self, token: str, provider: MobileMoneyProvider, amount: Decimal, currency: Currency, transaction_type: TransactionType, db: Session) -> MobileMoneyFeeCalculation:
        """
        Calculate mobile money transaction fees.
        
        Args:
            token: Access token
            provider: Mobile money provider
            amount: Transaction amount
            currency: Currency
            transaction_type: Transaction type
            db: Database session
            
        Returns:
            MobileMoneyFeeCalculation: Fee calculation
        """
        try:
            logger.info(f"Calculating fees: {provider} - {amount} {currency}")
            
            # Get current user (for authentication)
            await self.auth_service.get_current_user(token, db)
            
            # Calculate fees
            fee_calculation = await self._calculate_transaction_fees(provider, amount, currency, transaction_type)
            
            logger.info(f"Fees calculated: {fee_calculation.total_fee}")
            return fee_calculation
            
        except Exception as e:
            logger.error(f"Error calculating fees: {e}")
            raise
    
    async def get_transaction_stats(self, token: str, db: Session) -> MobileMoneyStats:
        """
        Get mobile money transaction statistics.
        
        Args:
            token: Access token
            db: Database session
            
        Returns:
            MobileMoneyStats: Transaction statistics
        """
        try:
            logger.info("Getting mobile money statistics")
            
            # Get current user
            current_user = await self.auth_service.get_current_user(token, db)
            
            # Get statistics from database (mock implementation)
            stats = await self._get_transaction_stats_from_db(current_user.id, db)
            
            logger.info("Mobile money statistics retrieved")
            return stats
            
        except Exception as e:
            logger.error(f"Error getting transaction stats: {e}")
            raise
    
    # Private helper methods
    def _generate_transaction_id(self) -> str:
        """Generate unique transaction ID."""
        return f"momo_{secrets.token_urlsafe(16)}"
    
    def _generate_account_id(self) -> str:
        """Generate unique account ID."""
        return f"acc_{secrets.token_urlsafe(16)}"
    
    def _encrypt_phone_number(self, phone_number: str) -> str:
        """Encrypt phone number (mock implementation)."""
        # In a real implementation, use proper encryption
        return f"encrypted_{phone_number[-4:]}" if len(phone_number) >= 4 else f"encrypted_{phone_number}"
    
    def _mask_phone_number(self, phone_number: str) -> str:
        """Mask phone number for display."""
        if len(phone_number) <= 4:
            return "*" * len(phone_number)
        return "*" * (len(phone_number) - 4) + phone_number[-4:]
    
    # Mock database operations (replace with actual database calls)
    async def _get_provider_info(self, provider: MobileMoneyProvider, db: Session) -> MobileMoneyProvider_Info:
        """Get provider information (mock implementation)."""
        # Mock provider data
        provider_data = {
            MobileMoneyProvider.MTN_MOMO: MobileMoneyProvider_Info(
                provider=MobileMoneyProvider.MTN_MOMO,
                name="MTN Mobile Money",
                country="UG",
                currency=Currency.UGX,
                logo_url="https://example.com/mtn-logo.png",
                is_active=True,
                min_amount=Decimal("1000"),
                max_amount=Decimal("5000000"),
                fee_percentage=Decimal("1.5"),
                fee_fixed=Decimal("500")
            ),
            MobileMoneyProvider.MPESA: MobileMoneyProvider_Info(
                provider=MobileMoneyProvider.MPESA,
                name="M-Pesa",
                country="KE",
                currency=Currency.KES,
                logo_url="https://example.com/mpesa-logo.png",
                is_active=True,
                min_amount=Decimal("10"),
                max_amount=Decimal("300000"),
                fee_percentage=Decimal("1.0"),
                fee_fixed=Decimal("25")
            )
        }
        
        return provider_data.get(provider, provider_data[MobileMoneyProvider.MTN_MOMO])
    
    async def _calculate_transaction_fees(self, provider: MobileMoneyProvider, amount: Decimal, currency: Currency, transaction_type: TransactionType) -> MobileMoneyFeeCalculation:
        """Calculate transaction fees (mock implementation)."""
        provider_info = await self._get_provider_info(provider, None)
        
        fee_percentage = provider_info.fee_percentage / 100
        fee_fixed = provider_info.fee_fixed
        
        percentage_fee = amount * fee_percentage
        total_fee = percentage_fee + fee_fixed
        total_amount = amount + total_fee
        
        return MobileMoneyFeeCalculation(
            amount=amount,
            currency=currency,
            provider=provider,
            fee_percentage=provider_info.fee_percentage,
            fee_fixed=fee_fixed,
            total_fee=total_fee,
            total_amount=total_amount
        )
    
    async def _save_transaction_to_db(self, transaction_id: str, transaction_data: MobileMoneyTransactionCreate, fee_calculation: MobileMoneyFeeCalculation, db: Session) -> MobileMoneyTransaction:
        """Save transaction to database (mock implementation)."""
        return MobileMoneyTransaction(
            id=transaction_id,
            user_id=transaction_data.user_id,
            provider=transaction_data.provider,
            transaction_type=transaction_data.transaction_type,
            status=TransactionStatus.PENDING,
            amount=transaction_data.amount,
            currency=transaction_data.currency,
            fee=fee_calculation.total_fee,
            total_amount=fee_calculation.total_amount,
            sender_phone=self._mask_phone_number(transaction_data.sender_phone) if transaction_data.sender_phone else None,
            recipient_phone=self._mask_phone_number(transaction_data.recipient_phone) if transaction_data.recipient_phone else None,
            reference=transaction_data.reference,
            description=transaction_data.description,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=30),
            retry_count=0
        )
    
    async def _initiate_provider_transaction(self, transaction: MobileMoneyTransaction, db: Session) -> None:
        """Initiate transaction with provider."""
        logger.info(f"Initiating provider transaction: {transaction.id}")
        
        if transaction.provider == MobileMoneyProvider.MTN_MOMO:
            try:
                # Use real MTN MOMO API for transfers
                transfer_data = {
                    "amount": float(transaction.amount),
                    "currency": transaction.currency.value,
                    "recipient_phone": transaction.recipient_phone.replace("*", ""),  # Unmask for API call
                    "external_id": transaction.id,
                    "payer_message": f"Transfer from Hoardrun - {transaction.description or 'Money transfer'}",
                    "payee_note": f"Hoardrun transfer - Ref: {transaction.reference or transaction.id}"
                }
                
                result = await self.mtn_momo_client.transfer(transfer_data)
                logger.info(f"MTN MOMO transfer initiated: {result.get('reference_id')}")
                
                # Update transaction with provider reference
                transaction.provider_reference = result.get('reference_id')
                
            except Exception as e:
                logger.error(f"MTN MOMO transfer failed: {e}")
                # Update transaction status to failed
                await self._update_transaction_status(transaction.id, TransactionStatus.FAILED, db)
                raise
        else:
            # Use mock implementation for other providers
            logger.info(f"Using mock implementation for provider: {transaction.provider}")
    
    async def _initiate_provider_collection(self, transaction: MobileMoneyTransaction, db: Session) -> None:
        """Initiate collection request with provider."""
        logger.info(f"Initiating provider collection: {transaction.id}")
        
        if transaction.provider == MobileMoneyProvider.MTN_MOMO:
            try:
                # Use real MTN MOMO API for payment requests
                payment_data = {
                    "amount": float(transaction.amount),
                    "currency": transaction.currency.value,
                    "phone_number": transaction.sender_phone.replace("*", ""),  # Unmask for API call
                    "external_id": transaction.id,
                    "payer_message": f"Payment request from Hoardrun - {transaction.description or 'Payment request'}",
                    "payee_note": f"Hoardrun payment - Ref: {transaction.reference or transaction.id}"
                }
                
                result = await self.mtn_momo_client.request_to_pay(payment_data)
                logger.info(f"MTN MOMO payment request initiated: {result.get('reference_id')}")
                
                # Update transaction with provider reference
                transaction.provider_reference = result.get('reference_id')
                
            except Exception as e:
                logger.error(f"MTN MOMO payment request failed: {e}")
                # Update transaction status to failed
                await self._update_transaction_status(transaction.id, TransactionStatus.FAILED, db)
                raise
        else:
            # Use mock implementation for other providers
            logger.info(f"Using mock implementation for provider: {transaction.provider}")
    
    async def _initiate_provider_deposit(self, transaction: MobileMoneyTransaction, db: Session) -> None:
        """Initiate deposit with provider."""
        logger.info(f"Initiating provider deposit: {transaction.id}")
        
        if transaction.provider == MobileMoneyProvider.MTN_MOMO:
            try:
                # Use real MTN MOMO API for deposits
                deposit_data = {
                    "amount": float(transaction.amount),
                    "currency": transaction.currency.value,
                    "phone_number": transaction.recipient_phone.replace("*", ""),  # Unmask for API call
                    "external_id": transaction.id,
                    "payer_message": f"Deposit to Hoardrun account",
                    "payee_note": f"Hoardrun deposit - Ref: {transaction.reference or transaction.id}"
                }
                
                result = await self.mtn_momo_client.deposit(deposit_data)
                logger.info(f"MTN MOMO deposit initiated: {result.get('reference_id')}")
                
                # Update transaction with provider reference
                transaction.provider_reference = result.get('reference_id')
                
            except Exception as e:
                logger.error(f"MTN MOMO deposit failed: {e}")
                # Update transaction status to failed
                await self._update_transaction_status(transaction.id, TransactionStatus.FAILED, db)
                raise
        else:
            # Use mock implementation for other providers
            logger.info(f"Using mock implementation for provider: {transaction.provider}")
    
    async def _verify_account_with_provider(self, request: MobileMoneyAccountRequest, db: Session) -> Optional[Dict[str, Any]]:
        """Verify account with provider."""
        if request.provider == MobileMoneyProvider.MTN_MOMO:
            try:
                # Use real MTN MOMO API for account verification
                account_info = await self.mtn_momo_client.get_account_holder_info(request.phone_number)
                
                # Check if account is active
                is_active = await self.mtn_momo_client.validate_account_holder(request.phone_number)
                
                if account_info and is_active:
                    return {
                        "account_name": account_info.get("name", "MTN MOMO User"),
                        "is_valid": True,
                        "account_status": "active"
                    }
                else:
                    return None
                    
            except Exception as e:
                logger.error(f"MTN MOMO account verification failed: {e}")
                return None
        else:
            # Mock account verification for other providers
            return {
                "account_name": "John Doe",
                "is_valid": True
            }
    
    async def _save_account_to_db(self, account_id: str, account_data: MobileMoneyAccountCreate, db: Session) -> MobileMoneyAccount:
        """Save account to database (mock implementation)."""
        return MobileMoneyAccount(
            id=account_id,
            user_id=account_data.user_id,
            provider=account_data.provider,
            phone_number=self._mask_phone_number(account_data.phone_number_encrypted),
            country_code=account_data.country_code,
            account_name=account_data.account_name,
            is_verified=True,
            is_active=True,
            currency=account_data.currency,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
    
    async def _get_providers_from_db(self, country: Optional[str], currency: Optional[Currency], is_active: Optional[bool], db: Session) -> List[MobileMoneyProvider_Info]:
        """Get providers from database (mock implementation)."""
        # Mock providers data
        all_providers = [
            MobileMoneyProvider_Info(
                provider=MobileMoneyProvider.MTN_MOMO,
                name="MTN Mobile Money",
                country="UG",
                currency=Currency.UGX,
                is_active=True,
                min_amount=Decimal("1000"),
                max_amount=Decimal("5000000"),
                fee_percentage=Decimal("1.5"),
                fee_fixed=Decimal("500")
            ),
            MobileMoneyProvider_Info(
                provider=MobileMoneyProvider.MPESA,
                name="M-Pesa",
                country="KE",
                currency=Currency.KES,
                is_active=True,
                min_amount=Decimal("10"),
                max_amount=Decimal("300000"),
                fee_percentage=Decimal("1.0"),
                fee_fixed=Decimal("25")
            ),
            MobileMoneyProvider_Info(
                provider=MobileMoneyProvider.AIRTEL_MONEY,
                name="Airtel Money",
                country="UG",
                currency=Currency.UGX,
                is_active=True,
                min_amount=Decimal("500"),
                max_amount=Decimal("2000000"),
                fee_percentage=Decimal("1.2"),
                fee_fixed=Decimal("300")
            )
        ]
        
        # Apply filters
        filtered_providers = all_providers
        if country:
            filtered_providers = [p for p in filtered_providers if p.country == country]
        if currency:
            filtered_providers = [p for p in filtered_providers if p.currency == currency]
        if is_active is not None:
            filtered_providers = [p for p in filtered_providers if p.is_active == is_active]
        
        return filtered_providers
    
    async def _get_user_transactions(self, user_id: str, filter_params: MobileMoneyTransactionFilter, db: Session) -> List[MobileMoneyTransaction]:
        """Get user transactions from database (mock implementation)."""
        # Mock transactions data
        mock_transactions = [
            MobileMoneyTransaction(
                id="momo_1",
                user_id=user_id,
                provider=MobileMoneyProvider.MTN_MOMO,
                transaction_type=TransactionType.SEND,
                status=TransactionStatus.COMPLETED,
                amount=Decimal("50000"),
                currency=Currency.UGX,
                fee=Decimal("1250"),
                total_amount=Decimal("51250"),
                recipient_phone="****5678",
                reference="REF001",
                description="Payment for services",
                created_at=datetime.utcnow() - timedelta(hours=2),
                updated_at=datetime.utcnow() - timedelta(hours=1),
                completed_at=datetime.utcnow() - timedelta(hours=1),
                retry_count=0
            ),
            MobileMoneyTransaction(
                id="momo_2",
                user_id=user_id,
                provider=MobileMoneyProvider.MPESA,
                transaction_type=TransactionType.RECEIVE,
                status=TransactionStatus.PENDING,
                amount=Decimal("25000"),
                currency=Currency.KES,
                fee=Decimal("275"),
                total_amount=Decimal("25275"),
                sender_phone="****1234",
                reference="REF002",
                created_at=datetime.utcnow() - timedelta(minutes=30),
                updated_at=datetime.utcnow() - timedelta(minutes=30),
                expires_at=datetime.utcnow() + timedelta(minutes=30),
                retry_count=0
            )
        ]
        
        # Apply filters (simplified)
        filtered_transactions = mock_transactions
        if filter_params.provider:
            filtered_transactions = [t for t in filtered_transactions if t.provider == filter_params.provider]
        if filter_params.transaction_type:
            filtered_transactions = [t for t in filtered_transactions if t.transaction_type == filter_params.transaction_type]
        if filter_params.status:
            filtered_transactions = [t for t in filtered_transactions if t.status == filter_params.status]
        
        return filtered_transactions
    
    async def _get_transaction_from_db(self, transaction_id: str, user_id: str, db: Session) -> Optional[MobileMoneyTransaction]:
        """Get transaction from database (mock implementation)."""
        if transaction_id == "momo_1":
            return MobileMoneyTransaction(
                id=transaction_id,
                user_id=user_id,
                provider=MobileMoneyProvider.MTN_MOMO,
                transaction_type=TransactionType.SEND,
                status=TransactionStatus.COMPLETED,
                amount=Decimal("50000"),
                currency=Currency.UGX,
                fee=Decimal("1250"),
                total_amount=Decimal("51250"),
                recipient_phone="****5678",
                reference="REF001",
                description="Payment for services",
                created_at=datetime.utcnow() - timedelta(hours=2),
                updated_at=datetime.utcnow() - timedelta(hours=1),
                completed_at=datetime.utcnow() - timedelta(hours=1),
                retry_count=0
            )
        return None
    
    async def _cancel_provider_transaction(self, transaction: MobileMoneyTransaction, db: Session) -> None:
        """Cancel transaction with provider (mock implementation)."""
        logger.info(f"Cancelling provider transaction: {transaction.id}")
        # Mock provider API call
        pass
    
    async def _update_transaction_status(self, transaction_id: str, status: TransactionStatus, db: Session) -> None:
        """Update transaction status in database (mock implementation)."""
        logger.info(f"Updating transaction status: {transaction_id} -> {status}")
        pass
    
    async def _get_user_accounts_from_db(self, user_id: str, provider: Optional[MobileMoneyProvider], is_verified: Optional[bool], is_active: Optional[bool], db: Session) -> List[MobileMoneyAccount]:
        """Get user accounts from database (mock implementation)."""
        # Mock accounts data
        mock_accounts = [
            MobileMoneyAccount(
                id="acc_1",
                user_id=user_id,
                provider=MobileMoneyProvider.MTN_MOMO,
                phone_number="****5678",
                country_code="UG",
                account_name="John Doe",
                is_verified=True,
                is_active=True,
                balance=Decimal("150000"),
                currency=Currency.UGX,
                created_at=datetime.utcnow() - timedelta(days=30),
                updated_at=datetime.utcnow() - timedelta(days=1),
                last_used_at=datetime.utcnow() - timedelta(hours=2)
            ),
            MobileMoneyAccount(
                id="acc_2",
                user_id=user_id,
                provider=MobileMoneyProvider.MPESA,
                phone_number="****1234",
                country_code="KE",
                account_name="John Doe",
                is_verified=True,
                is_active=True,
                balance=Decimal("75000"),
                currency=Currency.KES,
                created_at=datetime.utcnow() - timedelta(days=15),
                updated_at=datetime.utcnow() - timedelta(days=2),
                last_used_at=datetime.utcnow() - timedelta(hours=6)
            )
        ]
        
        # Apply filters
        filtered_accounts = mock_accounts
        if provider:
            filtered_accounts = [a for a in filtered_accounts if a.provider == provider]
        if is_verified is not None:
            filtered_accounts = [a for a in filtered_accounts if a.is_verified == is_verified]
        if is_active is not None:
            filtered_accounts = [a for a in filtered_accounts if a.is_active == is_active]
        
        return filtered_accounts
    
    async def _get_transaction_stats_from_db(self, user_id: str, db: Session) -> MobileMoneyStats:
        """Get transaction statistics from database (mock implementation)."""
        return MobileMoneyStats(
            total_transactions=25,
            successful_transactions=22,
            failed_transactions=2,
            pending_transactions=1,
            total_volume=Decimal("2500000"),
            total_fees=Decimal("37500"),
            by_provider={
                "mtn_momo": 15,
                "mpesa": 8,
                "airtel_money": 2
            },
            by_type={
                "send": 18,
                "receive": 5,
                "deposit": 2
            },
            by_currency={
                "UGX": Decimal("1800000"),
                "KES": Decimal("700000")
            },
            success_rate=88.0
        )
