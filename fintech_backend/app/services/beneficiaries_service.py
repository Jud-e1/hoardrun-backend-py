"""
Beneficiaries service for managing payment recipients.
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from ..models.beneficiaries import (
    BeneficiaryCreateRequest, BeneficiaryUpdateRequest, BeneficiaryProfile,
    BeneficiarySearchRequest, BeneficiaryType, BeneficiaryStatus,
    BeneficiaryCreate, BeneficiaryUpdate, BeneficiaryStats
)
from ..services.auth_service import AuthService
from ..core.exceptions import (
    ValidationException, AuthenticationException, NotFoundError
)
from ..config.settings import get_settings
from ..config.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class BeneficiariesService:
    """Beneficiaries service for managing payment recipients."""
    
    def __init__(self):
        self.auth_service = AuthService()
    
    async def get_beneficiaries(self, token: str, search_request: BeneficiarySearchRequest, db: Session) -> Dict[str, Any]:
        """
        Get user's beneficiaries with filtering and pagination.
        
        Args:
            token: Access token
            search_request: Search and filter parameters
            db: Database session
            
        Returns:
            Dict: Paginated beneficiaries list
        """
        try:
            logger.info("Getting beneficiaries list")
            
            # Get current user
            current_user = await self.auth_service.get_current_user(token, db)
            
            # Get beneficiaries from database (mock implementation)
            beneficiaries = await self._get_user_beneficiaries(
                current_user.id, search_request, db
            )
            
            logger.info(f"Retrieved {len(beneficiaries)} beneficiaries for user {current_user.id}")
            return {
                "beneficiaries": beneficiaries,
                "total": len(beneficiaries),
                "page": search_request.page,
                "per_page": search_request.per_page
            }
            
        except Exception as e:
            logger.error(f"Error getting beneficiaries: {e}")
            raise
    
    async def create_beneficiary(self, token: str, request: BeneficiaryCreateRequest, db: Session) -> BeneficiaryProfile:
        """
        Create a new beneficiary.
        
        Args:
            token: Access token
            request: Beneficiary creation request
            db: Database session
            
        Returns:
            BeneficiaryProfile: Created beneficiary
        """
        try:
            logger.info(f"Creating beneficiary: {request.name}")
            
            # Get current user
            current_user = await self.auth_service.get_current_user(token, db)
            
            # Generate beneficiary ID
            beneficiary_id = self._generate_beneficiary_id()
            
            # Create beneficiary data
            beneficiary_data = BeneficiaryCreate(
                user_id=current_user.id,
                name=request.name,
                email=request.email,
                phone_number=request.phone_number,
                type=request.type,
                status=BeneficiaryStatus.ACTIVE,
                bank_name=request.bank_name,
                account_number_encrypted=self._encrypt_sensitive_data(request.account_number) if request.account_number else None,
                routing_number=request.routing_number,
                swift_code=request.swift_code,
                mobile_provider=request.mobile_provider,
                mobile_account_encrypted=self._encrypt_sensitive_data(request.mobile_account) if request.mobile_account else None,
                card_number_encrypted=self._encrypt_sensitive_data(request.card_number) if request.card_number else None,
                card_type=request.card_type,
                wallet_address_encrypted=self._encrypt_sensitive_data(request.wallet_address) if request.wallet_address else None,
                crypto_currency=request.crypto_currency,
                country=request.country,
                currency=request.currency,
                notes=request.notes
            )
            
            # Save to database (mock implementation)
            beneficiary = await self._save_beneficiary_to_db(beneficiary_id, beneficiary_data, db)
            
            logger.info(f"Beneficiary created successfully: {beneficiary_id}")
            return beneficiary
            
        except Exception as e:
            logger.error(f"Error creating beneficiary: {e}")
            raise ValidationException(f"Beneficiary creation failed: {str(e)}")
    
    async def get_beneficiary(self, token: str, beneficiary_id: str, db: Session) -> BeneficiaryProfile:
        """
        Get a specific beneficiary by ID.
        
        Args:
            token: Access token
            beneficiary_id: Beneficiary ID
            db: Database session
            
        Returns:
            BeneficiaryProfile: Beneficiary information
        """
        try:
            logger.info(f"Getting beneficiary: {beneficiary_id}")
            
            # Get current user
            current_user = await self.auth_service.get_current_user(token, db)
            
            # Get beneficiary from database (mock implementation)
            beneficiary = await self._get_beneficiary_from_db(beneficiary_id, current_user.id, db)
            if not beneficiary:
                raise NotFoundError(f"Beneficiary {beneficiary_id} not found")
            
            logger.info(f"Beneficiary retrieved: {beneficiary_id}")
            return beneficiary
            
        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error getting beneficiary: {e}")
            raise
    
    async def update_beneficiary(self, token: str, beneficiary_id: str, request: BeneficiaryUpdateRequest, db: Session) -> BeneficiaryProfile:
        """
        Update a beneficiary.
        
        Args:
            token: Access token
            beneficiary_id: Beneficiary ID
            request: Update request
            db: Database session
            
        Returns:
            BeneficiaryProfile: Updated beneficiary
        """
        try:
            logger.info(f"Updating beneficiary: {beneficiary_id}")
            
            # Get current user
            current_user = await self.auth_service.get_current_user(token, db)
            
            # Check if beneficiary exists and belongs to user
            existing_beneficiary = await self._get_beneficiary_from_db(beneficiary_id, current_user.id, db)
            if not existing_beneficiary:
                raise NotFoundError(f"Beneficiary {beneficiary_id} not found")
            
            # Create update data
            update_data = BeneficiaryUpdate(
                name=request.name,
                email=request.email,
                phone_number=request.phone_number,
                status=request.status,
                bank_name=request.bank_name,
                account_number_encrypted=self._encrypt_sensitive_data(request.account_number) if request.account_number else None,
                routing_number=request.routing_number,
                swift_code=request.swift_code,
                mobile_provider=request.mobile_provider,
                mobile_account_encrypted=self._encrypt_sensitive_data(request.mobile_account) if request.mobile_account else None,
                card_number_encrypted=self._encrypt_sensitive_data(request.card_number) if request.card_number else None,
                card_type=request.card_type,
                wallet_address_encrypted=self._encrypt_sensitive_data(request.wallet_address) if request.wallet_address else None,
                crypto_currency=request.crypto_currency,
                country=request.country,
                currency=request.currency,
                notes=request.notes,
                updated_at=datetime.utcnow()
            )
            
            # Update in database (mock implementation)
            updated_beneficiary = await self._update_beneficiary_in_db(beneficiary_id, update_data, db)
            
            logger.info(f"Beneficiary updated: {beneficiary_id}")
            return updated_beneficiary
            
        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error updating beneficiary: {e}")
            raise ValidationException(f"Beneficiary update failed: {str(e)}")
    
    async def delete_beneficiary(self, token: str, beneficiary_id: str, db: Session) -> Dict[str, Any]:
        """
        Delete a beneficiary.
        
        Args:
            token: Access token
            beneficiary_id: Beneficiary ID
            db: Database session
            
        Returns:
            Dict: Deletion result
        """
        try:
            logger.info(f"Deleting beneficiary: {beneficiary_id}")
            
            # Get current user
            current_user = await self.auth_service.get_current_user(token, db)
            
            # Check if beneficiary exists and belongs to user
            existing_beneficiary = await self._get_beneficiary_from_db(beneficiary_id, current_user.id, db)
            if not existing_beneficiary:
                raise NotFoundError(f"Beneficiary {beneficiary_id} not found")
            
            # Delete from database (mock implementation)
            await self._delete_beneficiary_from_db(beneficiary_id, db)
            
            logger.info(f"Beneficiary deleted: {beneficiary_id}")
            return {
                "deleted": True,
                "beneficiary_id": beneficiary_id,
                "deleted_at": datetime.utcnow().isoformat()
            }
            
        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error deleting beneficiary: {e}")
            raise ValidationException(f"Beneficiary deletion failed: {str(e)}")
    
    async def get_recent_beneficiaries(self, token: str, limit: int, db: Session) -> List[BeneficiaryProfile]:
        """
        Get recently used beneficiaries.
        
        Args:
            token: Access token
            limit: Number of beneficiaries to return
            db: Database session
            
        Returns:
            List[BeneficiaryProfile]: Recent beneficiaries
        """
        try:
            logger.info("Getting recent beneficiaries")
            
            # Get current user
            current_user = await self.auth_service.get_current_user(token, db)
            
            # Get recent beneficiaries from database (mock implementation)
            beneficiaries = await self._get_recent_beneficiaries_from_db(current_user.id, limit, db)
            
            logger.info(f"Retrieved {len(beneficiaries)} recent beneficiaries")
            return beneficiaries
            
        except Exception as e:
            logger.error(f"Error getting recent beneficiaries: {e}")
            raise
    
    async def toggle_favorite(self, token: str, beneficiary_id: str, is_favorite: bool, db: Session) -> Dict[str, Any]:
        """
        Toggle beneficiary favorite status.
        
        Args:
            token: Access token
            beneficiary_id: Beneficiary ID
            is_favorite: Favorite status
            db: Database session
            
        Returns:
            Dict: Toggle result
        """
        try:
            logger.info(f"Toggling favorite status for beneficiary: {beneficiary_id}")
            
            # Get current user
            current_user = await self.auth_service.get_current_user(token, db)
            
            # Check if beneficiary exists and belongs to user
            existing_beneficiary = await self._get_beneficiary_from_db(beneficiary_id, current_user.id, db)
            if not existing_beneficiary:
                raise NotFoundError(f"Beneficiary {beneficiary_id} not found")
            
            # Update favorite status (mock implementation)
            await self._update_favorite_status(beneficiary_id, is_favorite, db)
            
            logger.info(f"Favorite status updated for beneficiary: {beneficiary_id}")
            return {
                "beneficiary_id": beneficiary_id,
                "is_favorite": is_favorite,
                "updated_at": datetime.utcnow().isoformat()
            }
            
        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error toggling favorite: {e}")
            raise ValidationException(f"Favorite toggle failed: {str(e)}")
    
    async def verify_beneficiary(self, token: str, beneficiary_id: str, verification_method: str, verification_data: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """
        Verify a beneficiary.
        
        Args:
            token: Access token
            beneficiary_id: Beneficiary ID
            verification_method: Verification method
            verification_data: Verification data
            db: Database session
            
        Returns:
            Dict: Verification result
        """
        try:
            logger.info(f"Verifying beneficiary: {beneficiary_id}")
            
            # Get current user
            current_user = await self.auth_service.get_current_user(token, db)
            
            # Check if beneficiary exists and belongs to user
            existing_beneficiary = await self._get_beneficiary_from_db(beneficiary_id, current_user.id, db)
            if not existing_beneficiary:
                raise NotFoundError(f"Beneficiary {beneficiary_id} not found")
            
            # Perform verification (mock implementation)
            verification_result = await self._perform_beneficiary_verification(
                beneficiary_id, verification_method, verification_data, db
            )
            
            logger.info(f"Beneficiary verification initiated: {beneficiary_id}")
            return verification_result
            
        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error verifying beneficiary: {e}")
            raise ValidationException(f"Beneficiary verification failed: {str(e)}")
    
    async def get_beneficiaries_stats(self, token: str, db: Session) -> BeneficiaryStats:
        """
        Get beneficiaries statistics.
        
        Args:
            token: Access token
            db: Database session
            
        Returns:
            BeneficiaryStats: Statistics
        """
        try:
            logger.info("Getting beneficiaries statistics")
            
            # Get current user
            current_user = await self.auth_service.get_current_user(token, db)
            
            # Get statistics from database (mock implementation)
            stats = await self._get_beneficiaries_stats_from_db(current_user.id, db)
            
            logger.info("Beneficiaries statistics retrieved")
            return stats
            
        except Exception as e:
            logger.error(f"Error getting beneficiaries stats: {e}")
            raise
    
    # Private helper methods
    def _generate_beneficiary_id(self) -> str:
        """Generate unique beneficiary ID."""
        return f"ben_{secrets.token_urlsafe(16)}"
    
    def _encrypt_sensitive_data(self, data: Optional[str]) -> Optional[str]:
        """Encrypt sensitive data (mock implementation)."""
        if not data:
            return None
        # In a real implementation, use proper encryption
        return f"encrypted_{data[-4:]}" if len(data) >= 4 else f"encrypted_{data}"
    
    def _mask_sensitive_data(self, data: Optional[str]) -> Optional[str]:
        """Mask sensitive data for display."""
        if not data:
            return None
        if len(data) <= 4:
            return "*" * len(data)
        return "*" * (len(data) - 4) + data[-4:]
    
    # Mock database operations (replace with actual database calls)
    async def _get_user_beneficiaries(self, user_id: str, search_request: BeneficiarySearchRequest, db: Session) -> List[BeneficiaryProfile]:
        """Get user beneficiaries from database (mock implementation)."""
        # Mock beneficiaries data
        mock_beneficiaries = [
            BeneficiaryProfile(
                id="ben_1",
                user_id=user_id,
                name="John Doe",
                email="john@example.com",
                phone_number="+1234567890",
                type=BeneficiaryType.BANK_ACCOUNT,
                status=BeneficiaryStatus.ACTIVE,
                bank_name="Example Bank",
                account_number="****1234",
                routing_number="123456789",
                country="US",
                currency="USD",
                is_verified=True,
                is_favorite=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            ),
            BeneficiaryProfile(
                id="ben_2",
                user_id=user_id,
                name="Jane Smith",
                email="jane@example.com",
                phone_number="+1234567891",
                type=BeneficiaryType.MOBILE_MONEY,
                status=BeneficiaryStatus.ACTIVE,
                mobile_provider="MTN",
                mobile_account="****5678",
                country="UG",
                currency="UGX",
                is_verified=False,
                is_favorite=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        ]
        
        # Apply filters (simplified)
        filtered_beneficiaries = mock_beneficiaries
        if search_request.type:
            filtered_beneficiaries = [b for b in filtered_beneficiaries if b.type == search_request.type]
        if search_request.status:
            filtered_beneficiaries = [b for b in filtered_beneficiaries if b.status == search_request.status]
        if search_request.is_favorite is not None:
            filtered_beneficiaries = [b for b in filtered_beneficiaries if b.is_favorite == search_request.is_favorite]
        
        return filtered_beneficiaries
    
    async def _save_beneficiary_to_db(self, beneficiary_id: str, beneficiary_data: BeneficiaryCreate, db: Session) -> BeneficiaryProfile:
        """Save beneficiary to database (mock implementation)."""
        return BeneficiaryProfile(
            id=beneficiary_id,
            user_id=beneficiary_data.user_id,
            name=beneficiary_data.name,
            email=beneficiary_data.email,
            phone_number=beneficiary_data.phone_number,
            type=beneficiary_data.type,
            status=beneficiary_data.status,
            bank_name=beneficiary_data.bank_name,
            account_number=self._mask_sensitive_data(beneficiary_data.account_number_encrypted),
            routing_number=beneficiary_data.routing_number,
            swift_code=beneficiary_data.swift_code,
            mobile_provider=beneficiary_data.mobile_provider,
            mobile_account=self._mask_sensitive_data(beneficiary_data.mobile_account_encrypted),
            card_number=self._mask_sensitive_data(beneficiary_data.card_number_encrypted),
            card_type=beneficiary_data.card_type,
            wallet_address=self._mask_sensitive_data(beneficiary_data.wallet_address_encrypted),
            crypto_currency=beneficiary_data.crypto_currency,
            country=beneficiary_data.country,
            currency=beneficiary_data.currency,
            notes=beneficiary_data.notes,
            is_verified=beneficiary_data.is_verified,
            is_favorite=beneficiary_data.is_favorite,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
    
    async def _get_beneficiary_from_db(self, beneficiary_id: str, user_id: str, db: Session) -> Optional[BeneficiaryProfile]:
        """Get beneficiary from database (mock implementation)."""
        if beneficiary_id == "ben_1":
            return BeneficiaryProfile(
                id=beneficiary_id,
                user_id=user_id,
                name="John Doe",
                email="john@example.com",
                phone_number="+1234567890",
                type=BeneficiaryType.BANK_ACCOUNT,
                status=BeneficiaryStatus.ACTIVE,
                bank_name="Example Bank",
                account_number="****1234",
                routing_number="123456789",
                country="US",
                currency="USD",
                is_verified=True,
                is_favorite=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        return None
    
    async def _update_beneficiary_in_db(self, beneficiary_id: str, update_data: BeneficiaryUpdate, db: Session) -> BeneficiaryProfile:
        """Update beneficiary in database (mock implementation)."""
        # Get existing beneficiary and apply updates
        existing = await self._get_beneficiary_from_db(beneficiary_id, "user_1", db)
        if existing:
            # Apply updates
            update_dict = update_data.dict(exclude_unset=True)
            updated_beneficiary = existing.copy(update=update_dict)
            return updated_beneficiary
        raise NotFoundError(f"Beneficiary {beneficiary_id} not found")
    
    async def _delete_beneficiary_from_db(self, beneficiary_id: str, db: Session) -> None:
        """Delete beneficiary from database (mock implementation)."""
        logger.info(f"Deleting beneficiary from database: {beneficiary_id}")
        pass
    
    async def _get_recent_beneficiaries_from_db(self, user_id: str, limit: int, db: Session) -> List[BeneficiaryProfile]:
        """Get recent beneficiaries from database (mock implementation)."""
        # Return mock recent beneficiaries
        return await self._get_user_beneficiaries(user_id, BeneficiarySearchRequest(page=1, per_page=limit), db)
    
    async def _update_favorite_status(self, beneficiary_id: str, is_favorite: bool, db: Session) -> None:
        """Update favorite status in database (mock implementation)."""
        logger.info(f"Updating favorite status for {beneficiary_id}: {is_favorite}")
        pass
    
    async def _perform_beneficiary_verification(self, beneficiary_id: str, method: str, data: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """Perform beneficiary verification (mock implementation)."""
        return {
            "beneficiary_id": beneficiary_id,
            "verification_method": method,
            "status": "initiated",
            "verification_id": f"ver_{secrets.token_urlsafe(8)}",
            "initiated_at": datetime.utcnow().isoformat()
        }
    
    async def _get_beneficiaries_stats_from_db(self, user_id: str, db: Session) -> BeneficiaryStats:
        """Get beneficiaries statistics from database (mock implementation)."""
        return BeneficiaryStats(
            total_beneficiaries=5,
            active_beneficiaries=4,
            verified_beneficiaries=3,
            favorite_beneficiaries=2,
            by_type={
                "bank_account": 2,
                "mobile_money": 2,
                "card": 1,
                "crypto_wallet": 0
            },
            by_country={
                "US": 2,
                "UG": 2,
                "KE": 1
            },
            recent_additions=2
        )
