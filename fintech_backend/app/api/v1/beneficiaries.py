"""
Beneficiaries API endpoints for managing payment recipients.
"""

from fastapi import APIRouter, HTTPException, Depends, status, Body, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional, List
import asyncio
from datetime import datetime

from ...models.beneficiaries import (
    BeneficiaryCreateRequest, BeneficiaryUpdateRequest, BeneficiaryProfile,
    BeneficiaryListResponse, BeneficiaryResponse, RecentBeneficiariesResponse,
    BeneficiarySearchRequest, BeneficiaryType, BeneficiaryStatus, BeneficiaryStats
)
from ...services.beneficiaries_service import BeneficiariesService
from ...database.config import get_db
from ...core.exceptions import (
    ValidationException, AuthenticationException, AuthorizationException,
    UserNotFoundException, NotFoundError
)
from ...utils.response import success_response
from ...config.logging import get_logger

logger = get_logger(__name__)
security = HTTPBearer()

router = APIRouter(prefix="/beneficiaries", tags=["Beneficiaries"])


def get_beneficiaries_service():
    """Dependency to get beneficiaries service instance"""
    return BeneficiariesService()


@router.get("", response_model=BeneficiaryListResponse)
async def get_beneficiaries(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    type: Optional[BeneficiaryType] = Query(None, description="Filter by type"),
    status: Optional[BeneficiaryStatus] = Query(None, description="Filter by status"),
    country: Optional[str] = Query(None, description="Filter by country"),
    is_favorite: Optional[bool] = Query(None, description="Filter by favorite status"),
    search: Optional[str] = Query(None, description="Search query"),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    beneficiaries_service: BeneficiariesService = Depends(get_beneficiaries_service)
):
    """
    Get user's beneficiaries with filtering and pagination.
    
    Returns a paginated list of the user's beneficiaries with optional filtering.
    """
    try:
        logger.info("API: Getting beneficiaries list")
        
        token = credentials.credentials
        search_request = BeneficiarySearchRequest(
            query=search,
            type=type,
            status=status,
            country=country,
            is_favorite=is_favorite,
            page=page,
            per_page=per_page
        )
        
        result = await beneficiaries_service.get_beneficiaries(token, search_request, db)
        
        return BeneficiaryListResponse(
            success=True,
            message="Beneficiaries retrieved successfully",
            data={"beneficiaries": result["beneficiaries"]},
            total=result["total"],
            page=result["page"],
            per_page=result["per_page"]
        )
        
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting beneficiaries: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=BeneficiaryResponse)
async def create_beneficiary(
    request: BeneficiaryCreateRequest = Body(...),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    beneficiaries_service: BeneficiariesService = Depends(get_beneficiaries_service)
):
    """
    Create a new beneficiary.
    
    Creates a new payment recipient for the authenticated user.
    """
    try:
        logger.info(f"API: Creating beneficiary - {request.name}")
        
        token = credentials.credentials
        beneficiary = await beneficiaries_service.create_beneficiary(token, request, db)
        
        return success_response(
            data={"beneficiary": beneficiary},
            message="Beneficiary created successfully"
        )
        
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating beneficiary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{beneficiary_id}", response_model=BeneficiaryResponse)
async def get_beneficiary(
    beneficiary_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    beneficiaries_service: BeneficiariesService = Depends(get_beneficiaries_service)
):
    """
    Get a specific beneficiary by ID.
    
    Returns detailed information about a specific beneficiary.
    """
    try:
        logger.info(f"API: Getting beneficiary - {beneficiary_id}")
        
        token = credentials.credentials
        beneficiary = await beneficiaries_service.get_beneficiary(token, beneficiary_id, db)
        
        return success_response(
            data={"beneficiary": beneficiary},
            message="Beneficiary retrieved successfully"
        )
        
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except NotFoundError as e:
        logger.error(f"Beneficiary not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting beneficiary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{beneficiary_id}", response_model=BeneficiaryResponse)
async def update_beneficiary(
    beneficiary_id: str,
    request: BeneficiaryUpdateRequest = Body(...),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    beneficiaries_service: BeneficiariesService = Depends(get_beneficiaries_service)
):
    """
    Update a beneficiary.
    
    Updates an existing beneficiary's information.
    """
    try:
        logger.info(f"API: Updating beneficiary - {beneficiary_id}")
        
        token = credentials.credentials
        beneficiary = await beneficiaries_service.update_beneficiary(token, beneficiary_id, request, db)
        
        return success_response(
            data={"beneficiary": beneficiary},
            message="Beneficiary updated successfully"
        )
        
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except NotFoundError as e:
        logger.error(f"Beneficiary not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating beneficiary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{beneficiary_id}", response_model=dict)
async def delete_beneficiary(
    beneficiary_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    beneficiaries_service: BeneficiariesService = Depends(get_beneficiaries_service)
):
    """
    Delete a beneficiary.
    
    Permanently removes a beneficiary from the user's list.
    """
    try:
        logger.info(f"API: Deleting beneficiary - {beneficiary_id}")
        
        token = credentials.credentials
        result = await beneficiaries_service.delete_beneficiary(token, beneficiary_id, db)
        
        return success_response(
            data=result,
            message="Beneficiary deleted successfully"
        )
        
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except NotFoundError as e:
        logger.error(f"Beneficiary not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting beneficiary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/recent", response_model=RecentBeneficiariesResponse)
async def get_recent_beneficiaries(
    limit: int = Query(10, ge=1, le=50, description="Number of recent beneficiaries"),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    beneficiaries_service: BeneficiariesService = Depends(get_beneficiaries_service)
):
    """
    Get recently used beneficiaries.
    
    Returns a list of the most recently used beneficiaries.
    """
    try:
        logger.info("API: Getting recent beneficiaries")
        
        token = credentials.credentials
        beneficiaries = await beneficiaries_service.get_recent_beneficiaries(token, limit, db)
        
        return success_response(
            data={"beneficiaries": beneficiaries},
            message="Recent beneficiaries retrieved successfully"
        )
        
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting recent beneficiaries: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{beneficiary_id}/favorite", response_model=dict)
async def toggle_favorite_beneficiary(
    beneficiary_id: str,
    is_favorite: bool = Body(..., embed=True),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    beneficiaries_service: BeneficiariesService = Depends(get_beneficiaries_service)
):
    """
    Toggle beneficiary favorite status.
    
    Marks or unmarks a beneficiary as favorite.
    """
    try:
        logger.info(f"API: Toggling favorite status for beneficiary - {beneficiary_id}")
        
        token = credentials.credentials
        result = await beneficiaries_service.toggle_favorite(token, beneficiary_id, is_favorite, db)
        
        return success_response(
            data=result,
            message=f"Beneficiary {'added to' if is_favorite else 'removed from'} favorites"
        )
        
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except NotFoundError as e:
        logger.error(f"Beneficiary not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error toggling favorite: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{beneficiary_id}/verify", response_model=dict)
async def verify_beneficiary(
    beneficiary_id: str,
    verification_method: str = Body(...),
    verification_data: dict = Body(...),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    beneficiaries_service: BeneficiariesService = Depends(get_beneficiaries_service)
):
    """
    Verify a beneficiary.
    
    Initiates or completes the verification process for a beneficiary.
    """
    try:
        logger.info(f"API: Verifying beneficiary - {beneficiary_id}")
        
        token = credentials.credentials
        result = await beneficiaries_service.verify_beneficiary(
            token, beneficiary_id, verification_method, verification_data, db
        )
        
        return success_response(
            data=result,
            message="Beneficiary verification initiated"
        )
        
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except NotFoundError as e:
        logger.error(f"Beneficiary not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error verifying beneficiary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats", response_model=dict)
async def get_beneficiaries_stats(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    beneficiaries_service: BeneficiariesService = Depends(get_beneficiaries_service)
):
    """
    Get beneficiaries statistics.
    
    Returns statistical information about the user's beneficiaries.
    """
    try:
        logger.info("API: Getting beneficiaries statistics")
        
        token = credentials.credentials
        stats = await beneficiaries_service.get_beneficiaries_stats(token, db)
        
        return success_response(
            data={"stats": stats},
            message="Beneficiaries statistics retrieved successfully"
        )
        
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting beneficiaries stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/welcome", response_model=dict)
async def welcome(request: Request):
    """
    Welcome endpoint that logs request metadata and returns a welcome message.

    Logs the request method and path, then returns a JSON response with a welcome message.
    """
    try:
        logger.info(f"Request received: {request.method} {request.url.path}")

        return success_response(
            data={"message": "Welcome to the Beneficiaries API Service!"},
            message="Welcome message retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Error in welcome endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health", response_model=dict)
async def beneficiaries_service_health():
    """
    Health check endpoint for beneficiaries service.

    Returns the operational status of the beneficiaries service.
    """
    try:
        # Simulate service checks
        await asyncio.sleep(0.01)  # Mock processing time

        return success_response(
            data={
                "service": "beneficiaries_service",
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0"
            },
            message="Beneficiaries service is healthy"
        )

    except Exception as e:
        logger.error(f"Beneficiaries service health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")
