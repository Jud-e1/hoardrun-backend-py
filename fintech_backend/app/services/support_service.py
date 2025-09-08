from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import uuid
import random
from ..models.support import (
    SupportTicketRequest, TicketMessageRequest, TicketUpdateRequest, 
    FAQSearchRequest, FeedbackRequest,
    SupportTicketProfile, TicketMessage, TicketSummary, FAQItem, 
    FAQSearchResult, HelpArticle, SupportStats, ContactInfo,
    SupportTicketDB, TicketMessageDB, FAQDB, FeedbackDB, HelpArticleDB,
    TicketStatus, TicketPriority, TicketCategory, FAQCategory, SupportChannelType
)
from ..core.exceptions import NotFoundError, ValidationError, BusinessLogicError

class SupportService:
    def __init__(self):
        # Mock data storage
        self.tickets: Dict[str, SupportTicketDB] = {}
        self.messages: Dict[str, TicketMessageDB] = {}
        self.faqs: Dict[str, FAQDB] = {}
        self.feedback: Dict[str, FeedbackDB] = {}
        self.help_articles: Dict[str, HelpArticleDB] = {}
        self._ticket_counter = 1000
        self._initialize_mock_data()
    
    def _initialize_mock_data(self):
        """Initialize with sample support data"""
        user_id = "user_123"
        
        # Sample support tickets
        ticket_data = [
            {
                "subject": "Unable to complete mobile money transfer",
                "description": "I'm trying to send money via MTN MoMo but the transaction keeps failing. I've tried multiple times with the same result.",
                "category": TicketCategory.MOBILE_MONEY,
                "priority": TicketPriority.HIGH,
                "status": TicketStatus.OPEN,
                "channel": SupportChannelType.IN_APP,
                "user_email": "user@example.com"
            },
            {
                "subject": "KYC document verification taking too long",
                "description": "I submitted my national ID for verification 5 days ago but it's still pending. When will it be approved?",
                "category": TicketCategory.KYC_VERIFICATION,
                "priority": TicketPriority.MEDIUM,
                "status": TicketStatus.IN_PROGRESS,
                "channel": SupportChannelType.EMAIL,
                "assigned_agent": "agent_001",
                "first_response_at": datetime.utcnow() - timedelta(hours=4)
            },
            {
                "subject": "Savings goal not updating correctly",
                "description": "My emergency fund savings goal shows incorrect progress. I've made several contributions but the progress bar hasn't updated.",
                "category": TicketCategory.SAVINGS_GOALS,
                "priority": TicketPriority.LOW,
                "status": TicketStatus.RESOLVED,
                "channel": SupportChannelType.CHAT,
                "resolved_at": datetime.utcnow() - timedelta(hours=2),
                "satisfaction_rating": 4
            }
        ]
        
        for i, ticket_info in enumerate(ticket_data):
            ticket_id = str(uuid.uuid4())
            ticket_number = f"TKT-{self._ticket_counter + i}"
            
            self.tickets[ticket_id] = SupportTicketDB(
                id=ticket_id,
                ticket_number=ticket_number,
                user_id=user_id,
                created_at=datetime.utcnow() - timedelta(days=random.randint(1, 7)),
                updated_at=datetime.utcnow() - timedelta(hours=random.randint(1, 24)),
                last_activity_at=datetime.utcnow() - timedelta(hours=random.randint(1, 12)),
                **ticket_info
            )
            
            # Add sample messages for some tickets
            if i < 2:  # First two tickets have messages
                self._create_sample_messages(ticket_id, user_id)
        
        self._ticket_counter += len(ticket_data)
        
        # Sample FAQ items
        faq_data = [
            {
                "question": "How do I create an account?",
                "answer": "To create an account, download the HoardRun app, tap 'Sign Up', enter your phone number, verify with the SMS code, and complete your profile with basic information.",
                "category": FAQCategory.GETTING_STARTED,
                "tags": ["signup", "registration", "account"],
                "is_featured": True,
                "view_count": 1250,
                "helpful_count": 98
            },
            {
                "question": "What mobile money providers do you support?",
                "answer": "We support MTN Mobile Money, Airtel Money, and M-Pesa. You can link multiple mobile money accounts and switch between them easily.",
                "category": FAQCategory.MOBILE_MONEY,
                "tags": ["mtn", "airtel", "mpesa", "providers"],
                "is_featured": True,
                "view_count": 890,
                "helpful_count": 76
            },
            {
                "question": "How do I set up a savings goal?",
                "answer": "Go to the Savings section, tap 'Create Goal', choose your goal type (emergency fund, vacation, etc.), set your target amount and date, then start contributing regularly.",
                "category": FAQCategory.SAVINGS_INVESTMENTS,
                "tags": ["savings", "goals", "targets"],
                "view_count": 654,
                "helpful_count": 52
            },
            {
                "question": "Is my money safe with HoardRun?",
                "answer": "Yes, your money is protected by bank-level security, encryption, and regulatory compliance. We're licensed and regulated by the relevant financial authorities.",
                "category": FAQCategory.SECURITY_PRIVACY,
                "tags": ["security", "safety", "protection"],
                "is_featured": True,
                "view_count": 2100,
                "helpful_count": 187
            },
            {
                "question": "What are the transaction fees?",
                "answer": "Mobile money transfers: 1-2% depending on amount. Bank transfers: UGX 500-2000. International transfers: 3-5%. Check our fee schedule in the app for detailed rates.",
                "category": FAQCategory.FEES_CHARGES,
                "tags": ["fees", "charges", "costs"],
                "view_count": 1456,
                "helpful_count": 89
            }
        ]
        
        for faq_info in faq_data:
            faq_id = str(uuid.uuid4())
            self.faqs[faq_id] = FAQDB(
                id=faq_id,
                created_at=datetime.utcnow() - timedelta(days=random.randint(30, 90)),
                updated_at=datetime.utcnow() - timedelta(days=random.randint(1, 30)),
                is_published=True,
                not_helpful_count=random.randint(2, 15),
                **faq_info
            )
        
        # Sample help articles
        article_data = [
            {
                "title": "Getting Started with HoardRun: Complete Guide",
                "content": "Welcome to HoardRun! This comprehensive guide will walk you through setting up your account, verifying your identity, linking payment methods, and making your first transaction...",
                "category": FAQCategory.GETTING_STARTED,
                "tags": ["guide", "tutorial", "setup"],
                "author": "HoardRun Support Team",
                "view_count": 3200,
                "helpful_count": 245,
                "estimated_read_time": 8
            },
            {
                "title": "Understanding KYC Verification Requirements",
                "content": "Know Your Customer (KYC) verification is required by law to ensure the security of financial services. Here's what documents you need and how the process works...",
                "category": FAQCategory.KYC_VERIFICATION,
                "tags": ["kyc", "verification", "documents"],
                "author": "Compliance Team",
                "view_count": 1890,
                "helpful_count": 156,
                "estimated_read_time": 5
            }
        ]
        
        for article_info in article_data:
            article_id = str(uuid.uuid4())
            self.help_articles[article_id] = HelpArticleDB(
                id=article_id,
                created_at=datetime.utcnow() - timedelta(days=random.randint(60, 120)),
                updated_at=datetime.utcnow() - timedelta(days=random.randint(1, 30)),
                is_published=True,
                not_helpful_count=random.randint(5, 25),
                **article_info
            )
    
    def _create_sample_messages(self, ticket_id: str, user_id: str):
        """Create sample messages for a ticket"""
        messages_data = [
            {
                "sender_id": user_id,
                "sender_name": "John Doe",
                "sender_type": "user",
                "message": "I need help with this issue. It's been happening for the past few days.",
                "created_at": datetime.utcnow() - timedelta(hours=6)
            },
            {
                "sender_id": "agent_001",
                "sender_name": "Sarah Support",
                "sender_type": "agent",
                "message": "Hi John, I understand your concern. Let me look into this for you. Can you provide more details about when this started?",
                "created_at": datetime.utcnow() - timedelta(hours=4)
            },
            {
                "sender_id": user_id,
                "sender_name": "John Doe",
                "sender_type": "user",
                "message": "It started on Monday morning when I tried to make a transfer. The error message says 'Transaction failed - please try again later'.",
                "created_at": datetime.utcnow() - timedelta(hours=2)
            }
        ]
        
        for msg_data in messages_data:
            msg_id = str(uuid.uuid4())
            self.messages[msg_id] = TicketMessageDB(
                id=msg_id,
                ticket_id=ticket_id,
                **msg_data
            )
    
    async def create_support_ticket(
        self, 
        user_id: str, 
        request: SupportTicketRequest
    ) -> SupportTicketProfile:
        """Create a new support ticket"""
        ticket_id = str(uuid.uuid4())
        ticket_number = f"TKT-{self._ticket_counter}"
        self._ticket_counter += 1
        
        now = datetime.utcnow()
        
        ticket = SupportTicketDB(
            id=ticket_id,
            ticket_number=ticket_number,
            user_id=user_id,
            subject=request.subject,
            description=request.description,
            category=request.category,
            priority=request.priority,
            status=TicketStatus.OPEN,
            channel=request.channel,
            user_email=request.user_email,
            user_phone=request.user_phone,
            attachments=request.attachments or [],
            created_at=now,
            updated_at=now,
            last_activity_at=now
        )
        
        self.tickets[ticket_id] = ticket
        
        # Create initial message with the ticket description
        await self._add_ticket_message(
            ticket_id=ticket_id,
            sender_id=user_id,
            sender_name="User",  # In real implementation, get from user profile
            sender_type="user",
            message=request.description,
            attachments=request.attachments or []
        )
        
        return self._build_ticket_profile(ticket)
    
    async def get_user_tickets(
        self, 
        user_id: str,
        status: Optional[TicketStatus] = None,
        skip: int = 0,
        limit: int = 20
    ) -> List[SupportTicketProfile]:
        """Get support tickets for a user"""
        user_tickets = [
            ticket for ticket in self.tickets.values()
            if ticket.user_id == user_id
        ]
        
        # Apply status filter
        if status:
            user_tickets = [t for t in user_tickets if t.status == status]
        
        # Sort by last activity (most recent first)
        user_tickets.sort(key=lambda x: x.last_activity_at, reverse=True)
        
        # Apply pagination
        paginated_tickets = user_tickets[skip:skip + limit]
        
        return [self._build_ticket_profile(ticket) for ticket in paginated_tickets]
    
    async def get_ticket_details(
        self, 
        user_id: str, 
        ticket_id: str
    ) -> SupportTicketProfile:
        """Get detailed information about a specific ticket"""
        if ticket_id not in self.tickets:
            raise NotFoundError("Support ticket not found")
        
        ticket = self.tickets[ticket_id]
        if ticket.user_id != user_id:
            raise NotFoundError("Support ticket not found")
        
        return self._build_ticket_profile(ticket)
    
    async def get_ticket_messages(
        self, 
        user_id: str, 
        ticket_id: str
    ) -> List[TicketMessage]:
        """Get all messages for a ticket"""
        if ticket_id not in self.tickets:
            raise NotFoundError("Support ticket not found")
        
        ticket = self.tickets[ticket_id]
        if ticket.user_id != user_id:
            raise NotFoundError("Support ticket not found")
        
        ticket_messages = [
            msg for msg in self.messages.values()
            if msg.ticket_id == ticket_id and not msg.is_internal
        ]
        
        # Sort by creation time
        ticket_messages.sort(key=lambda x: x.created_at)
        
        return [
            TicketMessage(
                id=msg.id,
                ticket_id=msg.ticket_id,
                sender_id=msg.sender_id,
                sender_name=msg.sender_name,
                sender_type=msg.sender_type,
                message=msg.message,
                attachments=msg.attachments,
                is_internal=msg.is_internal,
                created_at=msg.created_at
            )
            for msg in ticket_messages
        ]
    
    async def add_ticket_message(
        self, 
        user_id: str, 
        ticket_id: str, 
        request: TicketMessageRequest
    ) -> TicketMessage:
        """Add a message to a support ticket"""
        if ticket_id not in self.tickets:
            raise NotFoundError("Support ticket not found")
        
        ticket = self.tickets[ticket_id]
        if ticket.user_id != user_id:
            raise NotFoundError("Support ticket not found")
        
        # Update ticket status if it was resolved/closed
        if ticket.status in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
            ticket.status = TicketStatus.OPEN
        
        ticket.last_activity_at = datetime.utcnow()
        ticket.updated_at = datetime.utcnow()
        
        message = await self._add_ticket_message(
            ticket_id=ticket_id,
            sender_id=user_id,
            sender_name="User",  # In real implementation, get from user profile
            sender_type="user",
            message=request.message,
            attachments=request.attachments or [],
            is_internal=request.is_internal
        )
        
        return message
    
    async def search_faq(self, request: FAQSearchRequest) -> FAQSearchResult:
        """Search FAQ items"""
        query_lower = request.query.lower()
        
        # Filter published FAQs
        published_faqs = [faq for faq in self.faqs.values() if faq.is_published]
        
        # Apply category filter
        if request.category:
            published_faqs = [faq for faq in published_faqs if faq.category == request.category]
        
        # Search in questions, answers, and tags
        matching_faqs = []
        for faq in published_faqs:
            score = 0
            
            # Question match (highest weight)
            if query_lower in faq.question.lower():
                score += 10
            
            # Answer match (medium weight)
            if query_lower in faq.answer.lower():
                score += 5
            
            # Tag match (lower weight)
            for tag in faq.tags:
                if query_lower in tag.lower():
                    score += 2
            
            if score > 0:
                matching_faqs.append((faq, score))
        
        # Sort by score (descending) and view count
        matching_faqs.sort(key=lambda x: (x[1], x[0].view_count), reverse=True)
        
        # Apply limit
        limited_faqs = matching_faqs[:request.limit]
        
        # Convert to response models and increment view counts
        result_items = []
        for faq, _ in limited_faqs:
            faq.view_count += 1  # Increment view count
            result_items.append(FAQItem(
                id=faq.id,
                question=faq.question,
                answer=faq.answer,
                category=faq.category,
                tags=faq.tags,
                view_count=faq.view_count,
                helpful_count=faq.helpful_count,
                not_helpful_count=faq.not_helpful_count,
                created_at=faq.created_at,
                updated_at=faq.updated_at,
                is_featured=faq.is_featured
            ))
        
        # Generate suggested categories
        suggested_categories = []
        if not request.category and len(result_items) < 5:
            category_counts = {}
            for faq in published_faqs:
                category_counts[faq.category.value] = category_counts.get(faq.category.value, 0) + 1
            
            suggested_categories = sorted(category_counts.keys(), 
                                        key=lambda x: category_counts[x], 
                                        reverse=True)[:3]
        
        return FAQSearchResult(
            items=result_items,
            total_results=len(matching_faqs),
            search_query=request.query,
            suggested_categories=suggested_categories
        )
    
    async def get_featured_faqs(self, limit: int = 10) -> List[FAQItem]:
        """Get featured FAQ items"""
        featured_faqs = [
            faq for faq in self.faqs.values() 
            if faq.is_featured and faq.is_published
        ]
        
        # Sort by view count and helpful count
        featured_faqs.sort(key=lambda x: (x.view_count, x.helpful_count), reverse=True)
        
        return [
            FAQItem(
                id=faq.id,
                question=faq.question,
                answer=faq.answer,
                category=faq.category,
                tags=faq.tags,
                view_count=faq.view_count,
                helpful_count=faq.helpful_count,
                not_helpful_count=faq.not_helpful_count,
                created_at=faq.created_at,
                updated_at=faq.updated_at,
                is_featured=faq.is_featured
            )
            for faq in featured_faqs[:limit]
        ]
    
    async def submit_feedback(
        self, 
        user_id: str, 
        request: FeedbackRequest
    ) -> Dict[str, str]:
        """Submit user feedback"""
        feedback_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        feedback = FeedbackDB(
            id=feedback_id,
            user_id=user_id,
            type=request.type,
            title=request.title,
            description=request.description,
            rating=request.rating,
            category=request.category,
            page_url=request.page_url,
            user_agent=request.user_agent,
            status="new",
            created_at=now,
            updated_at=now
        )
        
        self.feedback[feedback_id] = feedback
        
        return {
            "feedback_id": feedback_id,
            "status": "submitted",
            "message": "Thank you for your feedback! We'll review it and get back to you if needed."
        }
    
    async def get_contact_info(self) -> ContactInfo:
        """Get support contact information"""
        return ContactInfo(
            support_email="support@hoardrun.com",
            support_phone="+256-700-123-456",
            business_hours="Monday - Friday: 8:00 AM - 6:00 PM EAT",
            emergency_contact="+256-700-123-999",
            social_media={
                "twitter": "@HoardRunSupport",
                "facebook": "HoardRunOfficial",
                "linkedin": "company/hoardrun"
            },
            office_address="Plot 123, Kampala Road, Kampala, Uganda",
            response_time_sla={
                "critical": "Within 1 hour",
                "urgent": "Within 4 hours",
                "high": "Within 8 hours",
                "medium": "Within 24 hours",
                "low": "Within 48 hours"
            }
        )
    
    async def get_ticket_summary(self, user_id: str) -> TicketSummary:
        """Get ticket summary for user"""
        user_tickets = [t for t in self.tickets.values() if t.user_id == user_id]
        
        total_tickets = len(user_tickets)
        open_tickets = len([t for t in user_tickets if t.status == TicketStatus.OPEN])
        in_progress_tickets = len([t for t in user_tickets if t.status == TicketStatus.IN_PROGRESS])
        resolved_tickets = len([t for t in user_tickets if t.status == TicketStatus.RESOLVED])
        closed_tickets = len([t for t in user_tickets if t.status == TicketStatus.CLOSED])
        
        # Calculate average resolution time
        resolved_with_times = [
            t for t in user_tickets 
            if t.status == TicketStatus.RESOLVED and t.resolved_at
        ]
        
        avg_resolution_time = None
        if resolved_with_times:
            total_hours = sum(
                (t.resolved_at - t.created_at).total_seconds() / 3600
                for t in resolved_with_times
            )
            avg_resolution_time = total_hours / len(resolved_with_times)
        
        # Count by category
        tickets_by_category = {}
        for category in TicketCategory:
            tickets_by_category[category.value] = len([
                t for t in user_tickets if t.category == category
            ])
        
        # Count by priority
        tickets_by_priority = {}
        for priority in TicketPriority:
            tickets_by_priority[priority.value] = len([
                t for t in user_tickets if t.priority == priority
            ])
        
        # Get recent tickets
        recent_tickets = sorted(user_tickets, key=lambda x: x.created_at, reverse=True)[:5]
        recent_profiles = [self._build_ticket_profile(t) for t in recent_tickets]
        
        return TicketSummary(
            total_tickets=total_tickets,
            open_tickets=open_tickets,
            in_progress_tickets=in_progress_tickets,
            resolved_tickets=resolved_tickets,
            closed_tickets=closed_tickets,
            average_resolution_time=avg_resolution_time,
            tickets_by_category=tickets_by_category,
            tickets_by_priority=tickets_by_priority,
            recent_tickets=recent_profiles
        )
    
    # Helper methods
    async def _add_ticket_message(
        self,
        ticket_id: str,
        sender_id: str,
        sender_name: str,
        sender_type: str,
        message: str,
        attachments: List[str] = None,
        is_internal: bool = False
    ) -> TicketMessage:
        """Add a message to a ticket"""
        msg_id = str(uuid.uuid4())
        
        ticket_message = TicketMessageDB(
            id=msg_id,
            ticket_id=ticket_id,
            sender_id=sender_id,
            sender_name=sender_name,
            sender_type=sender_type,
            message=message,
            attachments=attachments or [],
            is_internal=is_internal,
            created_at=datetime.utcnow()
        )
        
        self.messages[msg_id] = ticket_message
        
        return TicketMessage(
            id=ticket_message.id,
            ticket_id=ticket_message.ticket_id,
            sender_id=ticket_message.sender_id,
            sender_name=ticket_message.sender_name,
            sender_type=ticket_message.sender_type,
            message=ticket_message.message,
            attachments=ticket_message.attachments,
            is_internal=ticket_message.is_internal,
            created_at=ticket_message.created_at
        )
    
    def _build_ticket_profile(self, ticket: SupportTicketDB) -> SupportTicketProfile:
        """Build ticket profile from ticket DB"""
        # Count messages for this ticket
        message_count = len([
            msg for msg in self.messages.values()
            if msg.ticket_id == ticket.id and not msg.is_internal
        ])
        
        return SupportTicketProfile(
            id=ticket.id,
            ticket_number=ticket.ticket_number,
            subject=ticket.subject,
            description=ticket.description,
            status=ticket.status,
            priority=ticket.priority,
            category=ticket.category,
            channel=ticket.channel,
            user_id=ticket.user_id,
            user_email=ticket.user_email,
            user_phone=ticket.user_phone,
            assigned_agent=ticket.assigned_agent,
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
            resolved_at=ticket.resolved_at,
            first_response_at=ticket.first_response_at,
            last_activity_at=ticket.last_activity_at,
            message_count=message_count,
            attachments=ticket.attachments,
            tags=ticket.tags,
            satisfaction_rating=ticket.satisfaction_rating
        )
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get support service health status"""
        total_tickets = len(self.tickets)
        total_faqs = len(self.faqs)
        total_feedback = len(self.feedback)
        total_articles = len(self.help_articles)
        
        # Calculate metrics
        open_tickets = len([t for t in self.tickets.values() if t.status == TicketStatus.OPEN])
        resolved_tickets = len([t for t in self.tickets.values() if t.status == TicketStatus.RESOLVED])
        
        return {
            "service": "support",
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {
                "total_tickets": total_tickets,
                "open_tickets": open_tickets,
                "resolved_tickets": resolved_tickets,
                "total_faqs": total_faqs,
                "total_feedback": total_feedback,
                "total_help_articles": total_articles
            },
            "features": {
                "ticket_management": "active",
                "faq_search": "active",
                "feedback_collection": "active",
                "help_articles": "active"
            },
            "version": "1.0.0"
        }
