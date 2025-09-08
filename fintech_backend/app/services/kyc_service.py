"""
KYC (Know Your Customer) Service
Handles business logic for KYC verification, document management, and compliance tracking.
"""

import uuid
import hashlib
import base64
import os
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path

from app.models.kyc import (
    KYCDocumentUploadRequest,
    KYCUpdateRequest,
    FaceVerificationRequest,
    KYCStatusResponse,
    KYCRequirementsResponse,
    FaceVerificationResponse,
    KYCDocumentProfile,
    VerificationLevel,
    DocumentType,
    DocumentStatus,
    KYCStatus,
    RiskLevel,
    PersonalInformation,
    AddressInformation,
    EmploymentInformation
)
from app.core.exceptions import ValidationError, NotFoundError, ConflictError
from app.repositories.mock_repository import MockRepository

class KYCService:
    def __init__(self):
        self.repository = MockRepository()
        # In production, this would be a proper file storage service
        self.file_storage_path = "/tmp/kyc_documents"
        
        # Initialize mock data
        self._init_mock_data()
    
    def _init_mock_data(self):
        """Initialize mock KYC data"""
        mock_kyc_profiles = [
            {
                "id": "kyc_001",
                "user_id": "user_001",
                "overall_status": KYCStatus.IN_PROGRESS,
                "verification_level": VerificationLevel.BASIC,
                "risk_level": RiskLevel.LOW,
                "personal_info": {
                    "first_name": "John",
                    "last_name": "Doe",
                    "date_of_birth": "1990-01-15",
                    "nationality": "UG",
                    "gender": "male"
                },
                "address_info": None,
                "employment_info": None,
                "phone_number": "+256701234567",
                "documents": [],
                "verification_history": [],
                "face_verification_attempts": 0,
                "last_face_verification": None,
                "restrictions": [],
                "created_at": datetime.now() - timedelta(days=10),
                "updated_at": datetime.now() - timedelta(days=2),
                "reviewed_at": None,
                "reviewed_by": None,
                "next_review_date": None
            }
        ]
        
        mock_documents = [
            {
                "id": "doc_001",
                "user_id": "user_001",
                "kyc_profile_id": "kyc_001",
                "document_type": DocumentType.NATIONAL_ID,
                "file_name": "national_id.jpg",
                "file_path": "/tmp/kyc_documents/doc_001.jpg",
                "file_size": 1024000,
                "mime_type": "image/jpeg",
                "status": DocumentStatus.UPLOADED,
                "upload_date": datetime.now() - timedelta(days=5),
                "verified_date": None,
                "expiry_date": None,
                "rejection_reason": None,
                "description": "National ID front page",
                "metadata": {}
            }
        ]
        
        for profile in mock_kyc_profiles:
            self.repository.data.setdefault("kyc_profiles", {})[profile["id"]] = profile
        
        for document in mock_documents:
            self.repository.data.setdefault("kyc_documents", {})[document["id"]] = document
    
    def _calculate_completion_percentage(self, kyc_profile: Dict[str, Any]) -> float:
        """Calculate KYC completion percentage"""
        total_steps = 5  # personal_info, address_info, employment_info, documents, face_verification
        completed_steps = 0
        
        # Personal information
        if kyc_profile.get("personal_info"):
            completed_steps += 1
        
        # Address information
        if kyc_profile.get("address_info"):
            completed_steps += 1
        
        # Employment information
        if kyc_profile.get("employment_info"):
            completed_steps += 1
        
        # Documents
        verified_docs = [doc for doc in kyc_profile.get("documents", []) 
                        if doc.get("status") == DocumentStatus.VERIFIED]
        if verified_docs:
            completed_steps += 1
        
        # Face verification
        if kyc_profile.get("last_face_verification"):
            completed_steps += 1
        
        return (completed_steps / total_steps) * 100
    
    def _determine_verification_level(self, kyc_profile: Dict[str, Any]) -> VerificationLevel:
        """Determine appropriate verification level based on completed information"""
        has_personal = bool(kyc_profile.get("personal_info"))
        has_address = bool(kyc_profile.get("address_info"))
        has_employment = bool(kyc_profile.get("employment_info"))
        has_verified_docs = any(doc.get("status") == DocumentStatus.VERIFIED 
                               for doc in kyc_profile.get("documents", []))
        has_face_verification = bool(kyc_profile.get("last_face_verification"))
        
        if has_employment and has_verified_docs and has_face_verification and has_address:
            return VerificationLevel.PREMIUM
        elif has_address and has_verified_docs and has_face_verification:
            return VerificationLevel.ENHANCED
        elif has_verified_docs and has_personal:
            return VerificationLevel.STANDARD
        else:
            return VerificationLevel.BASIC
    
    def _assess_risk_level(self, kyc_profile: Dict[str, Any]) -> RiskLevel:
        """Assess risk level based on KYC information"""
        # Mock risk assessment logic
        risk_factors = 0
        
        # Check employment status
        employment_info = kyc_profile.get("employment_info", {})
        if employment_info.get("employment_status") == "unemployed":
            risk_factors += 1
        
        # Check income level
        monthly_income = employment_info.get("monthly_income", 0)
        if monthly_income > 10000:  # High income might indicate higher risk
            risk_factors += 1
        
        # Check document verification failures
        rejected_docs = [doc for doc in kyc_profile.get("documents", []) 
                        if doc.get("status") == DocumentStatus.REJECTED]
        if len(rejected_docs) > 2:
            risk_factors += 2
        
        # Check face verification attempts
        if kyc_profile.get("face_verification_attempts", 0) > 3:
            risk_factors += 1
        
        # Determine risk level
        if risk_factors >= 3:
            return RiskLevel.HIGH
        elif risk_factors >= 2:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def _get_required_documents(self, verification_level: VerificationLevel) -> List[DocumentType]:
        """Get required documents for verification level"""
        requirements = {
            VerificationLevel.BASIC: [],
            VerificationLevel.STANDARD: [DocumentType.NATIONAL_ID],
            VerificationLevel.ENHANCED: [
                DocumentType.NATIONAL_ID,
                DocumentType.PROOF_OF_ADDRESS
            ],
            VerificationLevel.PREMIUM: [
                DocumentType.NATIONAL_ID,
                DocumentType.PROOF_OF_ADDRESS,
                DocumentType.PROOF_OF_INCOME
            ]
        }
        return requirements.get(verification_level, [])
    
    def _save_file(self, file_content: bytes, file_path: str) -> None:
        """Save file to storage (mock implementation)"""
        # In production, this would save to cloud storage (S3, GCS, etc.)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'wb') as f:
            f.write(file_content)
    
    async def get_kyc_status(self, user_id: str) -> KYCStatusResponse:
        """Get comprehensive KYC status for user"""
        
        # Get or create KYC profile
        kyc_profile = None
        for profile_id, profile_data in self.repository.data.get("kyc_profiles", {}).items():
            if profile_data["user_id"] == user_id:
                kyc_profile = profile_data
                break
        
        if not kyc_profile:
            # Create new KYC profile
            kyc_profile = {
                "id": f"kyc_{uuid.uuid4().hex[:8]}",
                "user_id": user_id,
                "overall_status": KYCStatus.NOT_STARTED,
                "verification_level": VerificationLevel.BASIC,
                "risk_level": RiskLevel.LOW,
                "personal_info": None,
                "address_info": None,
                "employment_info": None,
                "phone_number": None,
                "documents": [],
                "verification_history": [],
                "face_verification_attempts": 0,
                "last_face_verification": None,
                "restrictions": [],
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "reviewed_at": None,
                "reviewed_by": None,
                "next_review_date": None
            }
            self.repository.create("kyc_profiles", kyc_profile["id"], kyc_profile)
        
        # Get user documents
        user_documents = []
        for doc_id, doc_data in self.repository.data.get("kyc_documents", {}).items():
            if doc_data["user_id"] == user_id:
                doc_profile = KYCDocumentProfile(
                    id=doc_data["id"],
                    document_type=doc_data["document_type"],
                    file_name=doc_data["file_name"],
                    file_size=doc_data["file_size"],
                    mime_type=doc_data["mime_type"],
                    status=doc_data["status"],
                    upload_date=doc_data["upload_date"],
                    verified_date=doc_data.get("verified_date"),
                    expiry_date=doc_data.get("expiry_date"),
                    rejection_reason=doc_data.get("rejection_reason"),
                    description=doc_data.get("description")
                )
                user_documents.append(doc_profile)
        
        # Update verification level and risk assessment
        verification_level = self._determine_verification_level(kyc_profile)
        risk_level = self._assess_risk_level(kyc_profile)
        completion_percentage = self._calculate_completion_percentage(kyc_profile)
        
        # Update profile
        kyc_profile.update({
            "verification_level": verification_level,
            "risk_level": risk_level,
            "updated_at": datetime.now()
        })
        self.repository.update("kyc_profiles", kyc_profile["id"], kyc_profile)
        
        # Get required documents
        required_documents = self._get_required_documents(verification_level)
        
        return KYCStatusResponse(
            user_id=user_id,
            overall_status=kyc_profile["overall_status"],
            verification_level=verification_level,
            risk_level=risk_level,
            completion_percentage=completion_percentage,
            required_documents=required_documents,
            submitted_documents=user_documents,
            personal_info_complete=bool(kyc_profile.get("personal_info")),
            address_verified=bool(kyc_profile.get("address_info")),
            identity_verified=any(doc.status == DocumentStatus.VERIFIED for doc in user_documents),
            face_verified=bool(kyc_profile.get("last_face_verification")),
            last_updated=kyc_profile["updated_at"],
            next_review_date=kyc_profile.get("next_review_date"),
            restrictions=kyc_profile.get("restrictions", [])
        )
    
    async def upload_document(
        self,
        user_id: str,
        upload_request: KYCDocumentUploadRequest,
        file_content: bytes
    ) -> KYCDocumentProfile:
        """Upload a KYC document"""
        
        # Check if document type already exists
        existing_docs = []
        for doc_data in self.repository.data.get("kyc_documents", {}).values():
            if (doc_data["user_id"] == user_id and 
                doc_data["document_type"] == upload_request.document_type):
                existing_docs.append(doc_data)
        
        # Allow only one document per type (unless previous was rejected)
        active_docs = [doc for doc in existing_docs 
                      if doc["status"] not in [DocumentStatus.REJECTED, DocumentStatus.EXPIRED]]
        if active_docs:
            raise ConflictError(f"Document of type {upload_request.document_type} already exists")
        
        # Generate document ID and file path
        document_id = f"doc_{uuid.uuid4().hex[:8]}"
        file_extension = upload_request.file_name.split('.')[-1] if '.' in upload_request.file_name else 'bin'
        file_path = f"{self.file_storage_path}/{document_id}.{file_extension}"
        
        # Save file
        self._save_file(file_content, file_path)
        
        # Create document record
        document_data = {
            "id": document_id,
            "user_id": user_id,
            "kyc_profile_id": f"kyc_{user_id}",  # Simplified for mock
            "document_type": upload_request.document_type,
            "file_name": upload_request.file_name,
            "file_path": file_path,
            "file_size": upload_request.file_size,
            "mime_type": upload_request.mime_type,
            "status": DocumentStatus.UPLOADED,
            "upload_date": datetime.now(),
            "verified_date": None,
            "expiry_date": None,
            "rejection_reason": None,
            "description": upload_request.description,
            "metadata": {}
        }
        
        self.repository.create("kyc_documents", document_id, document_data)
        
        # Update KYC profile status
        await self._update_kyc_status_after_document_upload(user_id)
        
        return KYCDocumentProfile(
            id=document_data["id"],
            document_type=document_data["document_type"],
            file_name=document_data["file_name"],
            file_size=document_data["file_size"],
            mime_type=document_data["mime_type"],
            status=document_data["status"],
            upload_date=document_data["upload_date"],
            verified_date=document_data.get("verified_date"),
            expiry_date=document_data.get("expiry_date"),
            rejection_reason=document_data.get("rejection_reason"),
            description=document_data.get("description")
        )
    
    async def perform_face_verification(
        self,
        user_id: str,
        verification_request: FaceVerificationRequest
    ) -> FaceVerificationResponse:
        """Perform face verification"""
        
        # Get KYC profile
        kyc_profile = None
        for profile_data in self.repository.data.get("kyc_profiles", {}).values():
            if profile_data["user_id"] == user_id:
                kyc_profile = profile_data
                break
        
        if not kyc_profile:
            raise NotFoundError("KYC profile not found")
        
        # Check verification attempts limit
        if kyc_profile.get("face_verification_attempts", 0) >= 5:
            raise ConflictError("Maximum face verification attempts exceeded")
        
        # Mock face verification logic
        verification_id = f"face_verify_{uuid.uuid4().hex[:8]}"
        
        # Simulate verification process
        import random
        success_rate = 0.8  # 80% success rate for mock
        is_successful = random.random() < success_rate
        
        if is_successful:
            confidence_score = random.uniform(0.85, 0.99)
            liveness_check = True
            document_match = True
            status = "completed"
            message = "Face verification successful"
            next_steps = []
            
            # Update KYC profile
            kyc_profile.update({
                "last_face_verification": datetime.now(),
                "face_verification_attempts": kyc_profile.get("face_verification_attempts", 0) + 1,
                "updated_at": datetime.now()
            })
            
        else:
            confidence_score = random.uniform(0.3, 0.7)
            liveness_check = random.choice([True, False])
            document_match = random.choice([True, False])
            status = "failed"
            message = "Face verification failed"
            next_steps = [
                "Ensure good lighting conditions",
                "Remove sunglasses or face coverings",
                "Look directly at the camera",
                "Try again in a few minutes"
            ]
            
            # Update attempts count
            kyc_profile.update({
                "face_verification_attempts": kyc_profile.get("face_verification_attempts", 0) + 1,
                "updated_at": datetime.now()
            })
        
        # Save updated profile
        self.repository.update("kyc_profiles", kyc_profile["id"], kyc_profile)
        
        return FaceVerificationResponse(
            verification_id=verification_id,
            status=status,
            confidence_score=confidence_score,
            liveness_check=liveness_check,
            document_match=document_match,
            message=message,
            next_steps=next_steps
        )
    
    async def update_kyc_information(
        self,
        user_id: str,
        update_request: KYCUpdateRequest
    ) -> KYCStatusResponse:
        """Update KYC information"""
        
        # Get KYC profile
        kyc_profile = None
        profile_id = None
        for pid, profile_data in self.repository.data.get("kyc_profiles", {}).items():
            if profile_data["user_id"] == user_id:
                kyc_profile = profile_data
                profile_id = pid
                break
        
        if not kyc_profile:
            raise NotFoundError("KYC profile not found")
        
        # Update information
        if update_request.personal_info:
            kyc_profile["personal_info"] = update_request.personal_info.dict()
        
        if update_request.address_info:
            kyc_profile["address_info"] = update_request.address_info.dict()
        
        if update_request.employment_info:
            kyc_profile["employment_info"] = update_request.employment_info.dict()
        
        if update_request.phone_number:
            kyc_profile["phone_number"] = update_request.phone_number
        
        # Update status and timestamp
        if kyc_profile["overall_status"] == KYCStatus.NOT_STARTED:
            kyc_profile["overall_status"] = KYCStatus.IN_PROGRESS
        
        kyc_profile["updated_at"] = datetime.now()
        
        # Save updated profile
        self.repository.update("kyc_profiles", profile_id, kyc_profile)
        
        # Return updated status
        return await self.get_kyc_status(user_id)
    
    async def get_kyc_requirements(
        self,
        user_id: str,
        verification_level: Optional[VerificationLevel] = None
    ) -> KYCRequirementsResponse:
        """Get KYC requirements for verification level"""
        
        if not verification_level:
            verification_level = VerificationLevel.STANDARD
        
        requirements_map = {
            VerificationLevel.BASIC: {
                "required_documents": [
                    {"type": "email_verification", "name": "Email Verification", "required": True},
                    {"type": "phone_verification", "name": "Phone Verification", "required": True}
                ],
                "required_information": ["email", "phone_number"],
                "estimated_time": "5 minutes",
                "benefits": [
                    "Basic account access",
                    "Limited transactions ($100/day)"
                ],
                "transaction_limits": {
                    "daily_limit": 100,
                    "monthly_limit": 1000,
                    "currency": "USD"
                }
            },
            VerificationLevel.STANDARD: {
                "required_documents": [
                    {"type": "national_id", "name": "National ID", "required": True},
                    {"type": "personal_info", "name": "Personal Information", "required": True}
                ],
                "required_information": ["first_name", "last_name", "date_of_birth", "nationality"],
                "estimated_time": "15 minutes",
                "benefits": [
                    "Increased transaction limits ($1,000/day)",
                    "Access to savings features",
                    "Mobile money integration"
                ],
                "transaction_limits": {
                    "daily_limit": 1000,
                    "monthly_limit": 10000,
                    "currency": "USD"
                }
            },
            VerificationLevel.ENHANCED: {
                "required_documents": [
                    {"type": "national_id", "name": "National ID", "required": True},
                    {"type": "proof_of_address", "name": "Proof of Address", "required": True},
                    {"type": "face_verification", "name": "Face Verification", "required": True}
                ],
                "required_information": ["personal_info", "address_info", "face_verification"],
                "estimated_time": "30 minutes",
                "benefits": [
                    "High transaction limits ($5,000/day)",
                    "Investment features",
                    "International transfers",
                    "Premium support"
                ],
                "transaction_limits": {
                    "daily_limit": 5000,
                    "monthly_limit": 50000,
                    "currency": "USD"
                }
            },
            VerificationLevel.PREMIUM: {
                "required_documents": [
                    {"type": "national_id", "name": "National ID", "required": True},
                    {"type": "proof_of_address", "name": "Proof of Address", "required": True},
                    {"type": "proof_of_income", "name": "Proof of Income", "required": True},
                    {"type": "face_verification", "name": "Face Verification", "required": True}
                ],
                "required_information": ["personal_info", "address_info", "employment_info", "face_verification"],
                "estimated_time": "45 minutes",
                "benefits": [
                    "Unlimited transaction limits",
                    "Advanced investment options",
                    "Business account features",
                    "Dedicated account manager",
                    "Priority processing"
                ],
                "transaction_limits": {
                    "daily_limit": "unlimited",
                    "monthly_limit": "unlimited",
                    "currency": "USD"
                }
            }
        }
        
        requirements = requirements_map.get(verification_level)
        if not requirements:
            raise ValidationError(f"Invalid verification level: {verification_level}")
        
        return KYCRequirementsResponse(
            verification_level=verification_level,
            required_documents=requirements["required_documents"],
            required_information=requirements["required_information"],
            estimated_time=requirements["estimated_time"],
            benefits=requirements["benefits"],
            transaction_limits=requirements["transaction_limits"]
        )
    
    async def get_user_documents(
        self,
        user_id: str,
        document_type: Optional[DocumentType] = None
    ) -> List[KYCDocumentProfile]:
        """Get user's KYC documents"""
        
        documents = []
        for doc_data in self.repository.data.get("kyc_documents", {}).values():
            if doc_data["user_id"] == user_id:
                if document_type and doc_data["document_type"] != document_type:
                    continue
                
                doc_profile = KYCDocumentProfile(
                    id=doc_data["id"],
                    document_type=doc_data["document_type"],
                    file_name=doc_data["file_name"],
                    file_size=doc_data["file_size"],
                    mime_type=doc_data["mime_type"],
                    status=doc_data["status"],
                    upload_date=doc_data["upload_date"],
                    verified_date=doc_data.get("verified_date"),
                    expiry_date=doc_data.get("expiry_date"),
                    rejection_reason=doc_data.get("rejection_reason"),
                    description=doc_data.get("description")
                )
                documents.append(doc_profile)
        
        # Sort by upload date (newest first)
        documents.sort(key=lambda x: x.upload_date, reverse=True)
        
        return documents
    
    async def delete_document(self, user_id: str, document_id: str) -> None:
        """Delete a KYC document"""
        
        document_data = self.repository.get("kyc_documents", document_id)
        if not document_data or document_data["user_id"] != user_id:
            raise NotFoundError("Document not found")
        
        if document_data["status"] == DocumentStatus.VERIFIED:
            raise ConflictError("Cannot delete verified document")
        
        # Delete file (mock)
        try:
            if os.path.exists(document_data["file_path"]):
                os.remove(document_data["file_path"])
        except Exception:
            pass  # Ignore file deletion errors in mock
        
        # Delete document record
        self.repository.delete("kyc_documents", document_id)
    
    async def submit_for_review(self, user_id: str) -> KYCStatusResponse:
        """Submit KYC for manual review"""
        
        # Get current status
        current_status = await self.get_kyc_status(user_id)
        
        # Validate completeness
        if current_status.completion_percentage < 80:
            raise ValidationError("KYC information is incomplete. Please complete all required fields.")
        
        if not current_status.identity_verified:
            raise ValidationError("Identity verification required. Please upload and verify your ID document.")
        
        # Get KYC profile
        kyc_profile = None
        profile_id = None
        for pid, profile_data in self.repository.data.get("kyc_profiles", {}).items():
            if profile_data["user_id"] == user_id:
                kyc_profile = profile_data
                profile_id = pid
                break
        
        if not kyc_profile:
            raise NotFoundError("KYC profile not found")
        
        # Update status to pending review
        kyc_profile.update({
            "overall_status": KYCStatus.PENDING_REVIEW,
            "updated_at": datetime.now(),
            "next_review_date": datetime.now() + timedelta(days=3)  # 3 business days
        })
        
        self.repository.update("kyc_profiles", profile_id, kyc_profile)
        
        # Return updated status
        return await self.get_kyc_status(user_id)
    
    async def get_verification_levels(self) -> List[Dict[str, Any]]:
        """Get available verification levels"""
        
        levels = []
        for level in VerificationLevel:
            requirements = await self.get_kyc_requirements("dummy_user", level)
            levels.append({
                "level": level.value,
                "name": level.value.title(),
                "requirements": requirements.dict()
            })
        
        return levels
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for KYC service"""
        
        # Count statistics
        total_profiles = len(self.repository.data.get("kyc_profiles", {}))
        total_documents = len(self.repository.data.get("kyc_documents", {}))
        
        # Count by status
        status_counts = {}
        for profile_data in self.repository.data.get("kyc_profiles", {}).values():
            status = profile_data["overall_status"]
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            "service": "kyc",
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "statistics": {
                "total_profiles": total_profiles,
                "total_documents": total_documents,
                "status_distribution": status_counts
            },
            "file_storage": {
                "path": self.file_storage_path,
                "accessible": os.path.exists(self.file_storage_path) or True  # Mock always accessible
            }
        }
    
    async def _update_kyc_status_after_document_upload(self, user_id: str) -> None:
        """Update KYC status after document upload"""
        
        # Get KYC profile
        kyc_profile = None
        profile_id = None
        for pid, profile_data in self.repository.data.get("kyc_profiles", {}).items():
            if profile_data["user_id"] == user_id:
                kyc_profile = profile_data
                profile_id = pid
                break
        
        if kyc_profile and kyc_profile["overall_status"] == KYCStatus.NOT_STARTED:
            kyc_profile["overall_status"] = KYCStatus.IN_PROGRESS
            kyc_profile["updated_at"] = datetime.now()
            self.repository.update("kyc_profiles", profile_id, kyc_profile)
