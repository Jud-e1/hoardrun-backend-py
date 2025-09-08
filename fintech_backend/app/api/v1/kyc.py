"""
KYC (Know Your Customer) API Routes
Handles KYC verification, document management, and compliance tracking.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.security import HTTPBearer

from app.core.auth import get_current_user
from app.models.kyc import (
    KYCDocumentUploadRequest,
    KYCUpdateRequest,
    FaceVerificationRequest,
    KYCStatusResponse,
    KYCRequirementsResponse,
    FaceVerificationResponse,
    KYCDocumentProfile,
    VerificationLevel,
    DocumentType
)
from app.models.base import BaseResponse
from app.services.kyc_service import KYCService
from app.core.exceptions import ValidationError, NotFoundError, ConflictError

router = APIRouter(prefix="/kyc", tags=["KYC"])
security = HTTPBearer()

# Initialize service
kyc_service = KYCService()

@router.post(
    "/documents",
    response_model=BaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload KYC Document",
    description="Upload a KYC document for verification"
)
async def upload_kyc_document(
    file: UploadFile = File(...),
    document_type: DocumentType = Form(...),
    description: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user)
):
    """
    Upload a KYC document for verification.
    
    Supported document types:
    - National ID
    - Passport
    - Driver's License
    - Utility Bill
    - Bank Statement
    - Proof of Address
    - Proof of Income
    - Business Registration
    - Tax Certificate
    
    File requirements:
    - Max size: 10MB
    - Formats: JPEG, PNG, PDF, DOC, DOCX
    """
    try:
        # Validate file
        if not file.filename:
            raise ValidationError("No file provided")
        
        # Read file content
        file_content = await file.read()
        file_size = len(file_content)
        
        # Create upload request
        upload_request = KYCDocumentUploadRequest(
            document_type=document_type,
            file_name=file.filename,
            file_size=file_size,
            mime_type=file.content_type or "application/octet-stream",
            description=description
        )
        
        # Upload document
        document = await kyc_service.upload_document(
            user_id=current_user["user_id"],
            upload_request=upload_request,
            file_content=file_content
        )
        
        return BaseResponse(
            success=True,
            message="Document uploaded successfully",
            data=document
        )
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}"
        )

@router.get(
    "/status",
    response_model=BaseResponse,
    summary="Get KYC Status",
    description="Get comprehensive KYC status and progress for the current user"
)
async def get_kyc_status(
    current_user: dict = Depends(get_current_user)
):
    """
    Get comprehensive KYC status including:
    - Overall verification status
    - Completion percentage
    - Required documents
    - Submitted documents
    - Verification levels
    - Account restrictions
    """
    try:
        kyc_status = await kyc_service.get_kyc_status(
            user_id=current_user["user_id"]
        )
        
        return BaseResponse(
            success=True,
            message="KYC status retrieved successfully",
            data=kyc_status
        )
        
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve KYC status: {str(e)}"
        )

@router.post(
    "/face-verification",
    response_model=BaseResponse,
    summary="Face Verification",
    description="Perform face verification for identity confirmation"
)
async def face_verification(
    verification_request: FaceVerificationRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Perform face verification for identity confirmation.
    
    Verification types:
    - Liveness detection: Verify the person is real and present
    - Document match: Compare face with uploaded ID document
    
    Requirements:
    - Clear, well-lit photo
    - Face should be clearly visible
    - No sunglasses or face coverings
    - Image format: JPEG, PNG
    """
    try:
        verification_result = await kyc_service.perform_face_verification(
            user_id=current_user["user_id"],
            verification_request=verification_request
        )
        
        return BaseResponse(
            success=True,
            message="Face verification completed",
            data=verification_result
        )
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Face verification failed: {str(e)}"
        )

@router.put(
    "/update",
    response_model=BaseResponse,
    summary="Update KYC Information",
    description="Update personal, address, and employment information for KYC"
)
async def update_kyc_information(
    update_request: KYCUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Update KYC information including:
    - Personal information (name, date of birth, nationality)
    - Address information (residential address)
    - Employment information (job, income)
    - Phone number
    
    All fields are optional - only provided fields will be updated.
    """
    try:
        updated_status = await kyc_service.update_kyc_information(
            user_id=current_user["user_id"],
            update_request=update_request
        )
        
        return BaseResponse(
            success=True,
            message="KYC information updated successfully",
            data=updated_status
        )
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update KYC information: {str(e)}"
        )

@router.get(
    "/requirements",
    response_model=BaseResponse,
    summary="Get KYC Requirements",
    description="Get KYC requirements for different verification levels"
)
async def get_kyc_requirements(
    level: Optional[VerificationLevel] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Get KYC requirements for verification levels:
    
    - Basic: Email and phone verification only
    - Standard: ID document required
    - Enhanced: ID + address verification
    - Premium: Full KYC with income verification
    
    Returns required documents, information, and benefits for each level.
    """
    try:
        requirements = await kyc_service.get_kyc_requirements(
            user_id=current_user["user_id"],
            verification_level=level
        )
        
        return BaseResponse(
            success=True,
            message="KYC requirements retrieved successfully",
            data=requirements
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve KYC requirements: {str(e)}"
        )

@router.get(
    "/documents",
    response_model=BaseResponse,
    summary="Get KYC Documents",
    description="Get list of uploaded KYC documents"
)
async def get_kyc_documents(
    document_type: Optional[DocumentType] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Get list of uploaded KYC documents with their verification status.
    
    Optionally filter by document type.
    """
    try:
        documents = await kyc_service.get_user_documents(
            user_id=current_user["user_id"],
            document_type=document_type
        )
        
        return BaseResponse(
            success=True,
            message="KYC documents retrieved successfully",
            data=documents
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve KYC documents: {str(e)}"
        )

@router.delete(
    "/documents/{document_id}",
    response_model=BaseResponse,
    summary="Delete KYC Document",
    description="Delete an uploaded KYC document"
)
async def delete_kyc_document(
    document_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete an uploaded KYC document.
    
    Note: Only documents that haven't been verified can be deleted.
    """
    try:
        await kyc_service.delete_document(
            user_id=current_user["user_id"],
            document_id=document_id
        )
        
        return BaseResponse(
            success=True,
            message="Document deleted successfully",
            data={"document_id": document_id}
        )
        
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {str(e)}"
        )

@router.post(
    "/submit-for-review",
    response_model=BaseResponse,
    summary="Submit KYC for Review",
    description="Submit completed KYC information for manual review"
)
async def submit_kyc_for_review(
    current_user: dict = Depends(get_current_user)
):
    """
    Submit completed KYC information for manual review.
    
    This will:
    - Validate all required information is provided
    - Change status to pending review
    - Notify compliance team
    - Return updated KYC status
    """
    try:
        kyc_status = await kyc_service.submit_for_review(
            user_id=current_user["user_id"]
        )
        
        return BaseResponse(
            success=True,
            message="KYC submitted for review successfully",
            data=kyc_status
        )
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit KYC for review: {str(e)}"
        )

@router.get(
    "/verification-levels",
    response_model=BaseResponse,
    summary="Get Verification Levels",
    description="Get available KYC verification levels and their benefits"
)
async def get_verification_levels():
    """
    Get available KYC verification levels and their benefits.
    
    Returns information about:
    - Available verification levels
    - Requirements for each level
    - Transaction limits
    - Benefits and features
    """
    try:
        levels = await kyc_service.get_verification_levels()
        
        return BaseResponse(
            success=True,
            message="Verification levels retrieved successfully",
            data=levels
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve verification levels: {str(e)}"
        )

@router.get(
    "/health",
    response_model=BaseResponse,
    summary="KYC Service Health Check",
    description="Check KYC service health and status"
)
async def kyc_health_check():
    """
    Health check endpoint for KYC service.
    
    Returns service status and basic metrics.
    """
    try:
        health_status = await kyc_service.health_check()
        
        return BaseResponse(
            success=True,
            message="KYC service is healthy",
            data=health_status
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"KYC service health check failed: {str(e)}"
        )
