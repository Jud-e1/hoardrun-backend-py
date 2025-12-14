"""
P2P money transfer API endpoints for the fintech backend.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer
from typing import Optional, List
from datetime import date, datetime

from ..services.p2p_service import P2PService
from ..models.p2p import (
    P2PSendRequest, MoneyRequestCreateRequest, SplitBillCreateRequest,
    PaymentLinkCreateRequest, P2PQuoteRequest, PaymentLinkPaymentRequest,
    P2PTransactionResponse, P2PTransactionListResponse, MoneyRequestResponse,
    MoneyRequestListResponse, SplitBillResponse, SplitBillListResponse,
    PaymentLinkResponse, PaymentLinkListResponse, P2PQuoteResponse,
    P2PAnalyticsResponse, P2PContactListResponse, P2PTransactionType,
    P2PStatus, P2PRequestStatus, ContactMethod
)
from ..models.base import PaginationRequest, BaseResponse
from ..core.auth import get_current_user

router = APIRouter(prefix="/p2p", tags=["P2P Money"])
security = HTTPBearer()

# Initialize service
p2p_service = P2PService()


@router.get("/health", response_model=BaseResponse)
async def get_p2p_health():
    """Get P2P service health status."""
    health_data = await p2p_service.get_service_health()
    return BaseResponse(
        success=True,
        message="P2P service is healthy",
        data=health_data
    )


# Contact Management Endpoints
@router.get("/contacts", response_model=P2PContactListResponse)
async def get_contacts(
    search: Optional[str] = Query(None, description="Search contacts by name or value"),
    current_user: dict = Depends(get_current_user)
):
    """Get P2P contacts for the authenticated user."""
    try:
        contacts = await p2p_service.get_contacts(current_user["user_id"], search)
        
        # Separate recent contacts and favorites
        recent_contacts = [c for c in contacts if c.last_transaction_date and 
                          (datetime.utcnow() - c.last_transaction_date).days <= 30][:5]
        favorites = [c for c in contacts if c.is_favorite]
        
        return P2PContactListResponse(
            success=True,
            message="Contacts retrieved successfully",
            data={
                "contacts": contacts,
                "total_count": len(contacts),
                "recent_contacts": recent_contacts,
                "favorites": favorites
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve contacts: {str(e)}"
        )


@router.post("/contacts", response_model=BaseResponse)
async def add_contact(
    contact_value: str = Query(..., description="Contact value (email, phone, username)"),
    contact_method: ContactMethod = Query(..., description="Contact method"),
    display_name: str = Query(..., description="Display name for contact"),
    current_user: dict = Depends(get_current_user)
):
    """Add a new P2P contact."""
    try:
        contact = await p2p_service.add_contact(
            current_user["user_id"], contact_value, contact_method, display_name
        )
        return BaseResponse(
            success=True,
            message="Contact added successfully",
            data=contact.dict()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to add contact: {str(e)}"
        )


@router.patch("/contacts/{contact_id}/favorite", response_model=BaseResponse)
async def update_contact_favorite(
    contact_id: str,
    is_favorite: bool = Query(..., description="Favorite status"),
    current_user: dict = Depends(get_current_user)
):
    """Update contact favorite status."""
    try:
        contact = await p2p_service.update_contact_favorite(
            current_user["user_id"], contact_id, is_favorite
        )
        return BaseResponse(
            success=True,
            message="Contact updated successfully",
            data=contact.dict()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Failed to update contact: {str(e)}"
        )


# P2P Transaction Endpoints
@router.post("/send", response_model=P2PTransactionResponse)
async def send_money(
    request: P2PSendRequest,
    current_user: dict = Depends(get_current_user)
):
    """Send money to another user."""
    try:
        transaction = await p2p_service.send_money(current_user["user_id"], request)
        return P2PTransactionResponse(
            success=True,
            message="Money sent successfully",
            data={"transaction": transaction}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to send money: {str(e)}"
        )


@router.get("/transactions", response_model=P2PTransactionListResponse)
async def get_p2p_transactions(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    transaction_type: Optional[P2PTransactionType] = Query(None, description="Filter by transaction type"),
    status: Optional[P2PStatus] = Query(None, description="Filter by status"),
    current_user: dict = Depends(get_current_user)
):
    """Get P2P transactions for the authenticated user."""
    try:
        pagination = PaginationRequest(skip=(page - 1) * limit, limit=limit)
        result = await p2p_service.get_p2p_transactions(
            current_user["user_id"], pagination, transaction_type, status
        )
        
        return P2PTransactionListResponse(
            success=True,
            message="P2P transactions retrieved successfully",
            data=result
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve P2P transactions: {str(e)}"
        )


@router.get("/transactions/{transaction_id}", response_model=P2PTransactionResponse)
async def get_p2p_transaction(
    transaction_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific P2P transaction."""
    try:
        transaction = await p2p_service.get_p2p_transaction(current_user["user_id"], transaction_id)
        return P2PTransactionResponse(
            success=True,
            message="P2P transaction retrieved successfully",
            data={"transaction": transaction}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"P2P transaction not found: {str(e)}"
        )


@router.patch("/transactions/{transaction_id}/cancel", response_model=P2PTransactionResponse)
async def cancel_p2p_transaction(
    transaction_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Cancel a P2P transaction."""
    try:
        transaction = await p2p_service.cancel_p2p_transaction(current_user["user_id"], transaction_id)
        return P2PTransactionResponse(
            success=True,
            message="P2P transaction cancelled successfully",
            data={"transaction": transaction}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to cancel transaction: {str(e)}"
        )


@router.post("/quote", response_model=P2PQuoteResponse)
async def get_p2p_quote(
    request: P2PQuoteRequest,
    current_user: dict = Depends(get_current_user)
):
    """Get a quote for P2P transaction."""
    try:
        quote = await p2p_service.get_p2p_quote(current_user["user_id"], request)
        return P2PQuoteResponse(
            success=True,
            message="Quote generated successfully",
            data=quote
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to generate quote: {str(e)}"
        )


# Money Request Endpoints
@router.post("/request", response_model=MoneyRequestResponse)
async def request_money(
    request: MoneyRequestCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create a money request."""
    try:
        money_request = await p2p_service.request_money(current_user["user_id"], request)
        return MoneyRequestResponse(
            success=True,
            message="Money request created successfully",
            data={"request": money_request}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create money request: {str(e)}"
        )


@router.get("/requests", response_model=MoneyRequestListResponse)
async def get_money_requests(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[P2PRequestStatus] = Query(None, description="Filter by status"),
    request_type: str = Query("all", description="Request type: all, outgoing, incoming"),
    current_user: dict = Depends(get_current_user)
):
    """Get money requests for the authenticated user."""
    try:
        pagination = PaginationRequest(skip=(page - 1) * limit, limit=limit)
        result = await p2p_service.get_money_requests(
            current_user["user_id"], pagination, status, request_type
        )
        
        return MoneyRequestListResponse(
            success=True,
            message="Money requests retrieved successfully",
            data=result
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve money requests: {str(e)}"
        )


@router.get("/requests/{request_id}", response_model=MoneyRequestResponse)
async def get_money_request(
    request_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific money request."""
    try:
        money_request = await p2p_service.get_money_request(current_user["user_id"], request_id)
        return MoneyRequestResponse(
            success=True,
            message="Money request retrieved successfully",
            data={"request": money_request}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Money request not found: {str(e)}"
        )


@router.patch("/requests/{request_id}/respond", response_model=MoneyRequestResponse)
async def respond_to_money_request(
    request_id: str,
    action: str = Query(..., description="Action: accept or decline"),
    source_account_id: Optional[str] = Query(None, description="Source account for payment (required for accept)"),
    current_user: dict = Depends(get_current_user)
):
    """Respond to a money request (accept/decline)."""
    try:
        money_request = await p2p_service.respond_to_money_request(
            current_user["user_id"], request_id, action, source_account_id
        )
        return MoneyRequestResponse(
            success=True,
            message=f"Money request {action}ed successfully",
            data={"request": money_request}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to respond to money request: {str(e)}"
        )


@router.patch("/requests/{request_id}/cancel", response_model=MoneyRequestResponse)
async def cancel_money_request(
    request_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Cancel a money request."""
    try:
        money_request = await p2p_service.cancel_money_request(current_user["user_id"], request_id)
        return MoneyRequestResponse(
            success=True,
            message="Money request cancelled successfully",
            data={"request": money_request}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to cancel money request: {str(e)}"
        )


# Split Bill Endpoints
@router.post("/split-bills", response_model=SplitBillResponse)
async def create_split_bill(
    request: SplitBillCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create a split bill."""
    try:
        result = await p2p_service.create_split_bill(current_user["user_id"], request)
        
        # Get the related payment requests
        split_bill_data = await p2p_service.get_split_bill(current_user["user_id"], result.split_bill_id)
        
        return SplitBillResponse(
            success=True,
            message="Split bill created successfully",
            data=split_bill_data
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create split bill: {str(e)}"
        )


@router.get("/split-bills", response_model=SplitBillListResponse)
async def get_split_bills(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    active_only: bool = Query(False, description="Only show active split bills"),
    current_user: dict = Depends(get_current_user)
):
    """Get split bills for the authenticated user."""
    try:
        pagination = PaginationRequest(skip=(page - 1) * limit, limit=limit)
        result = await p2p_service.get_split_bills(
            current_user["user_id"], pagination, active_only
        )
        
        return SplitBillListResponse(
            success=True,
            message="Split bills retrieved successfully",
            data=result
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve split bills: {str(e)}"
        )


@router.get("/split-bills/{split_bill_id}", response_model=SplitBillResponse)
async def get_split_bill(
    split_bill_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific split bill with related payment requests."""
    try:
        result = await p2p_service.get_split_bill(current_user["user_id"], split_bill_id)
        return SplitBillResponse(
            success=True,
            message="Split bill retrieved successfully",
            data=result
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Split bill not found: {str(e)}"
        )


# Payment Link Endpoints
@router.post("/payment-links", response_model=PaymentLinkResponse)
async def create_payment_link(
    request: PaymentLinkCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create a payment link."""
    try:
        payment_link = await p2p_service.create_payment_link(current_user["user_id"], request)
        return PaymentLinkResponse(
            success=True,
            message="Payment link created successfully",
            data={"payment_link": payment_link}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create payment link: {str(e)}"
        )


@router.get("/payment-links", response_model=PaymentLinkListResponse)
async def get_payment_links(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    active_only: bool = Query(False, description="Only show active payment links"),
    current_user: dict = Depends(get_current_user)
):
    """Get payment links for the authenticated user."""
    try:
        pagination = PaginationRequest(skip=(page - 1) * limit, limit=limit)
        result = await p2p_service.get_payment_links(
            current_user["user_id"], pagination, active_only
        )
        
        return PaymentLinkListResponse(
            success=True,
            message="Payment links retrieved successfully",
            data=result
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve payment links: {str(e)}"
        )


@router.get("/payment-links/{link_id}", response_model=PaymentLinkResponse)
async def get_payment_link_public(link_id: str):
    """Get a payment link by ID (public access for payments)."""
    try:
        payment_link = await p2p_service.get_payment_link(link_id)
        return PaymentLinkResponse(
            success=True,
            message="Payment link retrieved successfully",
            data={"payment_link": payment_link}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment link not found: {str(e)}"
        )


@router.post("/payment-links/{link_id}/pay", response_model=P2PTransactionResponse)
async def pay_via_payment_link(
    link_id: str,
    request: PaymentLinkPaymentRequest,
    current_user: dict = Depends(get_current_user)
):
    """Make a payment via payment link."""
    try:
        # Set the link_id from URL
        request.link_id = link_id
        
        transaction = await p2p_service.process_payment_link_payment(request)
        return P2PTransactionResponse(
            success=True,
            message="Payment processed successfully",
            data={"transaction": transaction}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process payment: {str(e)}"
        )


@router.patch("/payment-links/{link_id}/deactivate", response_model=PaymentLinkResponse)
async def deactivate_payment_link(
    link_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Deactivate a payment link."""
    try:
        payment_link = await p2p_service.deactivate_payment_link(current_user["user_id"], link_id)
        return PaymentLinkResponse(
            success=True,
            message="Payment link deactivated successfully",
            data={"payment_link": payment_link}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Failed to deactivate payment link: {str(e)}"
        )


# Analytics Endpoints
@router.get("/analytics", response_model=P2PAnalyticsResponse)
async def get_p2p_analytics(
    start_date: date = Query(..., description="Analysis start date"),
    end_date: date = Query(..., description="Analysis end date"),
    current_user: dict = Depends(get_current_user)
):
    """Get P2P transaction analytics for the authenticated user."""
    try:
        # Validate date range
        if start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start date cannot be after end date"
            )
        
        if (end_date - start_date).days > 365:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Date range cannot exceed 365 days"
            )
        
        analytics = await p2p_service.get_p2p_analytics(
            current_user["user_id"], start_date, end_date
        )
        
        return P2PAnalyticsResponse(
            success=True,
            message="P2P analytics retrieved successfully",
            data=analytics
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve P2P analytics: {str(e)}"
        )


# Quick Action Endpoints
@router.get("/recent-contacts", response_model=BaseResponse)
async def get_recent_contacts(
    limit: int = Query(10, ge=1, le=50, description="Number of recent contacts"),
    current_user: dict = Depends(get_current_user)
):
    """Get recently used P2P contacts."""
    try:
        contacts = await p2p_service.get_contacts(current_user["user_id"])
        
        # Filter and sort by recent activity
        recent_contacts = [
            contact for contact in contacts 
            if contact.last_transaction_date and 
               (datetime.utcnow() - contact.last_transaction_date).days <= 30
        ]
        recent_contacts.sort(key=lambda x: x.last_transaction_date, reverse=True)
        recent_contacts = recent_contacts[:limit]
        
        return BaseResponse(
            success=True,
            message="Recent contacts retrieved successfully",
            data={"contacts": recent_contacts}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve recent contacts: {str(e)}"
        )


@router.get("/pending-requests", response_model=BaseResponse)
async def get_pending_requests(
    current_user: dict = Depends(get_current_user)
):
    """Get pending money requests (both sent and received)."""
    try:
        pagination = PaginationRequest(skip=0, limit=50)
        
        # Get pending outgoing requests
        outgoing_result = await p2p_service.get_money_requests(
            current_user["user_id"], pagination, P2PRequestStatus.PENDING, "outgoing"
        )
        
        # Get pending incoming requests
        incoming_result = await p2p_service.get_money_requests(
            current_user["user_id"], pagination, P2PRequestStatus.PENDING, "incoming"
        )
        
        return BaseResponse(
            success=True,
            message="Pending requests retrieved successfully",
            data={
                "outgoing_requests": outgoing_result["requests"],
                "incoming_requests": incoming_result["requests"],
                "outgoing_count": outgoing_result["pending_outgoing"],
                "incoming_count": incoming_result["pending_incoming"]
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve pending requests: {str(e)}"
        )


@router.get("/summary", response_model=BaseResponse)
async def get_p2p_summary(
    current_user: dict = Depends(get_current_user)
):
    """Get P2P activity summary for dashboard."""
    try:
        # Get recent analytics (last 30 days)
        end_date = date.today()
        start_date = end_date.replace(day=1)  # Start of current month
        
        analytics = await p2p_service.get_p2p_analytics(
            current_user["user_id"], start_date, end_date
        )
        
        # Get pending counts
        pagination = PaginationRequest(skip=0, limit=1)
        transactions_result = await p2p_service.get_p2p_transactions(
            current_user["user_id"], pagination
        )
        
        requests_result = await p2p_service.get_money_requests(
            current_user["user_id"], pagination
        )
        
        return BaseResponse(
            success=True,
            message="P2P summary retrieved successfully",
            data={
                "monthly_sent": analytics["total_sent"],
                "monthly_received": analytics["total_received"],
                "pending_transactions": transactions_result["pending_sent"] + transactions_result["pending_received"],
                "pending_requests": requests_result["pending_outgoing"] + requests_result["pending_incoming"],
                "recent_transaction_count": analytics["transaction_count"]
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve P2P summary: {str(e)}"
        )


# Additional Utility Endpoints
@router.get("/limits", response_model=BaseResponse)
async def get_p2p_limits(
    current_user: dict = Depends(get_current_user)
):
    """Get P2P transaction limits for the user."""
    try:
        # Mock P2P limits based on user tier
        limits = {
            "daily_send_limit": Decimal("5000.00"),
            "daily_receive_limit": Decimal("10000.00"),
            "monthly_send_limit": Decimal("20000.00"),
            "monthly_receive_limit": Decimal("50000.00"),
            "per_transaction_limit": Decimal("2500.00"),
            "daily_send_used": Decimal("250.00"),
            "daily_receive_used": Decimal("150.00"),
            "monthly_send_used": Decimal("1200.00"),
            "monthly_receive_used": Decimal("800.00"),
            "currency": "USD"
        }
        
        return BaseResponse(
            success=True,
            message="P2P limits retrieved successfully",
            data=limits
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve P2P limits: {str(e)}"
        )


@router.get("/fees", response_model=BaseResponse)
async def get_p2p_fees(
    amount: Optional[float] = Query(None, description="Amount to calculate fee for"),
    currency: str = Query("USD", description="Currency code"),
    current_user: dict = Depends(get_current_user)
):
    """Get P2P transaction fee information."""
    try:
        if amount:
            # Calculate fee for specific amount
            fee = await p2p_service._calculate_p2p_fee(Decimal(str(amount)), currency)
            fee_data = {
                "amount": Decimal(str(amount)),
                "fee": fee,
                "total_cost": Decimal(str(amount)) + fee,
                "currency": currency
            }
        else:
            # Return fee structure
            fee_data = {
                "fee_structure": {
                    "under_100": "Free",
                    "100_to_1000": "$0.50 flat fee",
                    "over_1000": "0.5% of amount"
                },
                "currency": currency
            }
        
        return BaseResponse(
            success=True,
            message="P2P fees retrieved successfully",
            data=fee_data
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve P2P fees: {str(e)}"
        )
