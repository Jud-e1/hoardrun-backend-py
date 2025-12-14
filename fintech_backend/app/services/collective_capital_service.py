"""
Collective Capital service for managing investment circles and group investing functionality.
"""

import asyncio
import random
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from fastapi import HTTPException

from ..models.collective_capital import (
    CollectiveCircle, CircleMember, InvestmentProposal, CircleInvestment,
    CircleActivity, JoinRequest, AIRecommendationModel, LoyaltyBadge,
    CircleFilters, CircleStats, CreateCircleRequest, UpdateCircleRequest,
    CreateProposalRequest, VoteOnProposalRequest, JoinCircleRequest,
    ContributeToCircleRequest, ProposalVote, AssetDetails, MemberInvestmentHistory,
    InvestmentCategory, CircleStatus, MemberRole, ProposalStatus, VoteType,
    RiskLevel, InvestmentStatus, ActivityType, BadgeRarity, AIRecommendationType,
    Priority, JoinRequestStatus, AIRecommendation, BlockchainNetwork
)
from ..core.exceptions import (
    ValidationException, BusinessRuleViolationException, 
    AccountNotFoundException, FintechException
)
from ..config.logging import get_logger

logger = get_logger(__name__)


class CollectiveCapitalService:
    """Service for managing collective capital circles and investments"""

    def __init__(self):
        # Mock data storage - in production, this would use a database
        self._circles: Dict[str, CollectiveCircle] = {}
        self._join_requests: Dict[str, JoinRequest] = {}
        self._user_circles: Dict[str, List[str]] = {}  # user_id -> circle_ids
        self._initialize_mock_data()

    def _initialize_mock_data(self):
        """Initialize mock data for development"""
        # Create sample circles
        sample_circles = [
            {
                "id": "circle_1",
                "name": "Tech Growth Circle",
                "description": "Focused on high-growth technology stocks and emerging tech companies",
                "category": InvestmentCategory.AI_TECH,
                "created_by": "user_1",
                "is_private": False,
                "max_members": 25,
                "current_members": 12,
                "total_pool_value": Decimal("125000.00"),
                "minimum_contribution": Decimal("1000.00"),
                "status": CircleStatus.ACTIVE,
                "blockchain_network": BlockchainNetwork.ETHEREUM,
                "voting_threshold": 65.0,
                "proposal_duration": 72,
                "auto_distribution": True,
                "total_returns": Decimal("18750.00"),
                "average_return": 15.2,
                "risk_score": 72.5
            },
            {
                "id": "circle_2", 
                "name": "Green Energy Collective",
                "description": "Sustainable investing in renewable energy and clean technology",
                "category": InvestmentCategory.GREEN_TECH,
                "created_by": "user_2",
                "is_private": False,
                "max_members": 50,
                "current_members": 28,
                "total_pool_value": Decimal("89000.00"),
                "minimum_contribution": Decimal("500.00"),
                "status": CircleStatus.ACTIVE,
                "blockchain_network": BlockchainNetwork.POLYGON,
                "voting_threshold": 60.0,
                "proposal_duration": 48,
                "auto_distribution": True,
                "total_returns": Decimal("12450.00"),
                "average_return": 14.8,
                "risk_score": 58.3
            },
            {
                "id": "circle_3",
                "name": "Crypto Pioneers",
                "description": "Early-stage cryptocurrency and DeFi protocol investments",
                "category": InvestmentCategory.CRYPTO,
                "created_by": "user_3",
                "is_private": True,
                "max_members": 15,
                "current_members": 8,
                "total_pool_value": Decimal("67500.00"),
                "minimum_contribution": Decimal("2500.00"),
                "status": CircleStatus.ACTIVE,
                "blockchain_network": BlockchainNetwork.BSC,
                "voting_threshold": 70.0,
                "proposal_duration": 96,
                "auto_distribution": False,
                "total_returns": Decimal("23625.00"),
                "average_return": 35.0,
                "risk_score": 89.2
            }
        ]

        for circle_data in sample_circles:
            circle = self._create_mock_circle(circle_data)
            self._circles[circle.id] = circle

    def _create_mock_circle(self, data: Dict[str, Any]) -> CollectiveCircle:
        """Create a mock circle with sample data"""
        now = datetime.utcnow()
        
        # Create mock members
        members = []
        for i in range(min(data["current_members"], 5)):  # Limit to 5 for mock data
            member = CircleMember(
                id=f"member_{data['id']}_{i}",
                user_id=f"user_{i+1}",
                user_name=f"User {i+1}",
                user_avatar=f"https://api.dicebear.com/7.x/avataaars/svg?seed=user{i+1}",
                joined_at=now - timedelta(days=random.randint(1, 90)),
                role=MemberRole.CREATOR if i == 0 else MemberRole.MEMBER,
                total_contributed=Decimal(str(random.randint(1000, 10000))),
                current_stake=Decimal(str(random.uniform(5.0, 25.0))),
                voting_power=Decimal(str(random.uniform(10.0, 30.0))),
                loyalty_points=random.randint(100, 1000),
                badges=[],
                is_active=True,
                personal_returns=Decimal(str(random.randint(100, 2000))),
                investment_history=[]
            )
            members.append(member)

        # Create mock AI recommendations
        ai_recommendations = [
            AIRecommendationModel(
                id=f"ai_rec_{data['id']}_1",
                type=AIRecommendationType.INVESTMENT_OPPORTUNITY,
                title="Strong Buy Signal for NVDA",
                description="AI analysis shows strong momentum in NVIDIA stock with 85% confidence",
                confidence=85,
                category=data["category"],
                priority=Priority.HIGH,
                action_required=True,
                created_at=now - timedelta(hours=2)
            )
        ]

        # Create mock activities
        activities = [
            CircleActivity(
                id=f"activity_{data['id']}_1",
                circle_id=data["id"],
                type=ActivityType.CIRCLE_CREATED,
                user_id=data["created_by"],
                user_name="Circle Creator",
                description=f"Created {data['name']} circle",
                created_at=now - timedelta(days=30)
            )
        ]

        return CollectiveCircle(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            category=data["category"],
            created_by=data["created_by"],
            created_at=now - timedelta(days=30),
            updated_at=now,
            is_private=data["is_private"],
            invite_code=f"INV{data['id'].upper()}" if data["is_private"] else None,
            max_members=data["max_members"],
            current_members=data["current_members"],
            total_pool_value=data["total_pool_value"],
            minimum_contribution=data["minimum_contribution"],
            status=data["status"],
            contract_address=f"0x{uuid.uuid4().hex[:40]}" if random.choice([True, False]) else None,
            blockchain_network=data["blockchain_network"],
            voting_threshold=data["voting_threshold"],
            proposal_duration=data["proposal_duration"],
            auto_distribution=data["auto_distribution"],
            total_returns=data["total_returns"],
            average_return=data["average_return"],
            risk_score=data["risk_score"],
            ai_recommendations=ai_recommendations,
            members=members,
            investments=[],
            proposals=[],
            activities=activities
        )

    async def get_circles(
        self, 
        user_id: str, 
        filters: Optional[CircleFilters] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[CollectiveCircle]:
        """Get circles with optional filtering"""
        logger.info(f"Getting circles for user {user_id} with filters: {filters}")
        
        circles = list(self._circles.values())
        
        # Apply filters
        if filters:
            if filters.category:
                circles = [c for c in circles if c.category in filters.category]
            
            if filters.min_pool_value:
                circles = [c for c in circles if c.total_pool_value >= filters.min_pool_value]
            
            if filters.max_pool_value:
                circles = [c for c in circles if c.total_pool_value <= filters.max_pool_value]
            
            if filters.status:
                circles = [c for c in circles if c.status in filters.status]
            
            if filters.member_count:
                if filters.member_count.get("min"):
                    circles = [c for c in circles if c.current_members >= filters.member_count["min"]]
                if filters.member_count.get("max"):
                    circles = [c for c in circles if c.current_members <= filters.member_count["max"]]
            
            if filters.returns:
                if filters.returns.get("min"):
                    circles = [c for c in circles if c.average_return >= filters.returns["min"]]
                if filters.returns.get("max"):
                    circles = [c for c in circles if c.average_return <= filters.returns["max"]]

        # Apply pagination
        total_circles = len(circles)
        circles = circles[offset:offset + limit]
        
        logger.info(f"Returning {len(circles)} circles out of {total_circles} total")
        return circles

    async def get_circle_by_id(self, circle_id: str, user_id: str) -> CollectiveCircle:
        """Get a specific circle by ID"""
        logger.info(f"Getting circle {circle_id} for user {user_id}")
        
        if circle_id not in self._circles:
            raise AccountNotFoundException(f"Circle {circle_id} not found")
        
        circle = self._circles[circle_id]
        
        # Check if user has access to private circles
        if circle.is_private:
            user_is_member = any(member.user_id == user_id for member in circle.members)
            if not user_is_member:
                raise FintechException("Access denied to private circle")
        
        return circle

    async def create_circle(self, user_id: str, request: CreateCircleRequest) -> CollectiveCircle:
        """Create a new collective capital circle"""
        logger.info(f"Creating new circle for user {user_id}: {request.name}")
        
        # Generate unique ID
        circle_id = f"circle_{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow()
        
        # Create the creator as the first member
        creator_member = CircleMember(
            id=f"member_{circle_id}_creator",
            user_id=user_id,
            user_name="Circle Creator",  # In production, get from user service
            user_avatar=None,
            joined_at=now,
            role=MemberRole.CREATOR,
            total_contributed=Decimal("0"),
            current_stake=Decimal("0"),
            voting_power=Decimal("100"),
            loyalty_points=0,
            badges=[],
            is_active=True,
            personal_returns=Decimal("0"),
            investment_history=[]
        )
        
        # Create initial activity
        activity = CircleActivity(
            id=f"activity_{circle_id}_created",
            circle_id=circle_id,
            type=ActivityType.CIRCLE_CREATED,
            user_id=user_id,
            user_name="Circle Creator",
            description=f"Created {request.name} circle",
            created_at=now
        )
        
        # Create the circle
        circle = CollectiveCircle(
            id=circle_id,
            name=request.name,
            description=request.description,
            category=request.category,
            created_by=user_id,
            created_at=now,
            updated_at=now,
            is_private=request.is_private,
            invite_code=f"INV{circle_id.upper()}" if request.is_private else None,
            max_members=request.max_members,
            current_members=1,
            total_pool_value=Decimal("0"),
            minimum_contribution=request.minimum_contribution,
            status=CircleStatus.ACTIVE,
            contract_address=None,
            blockchain_network=request.blockchain_network,
            voting_threshold=request.voting_threshold,
            proposal_duration=request.proposal_duration,
            auto_distribution=request.auto_distribution,
            total_returns=Decimal("0"),
            average_return=0.0,
            risk_score=50.0,
            ai_recommendations=[],
            members=[creator_member],
            investments=[],
            proposals=[],
            activities=[activity]
        )
        
        # Store the circle
        self._circles[circle_id] = circle
        
        # Update user circles mapping
        if user_id not in self._user_circles:
            self._user_circles[user_id] = []
        self._user_circles[user_id].append(circle_id)
        
        logger.info(f"Created circle {circle_id} successfully")
        return circle

    async def update_circle(
        self, 
        circle_id: str, 
        user_id: str, 
        request: UpdateCircleRequest
    ) -> CollectiveCircle:
        """Update circle settings"""
        logger.info(f"Updating circle {circle_id} by user {user_id}")
        
        if circle_id not in self._circles:
            raise AccountNotFoundException(f"Circle {circle_id} not found")
        
        circle = self._circles[circle_id]
        
        # Check if user is creator or admin
        user_member = next((m for m in circle.members if m.user_id == user_id), None)
        if not user_member or user_member.role not in [MemberRole.CREATOR, MemberRole.ADMIN]:
            raise FintechException("Only circle creators and admins can update settings")
        
        # Update fields
        if request.name is not None:
            circle.name = request.name
        if request.description is not None:
            circle.description = request.description
        if request.is_private is not None:
            circle.is_private = request.is_private
        if request.max_members is not None:
            circle.max_members = request.max_members
        if request.minimum_contribution is not None:
            circle.minimum_contribution = request.minimum_contribution
        if request.voting_threshold is not None:
            circle.voting_threshold = request.voting_threshold
        if request.proposal_duration is not None:
            circle.proposal_duration = request.proposal_duration
        if request.auto_distribution is not None:
            circle.auto_distribution = request.auto_distribution
        if request.status is not None:
            circle.status = request.status
        
        circle.updated_at = datetime.utcnow()
        
        # Add activity
        activity = CircleActivity(
            id=f"activity_{circle_id}_{uuid.uuid4().hex[:8]}",
            circle_id=circle_id,
            type=ActivityType.CIRCLE_UPDATED,
            user_id=user_id,
            user_name=user_member.user_name,
            description="Updated circle settings",
            created_at=datetime.utcnow()
        )
        circle.activities.append(activity)
        
        logger.info(f"Updated circle {circle_id} successfully")
        return circle

    async def join_circle(
        self, 
        circle_id: str, 
        user_id: str, 
        request: JoinCircleRequest
    ) -> JoinRequest:
        """Request to join a circle"""
        logger.info(f"User {user_id} requesting to join circle {circle_id}")
        
        if circle_id not in self._circles:
            raise AccountNotFoundException(f"Circle {circle_id} not found")
        
        circle = self._circles[circle_id]
        
        # Check if user is already a member
        if any(member.user_id == user_id for member in circle.members):
            raise BusinessRuleViolationException("User is already a member of this circle")
        
        # Check if circle is full
        if circle.current_members >= circle.max_members:
            raise BusinessRuleViolationException("Circle has reached maximum members")
        
        # Create join request
        join_request_id = f"join_req_{uuid.uuid4().hex[:8]}"
        join_request = JoinRequest(
            id=join_request_id,
            circle_id=circle_id,
            user_id=user_id,
            user_name="User Name",  # In production, get from user service
            user_avatar=None,
            message=request.message,
            status=JoinRequestStatus.PENDING,
            requested_at=datetime.utcnow()
        )
        
        self._join_requests[join_request_id] = join_request
        
        logger.info(f"Created join request {join_request_id}")
        return join_request

    async def get_circle_stats(self, user_id: str) -> CircleStats:
        """Get circle statistics"""
        logger.info(f"Getting circle stats for user {user_id}")
        
        all_circles = list(self._circles.values())
        user_circle_ids = self._user_circles.get(user_id, [])
        user_circles = [c for c in all_circles if c.id in user_circle_ids]
        
        total_members = sum(c.current_members for c in all_circles)
        total_pool_value = sum(c.total_pool_value for c in all_circles)
        average_return = sum(c.average_return for c in all_circles) / len(all_circles) if all_circles else 0
        
        # Find top performing circle
        top_performing = max(all_circles, key=lambda c: c.average_return) if all_circles else None
        
        # User stats
        user_total_invested = sum(
            sum(m.total_contributed for m in c.members if m.user_id == user_id)
            for c in user_circles
        )
        user_total_returns = sum(
            sum(m.personal_returns for m in c.members if m.user_id == user_id)
            for c in user_circles
        )
        
        stats = CircleStats(
            total_circles=len(all_circles),
            total_members=total_members,
            total_pool_value=total_pool_value,
            average_return=average_return,
            top_performing_circle=top_performing,
            user_circles=len(user_circles),
            user_total_invested=user_total_invested,
            user_total_returns=user_total_returns
        )
        
        logger.info(f"Generated circle stats: {stats.total_circles} circles, {stats.total_members} members")
        return stats

    async def create_proposal(
        self, 
        circle_id: str, 
        user_id: str, 
        request: CreateProposalRequest
    ) -> InvestmentProposal:
        """Create an investment proposal"""
        logger.info(f"Creating proposal for circle {circle_id} by user {user_id}")
        
        if circle_id not in self._circles:
            raise AccountNotFoundException(f"Circle {circle_id} not found")
        
        circle = self._circles[circle_id]
        
        # Check if user is a member
        user_member = next((m for m in circle.members if m.user_id == user_id), None)
        if not user_member:
            raise FintechException("Only circle members can create proposals")
        
        # Generate proposal ID and create asset details
        proposal_id = f"proposal_{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow()
        
        asset_details = request.asset_details or AssetDetails(
            symbol=request.asset_symbol,
            name=request.asset_name,
            type=request.investment_type,
            description=f"Investment in {request.asset_name}"
        )
        
        # Calculate required votes (based on voting threshold)
        total_voting_power = sum(m.voting_power for m in circle.members if m.is_active)
        required_votes = int((circle.voting_threshold / 100) * total_voting_power)
        
        # Generate AI analysis (mock)
        ai_score = random.uniform(60, 95)
        ai_recommendation = AIRecommendation.APPROVE if ai_score > 75 else AIRecommendation.CAUTION
        ai_analysis = f"AI analysis shows {ai_score:.1f}% confidence in this investment opportunity based on market trends and risk assessment."
        
        proposal = InvestmentProposal(
            id=proposal_id,
            circle_id=circle_id,
            proposed_by=user_id,
            proposer_name=user_member.user_name,
            title=request.title,
            description=request.description,
            investment_type=request.investment_type,
            target_amount=request.target_amount,
            minimum_amount=request.minimum_amount,
            expected_return=request.expected_return,
            risk_level=request.risk_level,
            duration=request.duration,
            asset_details=asset_details,
            market_analysis=request.market_analysis,
            risk_analysis=request.risk_analysis,
            exit_strategy=request.exit_strategy,
            voting_deadline=now + timedelta(hours=circle.proposal_duration),
            votes=[],
            current_votes={"yes": 0, "no": 0, "abstain": 0},
            required_votes=required_votes,
            status=ProposalStatus.PENDING,
            ai_score=ai_score,
            ai_recommendation=ai_recommendation,
            ai_analysis=ai_analysis,
            created_at=now,
            updated_at=now
        )
        
        # Add to circle
        circle.proposals.append(proposal)
        
        # Add activity
        activity = CircleActivity(
            id=f"activity_{circle_id}_{uuid.uuid4().hex[:8]}",
            circle_id=circle_id,
            type=ActivityType.PROPOSAL_CREATED,
            user_id=user_id,
            user_name=user_member.user_name,
            description=f"Created proposal: {request.title}",
            created_at=now
        )
        circle.activities.append(activity)
        
        logger.info(f"Created proposal {proposal_id} successfully")
        return proposal

    async def vote_on_proposal(
        self, 
        circle_id: str, 
        proposal_id: str, 
        user_id: str, 
        request: VoteOnProposalRequest
    ) -> InvestmentProposal:
        """Vote on an investment proposal"""
        logger.info(f"User {user_id} voting on proposal {proposal_id}")
        
        if circle_id not in self._circles:
            raise AccountNotFoundException(f"Circle {circle_id} not found")
        
        circle = self._circles[circle_id]
        
        # Find proposal
        proposal = next((p for p in circle.proposals if p.id == proposal_id), None)
        if not proposal:
            raise AccountNotFoundException(f"Proposal {proposal_id} not found")
        
        # Check if user is a member
        user_member = next((m for m in circle.members if m.user_id == user_id), None)
        if not user_member:
            raise FintechException("Only circle members can vote")
        
        # Check if proposal is still open for voting
        if proposal.status != ProposalStatus.PENDING:
            raise BusinessRuleViolationException("Proposal is no longer open for voting")
        
        if datetime.utcnow() > proposal.voting_deadline:
            raise BusinessRuleViolationException("Voting deadline has passed")
        
        # Check if user already voted
        existing_vote = next((v for v in proposal.votes if v.voter_id == user_id), None)
        if existing_vote:
            raise BusinessRuleViolationException("User has already voted on this proposal")
        
        # Create vote
        vote = ProposalVote(
            id=f"vote_{uuid.uuid4().hex[:8]}",
            proposal_id=proposal_id,
            voter_id=user_id,
            voter_name=user_member.user_name,
            vote=request.vote,
            voting_power=user_member.voting_power,
            comment=request.comment,
            voted_at=datetime.utcnow()
        )
        
        proposal.votes.append(vote)
        
        # Update vote counts
        vote_key = request.vote.value.lower()
        proposal.current_votes[vote_key] += int(user_member.voting_power)
        
        # Check if proposal should be approved/rejected
        total_votes = sum(proposal.current_votes.values())
        if total_votes >= proposal.required_votes:
            yes_percentage = (proposal.current_votes["yes"] / total_votes) * 100
            if yes_percentage >= circle.voting_threshold:
                proposal.status = ProposalStatus.APPROVED
            else:
                proposal.status = ProposalStatus.REJECTED
        
        proposal.updated_at = datetime.utcnow()
        
        # Add activity
        activity = CircleActivity(
            id=f"activity_{circle_id}_{uuid.uuid4().hex[:8]}",
            circle_id=circle_id,
            type=ActivityType.PROPOSAL_VOTED,
            user_id=user_id,
            user_name=user_member.user_name,
            description=f"Voted {request.vote.value} on proposal: {proposal.title}",
            created_at=datetime.utcnow()
        )
        circle.activities.append(activity)
        
        logger.info(f"Vote recorded successfully for proposal {proposal_id}")
        return proposal

    async def get_ai_recommendations(
        self, 
        circle_id: str, 
        user_id: str
    ) -> List[AIRecommendationModel]:
        """Get AI recommendations for a circle"""
        logger.info(f"Getting AI recommendations for circle {circle_id}")
        
        if circle_id not in self._circles:
            raise AccountNotFoundException(f"Circle {circle_id} not found")
        
        circle = self._circles[circle_id]
        
        # Check if user is a member
        user_member = next((m for m in circle.members if m.user_id == user_id), None)
        if not user_member:
            raise FintechException("Only circle members can view AI recommendations")
        
        return circle.ai_recommendations

    async def get_circle_activities(
        self, 
        circle_id: str, 
        user_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[CircleActivity]:
        """Get circle activities"""
        logger.info(f"Getting activities for circle {circle_id}")
        
        if circle_id not in self._circles:
            raise AccountNotFoundException(f"Circle {circle_id} not found")
        
        circle = self._circles[circle_id]
        
        # Check if user has access
        if circle.is_private:
            user_is_member = any(member.user_id == user_id for member in circle.members)
            if not user_is_member:
                raise FintechException("Access denied to private circle")
        
        # Sort activities by date (newest first) and apply pagination
        activities = sorted(circle.activities, key=lambda a: a.created_at, reverse=True)
        return activities[offset:offset + limit]

    async def health_check(self) -> Dict[str, Any]:
        """Health check for collective capital service"""
        return {
            "service": "collective_capital_service",
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "circles_count": len(self._circles),
            "join_requests_count": len(self._join_requests)
        }
