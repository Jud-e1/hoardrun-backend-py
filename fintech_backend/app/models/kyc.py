"""
KYC (Know Your Customer) Models
Handles data models for KYC verification, document management, and compliance tracking.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator
from ..models.base import BaseResponse

class KYCStatus(str, Enum):
    """KYC verification status"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    SUSPENDED = "suspended"

class DocumentType(str, Enum):
    """Types of KYC documents"""
    NATIONAL_ID = "national_id"
    PASSPORT = "passport"
    DRIVERS_LICENSE = "drivers_license"
    BIRTH_CERTIFICATE = "birth_certificate"
    UTILITY_BILL = "utility_bill"
    BANK_STATEMENT = "bank_statement"
    PROOF_OF_ADDRESS = "proof_of_address"
    PROOF_OF_INCOME = "proof_of_income"
    BUSINESS_REGISTRATION = "business_registration"
    TAX_CERTIFICATE = "tax_certificate"

class DocumentStatus(str, Enum):
    """Document verification status"""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    VERIFIED = "verified"
    REJECTED = "rejected"
    EXPIRED = "expired"

class VerificationLevel(str, Enum):
    """KYC verification levels"""
    BASIC = "basic"          # Basic information only
    STANDARD = "standard"    # ID verification required
    ENHANCED = "enhanced"    # Full KYC with address verification
    PREMIUM = "premium"      # Enhanced KYC with income verification

class RiskLevel(str, Enum):
    """Risk assessment levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"

class KYCDocumentUploadRequest(BaseModel):
    """Request model for uploading KYC documents"""
    document_type: DocumentType = Field(..., description="Type of document being uploaded")
    file_name: str = Field(..., min_length=1, max_length=255, description="Original filename")
    file_size: int = Field(..., gt=0, le=10*1024*1024, description="File size in bytes (max 10MB)")
    mime_type: str = Field(..., description="MIME type of the file")
    description: Optional[str] = Field(None, max_length=500, description="Optional description")
    
    @validator('mime_type')
    def validate_mime_type(cls, v):
        allowed_types = [
            'image/jpeg', 'image/png', 'image/gif', 'image/webp',
            'application/pdf', 'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        ]
        if v not in allowed_types:
            raise ValueError(f'Unsupported file type. Allowed types: {", ".join(allowed_types)}')
        return v
    
    @validator('file_name')
    def validate_file_name(cls, v):
        # Basic filename validation
        if not v or v.strip() == '':
            raise ValueError('Filename cannot be empty')
        # Check for dangerous characters
        dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/']
        if any(char in v for char in dangerous_chars):
            raise ValueError('Filename contains invalid characters')
        return v.strip()

class KYCDocumentProfile(BaseModel):
    """Profile model for KYC documents"""
    id: str = Field(..., description="Document ID")
    document_type: DocumentType = Field(..., description="Type of document")
    file_name: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    mime_type: str = Field(..., description="MIME type")
    status: DocumentStatus = Field(..., description="Document verification status")
    upload_date: datetime = Field(..., description="Upload timestamp")
    verified_date: Optional[datetime] = Field(None, description="Verification timestamp")
    expiry_date: Optional[datetime] = Field(None, description="Document expiry date")
    rejection_reason: Optional[str] = Field(None, description="Reason for rejection if applicable")
    description: Optional[str] = Field(None, description="Document description")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class PersonalInformation(BaseModel):
    """Personal information for KYC"""
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    date_of_birth: str = Field(..., description="Date of birth in YYYY-MM-DD format")
    nationality: str = Field(..., min_length=2, max_length=3, description="Country code (ISO 2 or 3 letter)")
    gender: Optional[str] = Field(None, pattern="^(male|female|other)$")
    marital_status: Optional[str] = Field(None, pattern="^(single|married|divorced|widowed)$")
    
    @validator('date_of_birth')
    def validate_date_of_birth(cls, v):
        try:
            birth_date = datetime.strptime(v, '%Y-%m-%d')
            # Check if person is at least 18 years old
            today = datetime.now()
            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
            if age < 18:
                raise ValueError('Must be at least 18 years old')
            if age > 120:
                raise ValueError('Invalid date of birth')
            return v
        except ValueError as e:
            if "Must be at least" in str(e) or "Invalid date" in str(e):
                raise e
            raise ValueError('Date of birth must be in YYYY-MM-DD format')

class AddressInformation(BaseModel):
    """Address information for KYC"""
    street_address: str = Field(..., min_length=5, max_length=200)
    city: str = Field(..., min_length=2, max_length=100)
    state_province: Optional[str] = Field(None, max_length=100)
    postal_code: str = Field(..., min_length=3, max_length=20)
    country: str = Field(..., min_length=2, max_length=3, description="Country code (ISO 2 or 3 letter)")
    address_type: str = Field(default="residential", pattern="^(residential|business|mailing)$")

class EmploymentInformation(BaseModel):
    """Employment information for KYC"""
    employment_status: str = Field(..., pattern="^(employed|self_employed|unemployed|student|retired)$")
    employer_name: Optional[str] = Field(None, max_length=200)
    job_title: Optional[str] = Field(None, max_length=100)
    industry: Optional[str] = Field(None, max_length=100)
    monthly_income: Optional[float] = Field(None, ge=0, description="Monthly income in USD")
    income_source: Optional[str] = Field(None, max_length=200)

class KYCUpdateRequest(BaseModel):
    """Request model for updating KYC information"""
    personal_info: Optional[PersonalInformation] = Field(None, description="Personal information")
    address_info: Optional[AddressInformation] = Field(None, description="Address information")
    employment_info: Optional[EmploymentInformation] = Field(None, description="Employment information")
    phone_number: Optional[str] = Field(None, pattern=r'^\+\d{10,15}$', description="Phone number with country code")
    
class FaceVerificationRequest(BaseModel):
    """Request model for face verification"""
    image_data: str = Field(..., description="Base64 encoded image data")
    image_format: str = Field(..., pattern="^(jpeg|jpg|png)$", description="Image format")
    verification_type: str = Field(default="liveness", pattern="^(liveness|document_match)$")
    
    @validator('image_data')
    def validate_image_data(cls, v):
        # Basic validation for base64 data
        if not v or len(v) < 100:
            raise ValueError('Invalid image data')
        # Check if it's valid base64 (basic check)
        import base64
        try:
            base64.b64decode(v)
        except Exception:
            raise ValueError('Invalid base64 image data')
        return v

class KYCStatusResponse(BaseModel):
    """Response model for KYC status"""
    user_id: str = Field(..., description="User ID")
    overall_status: KYCStatus = Field(..., description="Overall KYC status")
    verification_level: VerificationLevel = Field(..., description="Current verification level")
    risk_level: RiskLevel = Field(..., description="Risk assessment level")
    completion_percentage: float = Field(..., ge=0, le=100, description="KYC completion percentage")
    required_documents: List[DocumentType] = Field(..., description="Required documents for current level")
    submitted_documents: List[KYCDocumentProfile] = Field(..., description="Submitted documents")
    personal_info_complete: bool = Field(..., description="Personal information completion status")
    address_verified: bool = Field(..., description="Address verification status")
    identity_verified: bool = Field(..., description="Identity verification status")
    face_verified: bool = Field(..., description="Face verification status")
    last_updated: datetime = Field(..., description="Last update timestamp")
    next_review_date: Optional[datetime] = Field(None, description="Next review date if applicable")
    restrictions: List[str] = Field(default=[], description="Current account restrictions")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class KYCRequirementsResponse(BaseModel):
    """Response model for KYC requirements"""
    verification_level: VerificationLevel = Field(..., description="Verification level")
    required_documents: List[Dict[str, Any]] = Field(..., description="Required documents with details")
    required_information: List[str] = Field(..., description="Required information fields")
    estimated_time: str = Field(..., description="Estimated completion time")
    benefits: List[str] = Field(..., description="Benefits of this verification level")
    transaction_limits: Dict[str, Any] = Field(..., description="Transaction limits for this level")

class FaceVerificationResponse(BaseModel):
    """Response model for face verification"""
    verification_id: str = Field(..., description="Verification session ID")
    status: str = Field(..., description="Verification status")
    confidence_score: Optional[float] = Field(None, ge=0, le=1, description="Confidence score (0-1)")
    liveness_check: Optional[bool] = Field(None, description="Liveness detection result")
    document_match: Optional[bool] = Field(None, description="Document photo match result")
    message: str = Field(..., description="Verification result message")
    next_steps: List[str] = Field(default=[], description="Next steps if verification failed")

class KYCReviewRequest(BaseModel):
    """Request model for KYC review (admin use)"""
    user_id: str = Field(..., description="User ID to review")
    action: str = Field(..., pattern="^(approve|reject|request_more_info)$")
    comments: Optional[str] = Field(None, max_length=1000, description="Review comments")
    required_documents: Optional[List[DocumentType]] = Field(None, description="Additional required documents")

# Database Models
class KYCProfileDB(BaseModel):
    """Database model for KYC profile"""
    id: str
    user_id: str
    overall_status: KYCStatus
    verification_level: VerificationLevel
    risk_level: RiskLevel
    personal_info: Optional[Dict[str, Any]]
    address_info: Optional[Dict[str, Any]]
    employment_info: Optional[Dict[str, Any]]
    phone_number: Optional[str]
    documents: List[Dict[str, Any]]
    verification_history: List[Dict[str, Any]]
    face_verification_attempts: int
    last_face_verification: Optional[datetime]
    restrictions: List[str]
    created_at: datetime
    updated_at: datetime
    reviewed_at: Optional[datetime]
    reviewed_by: Optional[str]
    next_review_date: Optional[datetime]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class KYCDocumentDB(BaseModel):
    """Database model for KYC documents"""
    id: str
    user_id: str
    kyc_profile_id: str
    document_type: DocumentType
    file_name: str
    file_path: str
    file_size: int
    mime_type: str
    status: DocumentStatus
    upload_date: datetime
    verified_date: Optional[datetime]
    expiry_date: Optional[datetime]
    rejection_reason: Optional[str]
    description: Optional[str]
    metadata: Optional[Dict[str, Any]]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
