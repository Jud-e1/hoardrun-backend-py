"""
Payment Methods Service
Handles business logic for payment method management including validation, encryption, and provider integration.
"""

import uuid
import hashlib
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
import re

from app.models.payment_methods import (
    PaymentMethodCreateRequest,
    PaymentMethodUpdateRequest,
    PaymentMethodProfile,
    PaymentMethodVerificationRequest,
    PaymentMethodVerificationResponse,
    PaymentMethodType,
    PaymentMethodStatus,
    PaymentMethodDB
)
from app.core.exceptions import ValidationError, NotFoundError, ConflictError
from app.repositories.mock_repository import MockRepository

class PaymentMethodsService:
    def __init__(self):
        self.repository = MockRepository()
        # In production, this would be loaded from environment variables
        self.encryption_key = Fernet.generate_key()
        self.cipher_suite = Fernet(self.encryption_key)
        
        # Initialize mock data
        self._init_mock_data()
    
    def _init_mock_data(self):
        """Initialize mock payment methods data"""
        mock_payment_methods = [
            {
                "id": "pm_001",
                "user_id": "user_001",
                "payment_type": PaymentMethodType.BANK_ACCOUNT,
                "display_name": "Primary Checking",
                "is_default": True,
                "status": PaymentMethodStatus.VERIFIED,
                "bank_name": "Bank of Uganda",
                "account_number_encrypted": self._encrypt_data("1234567890"),
                "account_number_masked": "****7890",
                "routing_number": "123456789",
                "account_type": "checking",
                "created_at": datetime.now() - timedelta(days=30),
                "updated_at": datetime.now() - timedelta(days=5)
            },
            {
                "id": "pm_002",
                "user_id": "user_001",
                "payment_type": PaymentMethodType.CREDIT_CARD,
                "display_name": "Visa Credit Card",
                "is_default": False,
                "status": PaymentMethodStatus.VERIFIED,
                "card_number_encrypted": self._encrypt_data("4111111111111111"),
                "card_number_masked": "****1111",
                "expiry_month": 12,
                "expiry_year": 2025,
                "card_brand": "visa",
                "cardholder_name": "John Doe",
                "created_at": datetime.now() - timedelta(days=20),
                "updated_at": datetime.now() - timedelta(days=2)
            },
            {
                "id": "pm_003",
                "user_id": "user_001",
                "payment_type": PaymentMethodType.MOBILE_MONEY,
                "display_name": "MTN Mobile Money",
                "is_default": False,
                "status": PaymentMethodStatus.PENDING_VERIFICATION,
                "provider": "mtn",
                "phone_number": "+256701234567",
                "country_code": "UG",
                "created_at": datetime.now() - timedelta(days=5),
                "updated_at": datetime.now() - timedelta(days=1)
            }
        ]
        
        # Initialize the repository data directly since we can't use async in __init__
        if "payment_methods" not in self.repository.data:
            self.repository.data["payment_methods"] = {}
        
        for method in mock_payment_methods:
            self.repository.data["payment_methods"][method["id"]] = method
    
    def _encrypt_data(self, data: str) -> str:
        """Encrypt sensitive data"""
        return self.cipher_suite.encrypt(data.encode()).decode()
    
    def _decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data"""
        return self.cipher_suite.decrypt(encrypted_data.encode()).decode()
    
    def _mask_card_number(self, card_number: str) -> str:
        """Mask card number for display"""
        if len(card_number) < 4:
            return "*" * len(card_number)
        return "*" * (len(card_number) - 4) + card_number[-4:]
    
    def _mask_account_number(self, account_number: str) -> str:
        """Mask account number for display"""
        if len(account_number) < 4:
            return "*" * len(account_number)
        return "*" * (len(account_number) - 4) + account_number[-4:]
    
    def _validate_card_number(self, card_number: str) -> bool:
        """Validate card number using Luhn algorithm"""
        # Remove spaces and non-digits
        card_number = re.sub(r'\D', '', card_number)
        
        if len(card_number) < 13 or len(card_number) > 19:
            return False
        
        # Luhn algorithm
        def luhn_checksum(card_num):
            def digits_of(n):
                return [int(d) for d in str(n)]
            digits = digits_of(card_num)
            odd_digits = digits[-1::-2]
            even_digits = digits[-2::-2]
            checksum = sum(odd_digits)
            for d in even_digits:
                checksum += sum(digits_of(d*2))
            return checksum % 10
        
        return luhn_checksum(card_number) == 0
    
    def _get_card_brand(self, card_number: str) -> str:
        """Determine card brand from card number"""
        card_number = re.sub(r'\D', '', card_number)
        
        if card_number.startswith('4'):
            return 'visa'
        elif card_number.startswith(('51', '52', '53', '54', '55')):
            return 'mastercard'
        elif card_number.startswith(('34', '37')):
            return 'amex'
        elif card_number.startswith('6011'):
            return 'discover'
        else:
            return 'unknown'
    
    def _validate_payment_method_data(self, data: PaymentMethodCreateRequest) -> None:
        """Validate payment method data based on type"""
        if data.payment_type == PaymentMethodType.BANK_ACCOUNT:
            if not data.bank_details or not data.bank_details.account_number:
                raise ValidationError("Bank account number is required")
            if not data.bank_details.bank_name:
                raise ValidationError("Bank name is required")
            if len(data.bank_details.account_number) < 8:
                raise ValidationError("Account number must be at least 8 digits")
        
        elif data.payment_type in [PaymentMethodType.CREDIT_CARD, PaymentMethodType.DEBIT_CARD]:
            if not data.card_details or not data.card_details.card_number:
                raise ValidationError("Card number is required")
            if not data.card_details.expiry_month or not data.card_details.expiry_year:
                raise ValidationError("Card expiry date is required")
            if not data.card_details.cvv:
                raise ValidationError("CVV is required")
            
            # Validate card number
            if not self._validate_card_number(data.card_details.card_number):
                raise ValidationError("Invalid card number")
            
            # Validate expiry date
            current_year = datetime.now().year
            current_month = datetime.now().month
            
            if data.card_details.expiry_year < current_year:
                raise ValidationError("Card has expired")
            if (data.card_details.expiry_year == current_year and 
                data.card_details.expiry_month < current_month):
                raise ValidationError("Card has expired")
        
        elif data.payment_type == PaymentMethodType.MOBILE_MONEY:
            if not data.mobile_money_details or not data.mobile_money_details.phone_number:
                raise ValidationError("Phone number is required for mobile money")
            if not data.mobile_money_details.provider:
                raise ValidationError("Mobile money provider is required")
            
            # Validate phone number format
            phone_pattern = r'^\+\d{10,15}$'
            if not re.match(phone_pattern, data.mobile_money_details.phone_number):
                raise ValidationError("Invalid phone number format")
        
        elif data.payment_type == PaymentMethodType.CRYPTO_WALLET:
            if not data.crypto_details or not data.crypto_details.wallet_address:
                raise ValidationError("Wallet address is required")
            if not data.crypto_details.currency:
                raise ValidationError("Cryptocurrency type is required")
    
    async def get_user_payment_methods(
        self,
        user_id: str,
        payment_type: Optional[PaymentMethodType] = None,
        status: Optional[PaymentMethodStatus] = None,
        is_default: Optional[bool] = None,
        page: int = 1,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Get user's payment methods with filtering and pagination"""
        
        # Get all payment methods for user
        all_methods = []
        for method_id, method_data in self.repository.data.get("payment_methods", {}).items():
            if method_data["user_id"] == user_id:
                # Apply filters
                if payment_type and method_data["payment_type"] != payment_type:
                    continue
                if status and method_data["status"] != status:
                    continue
                if is_default is not None and method_data["is_default"] != is_default:
                    continue
                
                # Convert to profile format
                profile = self._convert_to_profile(method_data)
                all_methods.append(profile)
        
        # Sort by default first, then by created_at
        all_methods.sort(key=lambda x: (not x.is_default, x.created_at), reverse=True)
        
        # Apply pagination
        total = len(all_methods)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        items = all_methods[start_idx:end_idx]
        
        total_pages = (total + limit - 1) // limit
        
        return {
            "items": items,
            "total": total,
            "total_pages": total_pages
        }
    
    async def get_user_payment_methods_count(self, user_id: str) -> int:
        """Get count of user's payment methods"""
        count = 0
        for method_data in self.repository.data.get("payment_methods", {}).values():
            if method_data["user_id"] == user_id:
                count += 1
        return count
    
    async def get_payment_method_by_id(
        self, 
        payment_method_id: str, 
        user_id: str
    ) -> Optional[PaymentMethodProfile]:
        """Get payment method by ID for specific user"""
        method_data = self.repository.get("payment_methods", payment_method_id)
        
        if not method_data or method_data["user_id"] != user_id:
            return None
        
        return self._convert_to_profile(method_data)
    
    async def add_payment_method(
        self,
        user_id: str,
        payment_method_data: PaymentMethodCreateRequest
    ) -> PaymentMethodProfile:
        """Add a new payment method"""
        
        # Validate the payment method data
        self._validate_payment_method_data(payment_method_data)
        
        # Check for duplicates
        await self._check_duplicate_payment_method(user_id, payment_method_data)
        
        # Generate ID
        payment_method_id = f"pm_{uuid.uuid4().hex[:8]}"
        
        # Prepare data for storage
        method_data = {
            "id": payment_method_id,
            "user_id": user_id,
            "payment_type": payment_method_data.payment_type,
            "display_name": payment_method_data.display_name,
            "is_default": payment_method_data.is_default,
            "status": PaymentMethodStatus.PENDING_VERIFICATION,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        # Add type-specific data
        if payment_method_data.payment_type == PaymentMethodType.BANK_ACCOUNT:
            bank_details = payment_method_data.bank_details
            method_data.update({
                "bank_name": bank_details.bank_name,
                "account_number_encrypted": self._encrypt_data(bank_details.account_number),
                "account_number_masked": self._mask_account_number(bank_details.account_number),
                "routing_number": bank_details.routing_number,
                "account_type": bank_details.account_type,
                "swift_code": bank_details.swift_code
            })
        
        elif payment_method_data.payment_type in [PaymentMethodType.CREDIT_CARD, PaymentMethodType.DEBIT_CARD]:
            card_details = payment_method_data.card_details
            method_data.update({
                "card_number_encrypted": self._encrypt_data(card_details.card_number),
                "card_number_masked": self._mask_card_number(card_details.card_number),
                "expiry_month": card_details.expiry_month,
                "expiry_year": card_details.expiry_year,
                "cvv_encrypted": self._encrypt_data(card_details.cvv),
                "cardholder_name": card_details.cardholder_name,
                "card_brand": self._get_card_brand(card_details.card_number)
            })
        
        elif payment_method_data.payment_type == PaymentMethodType.MOBILE_MONEY:
            mm_details = payment_method_data.mobile_money_details
            method_data.update({
                "provider": mm_details.provider,
                "phone_number": mm_details.phone_number,
                "country_code": mm_details.country_code
            })
        
        elif payment_method_data.payment_type == PaymentMethodType.CRYPTO_WALLET:
            crypto_details = payment_method_data.crypto_details
            method_data.update({
                "wallet_address": crypto_details.wallet_address,
                "currency": crypto_details.currency,
                "network": crypto_details.network
            })
        
        # If this is set as default, remove default from other methods
        if payment_method_data.is_default:
            await self._remove_default_from_other_methods(user_id)
        
        # Store the payment method
        self.repository.create("payment_methods", payment_method_id, method_data)
        
        return self._convert_to_profile(method_data)
    
    async def update_payment_method(
        self,
        payment_method_id: str,
        user_id: str,
        payment_method_data: PaymentMethodUpdateRequest
    ) -> PaymentMethodProfile:
        """Update an existing payment method"""
        
        # Get existing method
        existing_data = self.repository.get("payment_methods", payment_method_id)
        if not existing_data or existing_data["user_id"] != user_id:
            raise NotFoundError("Payment method not found")
        
        # Update allowed fields
        update_data = {
            "updated_at": datetime.now()
        }
        
        if payment_method_data.display_name is not None:
            update_data["display_name"] = payment_method_data.display_name
        
        if payment_method_data.is_default is not None:
            update_data["is_default"] = payment_method_data.is_default
            
            # If setting as default, remove default from other methods
            if payment_method_data.is_default:
                await self._remove_default_from_other_methods(user_id, exclude_id=payment_method_id)
        
        # Update billing address if provided
        if payment_method_data.billing_address:
            update_data["billing_address"] = payment_method_data.billing_address.dict()
        
        # Merge with existing data
        existing_data.update(update_data)
        
        # Update in repository
        self.repository.update("payment_methods", payment_method_id, existing_data)
        
        return self._convert_to_profile(existing_data)
    
    async def remove_payment_method(self, payment_method_id: str, user_id: str) -> None:
        """Remove a payment method (soft delete)"""
        
        # Get existing method
        existing_data = self.repository.get("payment_methods", payment_method_id)
        if not existing_data or existing_data["user_id"] != user_id:
            raise NotFoundError("Payment method not found")
        
        # Soft delete
        existing_data.update({
            "status": PaymentMethodStatus.INACTIVE,
            "deleted_at": datetime.now(),
            "updated_at": datetime.now()
        })
        
        self.repository.update("payment_methods", payment_method_id, existing_data)
    
    async def verify_payment_method(
        self,
        payment_method_id: str,
        user_id: str,
        verification_data: PaymentMethodVerificationRequest
    ) -> PaymentMethodVerificationResponse:
        """Verify a payment method"""
        
        # Get existing method
        existing_data = self.repository.get("payment_methods", payment_method_id)
        if not existing_data or existing_data["user_id"] != user_id:
            raise NotFoundError("Payment method not found")
        
        payment_type = existing_data["payment_type"]
        verification_id = f"verify_{uuid.uuid4().hex[:8]}"
        
        # Mock verification process based on payment type
        if payment_type == PaymentMethodType.BANK_ACCOUNT:
            # Bank account verification via micro-deposits
            if verification_data.verification_method == "micro_deposits":
                # In real implementation, this would initiate micro-deposits
                next_steps = [
                    "Check your bank account for two small deposits within 1-2 business days",
                    "Return to verify with the deposit amounts"
                ]
                status = "pending"
                message = "Micro-deposits initiated. Please check your account."
            else:
                # Instant verification
                next_steps = []
                status = "completed"
                message = "Bank account verified successfully"
                
                # Update status
                existing_data["status"] = PaymentMethodStatus.VERIFIED
                self.repository.update("payment_methods", payment_method_id, existing_data)
        
        elif payment_type in [PaymentMethodType.CREDIT_CARD, PaymentMethodType.DEBIT_CARD]:
            # Card verification via small authorization
            next_steps = []
            status = "completed"
            message = "Card verified successfully"
            
            # Update status
            existing_data["status"] = PaymentMethodStatus.VERIFIED
            self.repository.update("payment_methods", payment_method_id, existing_data)
        
        elif payment_type == PaymentMethodType.MOBILE_MONEY:
            # Mobile money verification via SMS/USSD
            if verification_data.verification_code:
                # Verify the code (mock verification)
                if verification_data.verification_code == "123456":
                    next_steps = []
                    status = "completed"
                    message = "Mobile money account verified successfully"
                    
                    # Update status
                    existing_data["status"] = PaymentMethodStatus.VERIFIED
                    self.repository.update("payment_methods", payment_method_id, existing_data)
                else:
                    raise ValidationError("Invalid verification code")
            else:
                # Send verification code
                next_steps = [
                    "Check your phone for a verification code",
                    "Enter the code to complete verification"
                ]
                status = "pending"
                message = "Verification code sent to your phone"
        
        else:
            # Default verification for other types
            next_steps = []
            status = "completed"
            message = "Payment method verified successfully"
            
            # Update status
            existing_data["status"] = PaymentMethodStatus.VERIFIED
            self.repository.update("payment_methods", payment_method_id, existing_data)
        
        return PaymentMethodVerificationResponse(
            verification_id=verification_id,
            status=status,
            message=message,
            next_steps=next_steps
        )
    
    async def set_default_payment_method(
        self,
        payment_method_id: str,
        user_id: str
    ) -> PaymentMethodProfile:
        """Set a payment method as default"""
        
        # Get existing method
        existing_data = self.repository.get("payment_methods", payment_method_id)
        if not existing_data or existing_data["user_id"] != user_id:
            raise NotFoundError("Payment method not found")
        
        # Remove default from other methods
        await self._remove_default_from_other_methods(user_id, exclude_id=payment_method_id)
        
        # Set as default
        existing_data.update({
            "is_default": True,
            "updated_at": datetime.now()
        })
        
        self.repository.update("payment_methods", payment_method_id, existing_data)
        
        return self._convert_to_profile(existing_data)
    
    async def has_pending_transactions(self, payment_method_id: str) -> bool:
        """Check if payment method has pending transactions"""
        # Mock implementation - in real system, would check transactions table
        return False
    
    async def get_supported_payment_types(self) -> List[Dict[str, Any]]:
        """Get supported payment method types and their requirements"""
        
        return [
            {
                "type": "bank_account",
                "name": "Bank Account",
                "description": "Link your bank account for direct transfers",
                "required_fields": ["bank_name", "account_number", "routing_number"],
                "optional_fields": ["account_type", "swift_code"],
                "supported_countries": ["UG", "KE", "TZ", "GH", "NG", "ZA"],
                "verification_methods": ["micro_deposits", "instant_verification"]
            },
            {
                "type": "credit_card",
                "name": "Credit Card",
                "description": "Add your credit card for payments",
                "required_fields": ["card_number", "expiry_month", "expiry_year", "cvv", "cardholder_name"],
                "optional_fields": ["billing_address"],
                "supported_brands": ["visa", "mastercard", "amex"],
                "verification_methods": ["authorization_charge"]
            },
            {
                "type": "debit_card",
                "name": "Debit Card",
                "description": "Add your debit card for payments",
                "required_fields": ["card_number", "expiry_month", "expiry_year", "cvv", "cardholder_name"],
                "optional_fields": ["billing_address"],
                "supported_brands": ["visa", "mastercard"],
                "verification_methods": ["authorization_charge"]
            },
            {
                "type": "mobile_money",
                "name": "Mobile Money",
                "description": "Link your mobile money account",
                "required_fields": ["phone_number", "provider"],
                "optional_fields": ["country_code"],
                "supported_providers": ["mtn", "airtel", "mpesa", "tigo"],
                "supported_countries": ["UG", "KE", "TZ", "GH", "RW"],
                "verification_methods": ["sms_verification", "ussd_verification"]
            },
            {
                "type": "digital_wallet",
                "name": "Digital Wallet",
                "description": "Connect your digital wallet",
                "required_fields": ["wallet_type", "account_identifier"],
                "supported_wallets": ["paypal", "stripe", "skrill"],
                "verification_methods": ["oauth", "api_verification"]
            },
            {
                "type": "crypto_wallet",
                "name": "Crypto Wallet",
                "description": "Add your cryptocurrency wallet",
                "required_fields": ["wallet_address", "currency"],
                "optional_fields": ["network"],
                "supported_currencies": ["BTC", "ETH", "USDT", "USDC"],
                "verification_methods": ["signature_verification"]
            }
        ]
    
    async def _check_duplicate_payment_method(
        self, 
        user_id: str, 
        payment_method_data: PaymentMethodCreateRequest
    ) -> None:
        """Check for duplicate payment methods"""
        
        for method_data in self.repository.data.get("payment_methods", {}).values():
            if method_data["user_id"] != user_id:
                continue
            
            # Check for duplicates based on payment type
            if payment_method_data.payment_type == PaymentMethodType.BANK_ACCOUNT:
                if (method_data.get("payment_type") == PaymentMethodType.BANK_ACCOUNT and
                    method_data.get("account_number_encrypted") == 
                    self._encrypt_data(payment_method_data.bank_details.account_number)):
                    raise ConflictError("Bank account already exists")
            
            elif payment_method_data.payment_type in [PaymentMethodType.CREDIT_CARD, PaymentMethodType.DEBIT_CARD]:
                if (method_data.get("payment_type") in [PaymentMethodType.CREDIT_CARD, PaymentMethodType.DEBIT_CARD] and
                    method_data.get("card_number_masked") == 
                    self._mask_card_number(payment_method_data.card_details.card_number)):
                    raise ConflictError("Card already exists")
            
            elif payment_method_data.payment_type == PaymentMethodType.MOBILE_MONEY:
                if (method_data.get("payment_type") == PaymentMethodType.MOBILE_MONEY and
                    method_data.get("phone_number") == payment_method_data.mobile_money_details.phone_number):
                    raise ConflictError("Mobile money account already exists")
    
    async def _remove_default_from_other_methods(self, user_id: str, exclude_id: str = None) -> None:
        """Remove default status from other payment methods"""
        
        for method_id, method_data in self.repository.data.get("payment_methods", {}).items():
            if (method_data["user_id"] == user_id and 
                method_data.get("is_default") and 
                method_id != exclude_id):
                
                method_data["is_default"] = False
                method_data["updated_at"] = datetime.now()
                self.repository.update("payment_methods", method_id, method_data)
    
    def _convert_to_profile(self, method_data: Dict[str, Any]) -> PaymentMethodProfile:
        """Convert database record to profile format"""
        
        profile_data = {
            "id": method_data["id"],
            "payment_type": method_data["payment_type"],
            "display_name": method_data["display_name"],
            "is_default": method_data["is_default"],
            "status": method_data["status"],
            "created_at": method_data["created_at"],
            "updated_at": method_data["updated_at"]
        }
        
        # Add type-specific data
        if method_data["payment_type"] == PaymentMethodType.BANK_ACCOUNT:
            profile_data.update({
                "bank_name": method_data.get("bank_name"),
                "account_number_masked": method_data.get("account_number_masked"),
                "account_type": method_data.get("account_type"),
                "routing_number": method_data.get("routing_number")
            })
        
        elif method_data["payment_type"] in [PaymentMethodType.CREDIT_CARD, PaymentMethodType.DEBIT_CARD]:
            profile_data.update({
                "card_number_masked": method_data.get("card_number_masked"),
                "card_brand": method_data.get("card_brand"),
                "expiry_month": method_data.get("expiry_month"),
                "expiry_year": method_data.get("expiry_year"),
                "cardholder_name": method_data.get("cardholder_name")
            })
        
        elif method_data["payment_type"] == PaymentMethodType.MOBILE_MONEY:
            profile_data.update({
                "provider": method_data.get("provider"),
                "phone_number": method_data.get("phone_number"),
                "country_code": method_data.get("country_code")
            })
        
        elif method_data["payment_type"] == PaymentMethodType.CRYPTO_WALLET:
            profile_data.update({
                "wallet_address": method_data.get("wallet_address"),
                "currency": method_data.get("currency"),
                "network": method_data.get("network")
            })
        
        return PaymentMethodProfile(**profile_data)
