"""
Support & Help API Routes
Handles customer support tickets, FAQ search, feedback, and help resources
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer

from ...core.auth import get_current_user
from ...models.support import (
    SupportTicketRequest,
    SupportTicketProfile,
    TicketMessageRequest,
    TicketMessage,
    FAQSearchRequest,
    FAQItem,
    FeedbackRequest,
    ContactInfo,
    TicketStatus,
    TicketPriority,
    TicketCategory,
    FAQCategory
)
from ...services.support_service import SupportService
from ...core.exceptions import ValidationError, NotFoundError
from ...models.base import PaginatedResponse, SuccessResponse

router = APIRouter(prefix="/support", tags=["Support & Help"])
security = HTTPBearer()

# Initialize support service
support_service = SupportService()

@router.post("/tickets", response_model=SupportTicketProfile, status_code=status.HTTP_201_CREATED)
async def create_support_ticket(
    ticket_request: SupportTicketRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new support ticket
    
    - **subject**: Brief description of the issue
    - **description**: Detailed description of the problem
    - **category**: Type of issue (technical, billing, account, etc.)
    - **priority**: Urgency level (low, medium, high, urgent, critical)
    - **channel**: How the ticket was created (email, chat, phone, etc.)
    - **attachments**: Optional file attachments
    """
    try:
        ticket = await support_service.create_ticket(
            user_id=current_user["user_id"],
            ticket_data=ticket_request
        )
        return ticket
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create support ticket"
        )

@router.get("/tickets", response_model=PaginatedResponse[SupportTicketProfile])
async def get_user_tickets(
    current_user: dict = Depends(get_current_user),
    status_filter: Optional[TicketStatus] = Query(None, description="Filter by ticket status"),
    category_filter: Optional[TicketCategory] = Query(None, description="Filter by ticket category"),
    priority_filter: Optional[TicketPriority] = Query(None, description="Filter by priority level"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page")
):
    """
    Get user's support tickets with optional filtering
    
    - **status_filter**: Filter by ticket status
    - **category_filter**: Filter by ticket category
    - **priority_filter**: Filter by priority level
    - **page**: Page number for pagination
    - **limit**: Number of items per page
    """
    try:
        tickets = await support_service.get_user_tickets(
            user_id=current_user["user_id"],
            status_filter=status_filter,
            category_filter=category_filter,
            priority_filter=priority_filter,
            page=page,
            limit=limit
        )
        return tickets
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve support tickets"
        )

@router.get("/tickets/{ticket_id}/messages", response_model=List[TicketMessage])
async def get_ticket_messages(
    ticket_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get all messages for a specific support ticket
    
    - **ticket_id**: Unique identifier of the support ticket
    """
    try:
        messages = await support_service.get_ticket_messages(
            ticket_id=ticket_id,
            user_id=current_user["user_id"]
        )
        return messages
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve ticket messages"
        )

@router.post("/tickets/{ticket_id}/messages", response_model=TicketMessage, status_code=status.HTTP_201_CREATED)
async def add_ticket_message(
    ticket_id: str,
    message_request: TicketMessageRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Add a message to an existing support ticket
    
    - **ticket_id**: Unique identifier of the support ticket
    - **message**: Message content
    - **attachments**: Optional file attachments
    """
    try:
        message = await support_service.add_ticket_message(
            ticket_id=ticket_id,
            user_id=current_user["user_id"],
            message_data=message_request
        )
        return message
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add ticket message"
        )

@router.post("/faq/search", response_model=List[FAQItem])
async def search_faq(
    search_request: FAQSearchRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Search FAQ items based on query and category
    
    - **query**: Search terms to find relevant FAQ items
    - **category**: Optional category filter
    - **limit**: Maximum number of results to return
    """
    try:
        faq_items = await support_service.search_faq(
            query=search_request.query,
            category=search_request.category,
            limit=search_request.limit
        )
        return faq_items
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search FAQ items"
        )

@router.get("/faq/categories", response_model=List[str])
async def get_faq_categories():
    """
    Get all available FAQ categories
    """
    try:
        categories = [category.value for category in FAQCategory]
        return categories
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve FAQ categories"
        )

@router.post("/feedback", response_model=SuccessResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    feedback_request: FeedbackRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Submit user feedback about the application
    
    - **type**: Type of feedback (bug_report, feature_request, general, complaint, compliment)
    - **subject**: Brief description of the feedback
    - **message**: Detailed feedback message
    - **rating**: Optional rating (1-5 stars)
    - **page_url**: Optional URL where feedback originated
    """
    try:
        await support_service.submit_feedback(
            user_id=current_user["user_id"],
            feedback_data=feedback_request
        )
        return SuccessResponse(
            success=True,
            message="Feedback submitted successfully. Thank you for helping us improve!"
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit feedback"
        )

@router.get("/contact", response_model=ContactInfo)
async def get_contact_information():
    """
    Get contact information for customer support
    """
    try:
        contact_info = await support_service.get_contact_info()
        return contact_info
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve contact information"
        )

@router.get("/health", response_model=dict)
async def support_health_check():
    """
    Health check endpoint for support system
    """
    try:
        health_status = await support_service.health_check()
        return {
            "status": "healthy",
            "service": "support",
            "timestamp": health_status["timestamp"],
            "details": health_status
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "support",
            "error": str(e)
        }
