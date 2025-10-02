"""
Collective Capital models for investment circles and group investing functionality.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from decimal import Decimal
from enum import Enum


class InvestmentCategory(str, Enum):
    """Investment categories for collective capital circles"""
    STOCKS = "STOCKS"
    CRYPTO = "CRYPTO"
    REAL_ESTATE = "REAL_ESTATE"
    BONDS = "BONDS"
    COMMODITIES = "COMMODITIES"
    STARTUPS = "STARTUPS"
    GREEN_TECH = "GREEN_TECH"
    AI_TECH = "AI_TECH"
    HEALTHCARE = "HEALTHCARE"
    ENERGY = "ENERGY"


class BlockchainNetwork(str, Enum):
    """Supported blockchain networks"""
    ETHEREUM = "ETHEREUM"
    POLYGON = "POLYGON"
    BSC = "BSC"


class CircleStatus(str, Enum):
    """Circle status options"""
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    CLOSED = "CLOSED"
    PENDING = "PENDING"


class MemberRole(str, Enum):
    """Member roles in a circle"""
    CREATOR = "CREATOR"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


class ProposalStatus(str, Enum):
    """Investment proposal status"""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    EXECUTED = "EXECUTED"


class VoteType(str, Enum):
    """Vote types for proposals"""
    YES = "YES"
    NO = "NO"
    ABSTAIN = "ABSTAIN"


class RiskLevel(str, Enum):
    """Risk levels for investments"""
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class InvestmentStatus(str, Enum):
    """Investment status"""
    ACTIVE = "ACTIVE"
    SOLD = "SOLD"
    PARTIAL_SOLD = "PARTIAL_SOLD"


class ActivityType(str, Enum):
    """Activity types in circles"""
    MEMBER_JOINED = "MEMBER_JOINED"
    MEMBER_LEFT = "MEMBER_LEFT"
    PROPOSAL_CREATED = "PROPOSAL_CREATED"
    PROPOSAL_VOTED = "PROPOSAL_VOTED"
    INVESTMENT_EXECUTED = "INVESTMENT_EXECUTED"
    RETURNS_DISTRIBUTED = "RETURNS_DISTRIBUTED"
    CIRCLE_CREATED = "CIRCLE_CREATED"
    CIRCLE_UPDATED = "CIRCLE_UPDATED"


class BadgeRarity(str, Enum):
    """Loyalty badge rarity levels"""
    COMMON = "COMMON"
    RARE = "RARE"
    EPIC = "EPIC"
    LEGENDARY = "LEGENDARY"


class AIRecommendationType(str, Enum):
    """AI recommendation types"""
    INVESTMENT_OPPORTUNITY = "INVESTMENT_OPPORTUNITY"
    RISK_WARNING = "RISK_WARNING"
    PORTFOLIO_OPTIMIZATION = "PORTFOLIO_OPTIMIZATION"
    MARKET_INSIGHT = "MARKET_INSIGHT"


class Priority(str, Enum):
    """Priority levels"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class JoinRequestStatus(str, Enum):
    """Join request status"""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AIRecommendation(str, Enum):
    """AI recommendation actions"""
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    CAUTION = "CAUTION"


# Base Models
class LoyaltyBadge(BaseModel):
    """Loyalty badge model"""
    id: str
    name: str
    description: str
    icon: str
    color: str
    earned_at: datetime
    rarity: BadgeRarity


class MemberInvestmentHistory(BaseModel):
    """Member investment history entry"""
    investment_id: str
    amount: Decimal
    returns: Decimal
    date: datetime


class AssetDetails(BaseModel):
    """Asset details for investments"""
    symbol: str
    name: str
    type: InvestmentCategory
    exchange: Optional[str] = None
    sector: Optional[str] = None
    market_cap: Optional[Decimal] = None
    pe_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    beta: Optional[float] = None
    description: Optional[str] = None
    fundamentals: Optional[Dict[str, Any]] = None


class AIRecommendationModel(BaseModel):
    """AI recommendation model"""
    id: str
    type: AIRecommendationType
    title: str
    description: str
    confidence: int = Field(..., ge=0, le=100)
    category: InvestmentCategory
    priority: Priority
    action_required: bool
    created_at: datetime
    expires_at: Optional[datetime] = None


class CircleMember(BaseModel):
    """Circle member model"""
    id: str
    user_id: str
    user_name: str
    user_avatar: Optional[str] = None
    joined_at: datetime
    role: MemberRole
    total_contributed: Decimal
    current_stake: Decimal  # Percentage of total pool
    voting_power: Decimal
    loyalty_points: int
    badges: List[LoyaltyBadge] = []
    is_active: bool = True
    personal_returns: Decimal
    investment_history: List[MemberInvestmentHistory] = []


class ProposalVote(BaseModel):
    """Proposal vote model"""
    id: str
    proposal_id: str
    voter_id: str
    voter_name: str
    vote: VoteType
    voting_power: Decimal
    comment: Optional[str] = None
    voted_at: datetime


class CircleInvestment(BaseModel):
    """Circle investment model"""
    id: str
    circle_id: str
    proposal_id: str
    asset_type: InvestmentCategory
    asset_symbol: str
    asset_name: str
    total_amount: Decimal
    purchase_price: Decimal
    current_price: Decimal
    quantity: Decimal
    current_value: Decimal
    total_return: Decimal
    return_percentage: float
    transaction_hash: Optional[str] = None
    block_number: Optional[int] = None
    last_distribution: Optional[datetime] = None
    total_distributed: Decimal
    status: InvestmentStatus
    purchase_date: datetime
    updated_at: datetime


class InvestmentProposal(BaseModel):
    """Investment proposal model"""
    id: str
    circle_id: str
    proposed_by: str
    proposer_name: str
    title: str
    description: str
    investment_type: InvestmentCategory
    target_amount: Decimal
    minimum_amount: Decimal
    expected_return: float
    risk_level: RiskLevel
    duration: int  # months
    asset_details: AssetDetails
    market_analysis: str
    risk_analysis: str
    exit_strategy: str
    voting_deadline: datetime
    votes: List[ProposalVote] = []
    current_votes: Dict[str, int] = Field(default_factory=lambda: {"yes": 0, "no": 0, "abstain": 0})
    required_votes: int
    status: ProposalStatus
    ai_score: float = Field(..., ge=0, le=100)
    ai_recommendation: AIRecommendation
    ai_analysis: str
    created_at: datetime
    updated_at: datetime


class CircleActivity(BaseModel):
    """Circle activity model"""
    id: str
    circle_id: str
    type: ActivityType
    user_id: str
    user_name: str
    description: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime


class CollectiveCircle(BaseModel):
    """Main collective capital circle model"""
    id: str
    name: str
    description: str
    category: InvestmentCategory
    created_by: str
    created_at: datetime
    updated_at: datetime
    is_private: bool
    invite_code: Optional[str] = None
    max_members: int
    current_members: int
    total_pool_value: Decimal
    minimum_contribution: Decimal
    status: CircleStatus
    contract_address: Optional[str] = None
    blockchain_network: BlockchainNetwork
    voting_threshold: float  # Percentage needed to approve investment
    proposal_duration: int  # Hours for voting
    auto_distribution: bool
    total_returns: Decimal
    average_return: float
    risk_score: float = Field(..., ge=0, le=100)
    ai_recommendations: List[AIRecommendationModel] = []
    members: List[CircleMember] = []
    investments: List[CircleInvestment] = []
    proposals: List[InvestmentProposal] = []
    activities: List[CircleActivity] = []


class JoinRequest(BaseModel):
    """Join request model"""
    id: str
    circle_id: str
    user_id: str
    user_name: str
    user_avatar: Optional[str] = None
    message: str
    status: JoinRequestStatus
    requested_at: datetime
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None


# Request/Response Models
class CircleFilters(BaseModel):
    """Filters for circle search"""
    category: Optional[List[InvestmentCategory]] = None
    min_pool_value: Optional[Decimal] = None
    max_pool_value: Optional[Decimal] = None
    risk_level: Optional[List[str]] = None
    member_count: Optional[Dict[str, int]] = None
    returns: Optional[Dict[str, float]] = None
    status: Optional[List[CircleStatus]] = None


class CircleStats(BaseModel):
    """Circle statistics"""
    total_circles: int
    total_members: int
    total_pool_value: Decimal
    average_return: float
    top_performing_circle: Optional[CollectiveCircle] = None
    user_circles: int
    user_total_invested: Decimal
    user_total_returns: Decimal


class CreateCircleRequest(BaseModel):
    """Request to create a new circle"""
    name: str = Field(..., min_length=3, max_length=100)
    description: str = Field(..., min_length=10, max_length=1000)
    category: InvestmentCategory
    is_private: bool = False
    max_members: int = Field(default=50, ge=2, le=1000)
    minimum_contribution: Decimal = Field(..., gt=0)
    blockchain_network: BlockchainNetwork = BlockchainNetwork.POLYGON
    voting_threshold: float = Field(default=60.0, ge=50.0, le=100.0)
    proposal_duration: int = Field(default=72, ge=24, le=168)  # 24 hours to 1 week
    auto_distribution: bool = True


class UpdateCircleRequest(BaseModel):
    """Request to update circle settings"""
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = Field(None, min_length=10, max_length=1000)
    is_private: Optional[bool] = None
    max_members: Optional[int] = Field(None, ge=2, le=1000)
    minimum_contribution: Optional[Decimal] = Field(None, gt=0)
    voting_threshold: Optional[float] = Field(None, ge=50.0, le=100.0)
    proposal_duration: Optional[int] = Field(None, ge=24, le=168)
    auto_distribution: Optional[bool] = None
    status: Optional[CircleStatus] = None


class CreateProposalRequest(BaseModel):
    """Request to create investment proposal"""
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=20, max_length=2000)
    investment_type: InvestmentCategory
    target_amount: Decimal = Field(..., gt=0)
    minimum_amount: Decimal = Field(..., gt=0)
    expected_return: float = Field(..., ge=0)
    risk_level: RiskLevel
    duration: int = Field(..., ge=1, le=120)  # 1 to 120 months
    asset_symbol: str = Field(..., min_length=1, max_length=20)
    asset_name: str = Field(..., min_length=1, max_length=100)
    market_analysis: str = Field(..., min_length=50, max_length=2000)
    risk_analysis: str = Field(..., min_length=50, max_length=2000)
    exit_strategy: str = Field(..., min_length=20, max_length=1000)
    asset_details: Optional[AssetDetails] = None

    @validator('minimum_amount')
    def minimum_amount_must_be_less_than_target(cls, v, values):
        if 'target_amount' in values and v >= values['target_amount']:
            raise ValueError('minimum_amount must be less than target_amount')
        return v


class VoteOnProposalRequest(BaseModel):
    """Request to vote on proposal"""
    vote: VoteType
    comment: Optional[str] = Field(None, max_length=500)


class JoinCircleRequest(BaseModel):
    """Request to join a circle"""
    message: str = Field(..., min_length=10, max_length=500)
    initial_contribution: Optional[Decimal] = Field(None, gt=0)


class ContributeToCircleRequest(BaseModel):
    """Request to contribute to circle"""
    amount: Decimal = Field(..., gt=0)
    payment_method_id: Optional[str] = None


# Response Models
class CircleResponse(BaseModel):
    """Circle response model"""
    success: bool
    message: str
    data: Optional[CollectiveCircle] = None


class CircleListResponse(BaseModel):
    """Circle list response model"""
    success: bool
    message: str
    data: Optional[List[CollectiveCircle]] = None
    total_count: int
    filters_applied: Optional[CircleFilters] = None


class CircleStatsResponse(BaseModel):
    """Circle stats response model"""
    success: bool
    message: str
    data: Optional[CircleStats] = None


class ProposalResponse(BaseModel):
    """Proposal response model"""
    success: bool
    message: str
    data: Optional[InvestmentProposal] = None


class ProposalListResponse(BaseModel):
    """Proposal list response model"""
    success: bool
    message: str
    data: Optional[List[InvestmentProposal]] = None
    total_count: int


class JoinRequestResponse(BaseModel):
    """Join request response model"""
    success: bool
    message: str
    data: Optional[JoinRequest] = None


class JoinRequestListResponse(BaseModel):
    """Join request list response model"""
    success: bool
    message: str
    data: Optional[List[JoinRequest]] = None
    total_count: int


class AIRecommendationResponse(BaseModel):
    """AI recommendation response model"""
    success: bool
    message: str
    data: Optional[List[AIRecommendationModel]] = None


class MemberResponse(BaseModel):
    """Member response model"""
    success: bool
    message: str
    data: Optional[CircleMember] = None


class ActivityResponse(BaseModel):
    """Activity response model"""
    success: bool
    message: str
    data: Optional[List[CircleActivity]] = None
    total_count: int
