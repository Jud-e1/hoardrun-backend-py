"""
What a user owns across Hoardrun, from the database: cash, savings and investments.

Money moved between them never changes the total, so net worth stays right when someone
saves into a goal, locks a fixed deposit or buys into a fund. Investments are valued at what
was paid for them; live market prices aren't fetched here.
"""

from decimal import Decimal
from typing import Dict

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database.circle_models import CircleInvestment, CircleMember
from ..database.market_models import MarketPosition
from ..database.models import Account, AccountStatusEnum
from ..database.venture_models import FundShareOrder

ZERO = Decimal("0")


def _sum(query) -> Decimal:
    return Decimal(str(query.scalar() or 0))


def wealth(db: Session, user_id: str) -> Dict[str, Decimal]:
    # Imported here: the savings module registers its tables with the app's routers
    from ..api.v1.savings_store import AutoSavePlan, FixedDeposit, SavingsGoal

    cash = _sum(db.query(func.sum(Account.current_balance)).filter(
        Account.user_id == user_id, Account.status == AccountStatusEnum.ACTIVE, Account.currency == "USD"))
    available = _sum(db.query(func.sum(Account.available_balance)).filter(
        Account.user_id == user_id, Account.status == AccountStatusEnum.ACTIVE, Account.currency == "USD"))

    goals = _sum(db.query(func.sum(SavingsGoal.current_amount)).filter(SavingsGoal.user_id == user_id))
    deposits = _sum(db.query(func.sum(FixedDeposit.principal)).filter(FixedDeposit.user_id == user_id, FixedDeposit.status == "active"))
    auto_save = _sum(db.query(func.sum(AutoSavePlan.saved_total)).filter(AutoSavePlan.user_id == user_id))
    savings = goals + deposits + auto_save

    from ..api.v1.brokerage import BrokerageAccount
    markets = _sum(db.query(func.sum(MarketPosition.cost_basis)).filter(MarketPosition.user_id == user_id, MarketPosition.quantity > 0))
    # Cash sitting in the investing account at Alpaca (an order not filled yet, proceeds not swept yet)
    markets += _sum(db.query(func.sum(BrokerageAccount.uninvested_cash)).filter(BrokerageAccount.user_id == user_id))
    funds = _sum(db.query(func.sum(FundShareOrder.amount)).filter(FundShareOrder.user_id == user_id))
    circles = _sum(db.query(func.sum(CircleMember.contributed)).filter(CircleMember.user_id == user_id))
    # Money members put into investments their circle voted for
    circles += _sum(db.query(func.sum(CircleInvestment.amount)).filter(CircleInvestment.user_id == user_id))
    investments = markets + funds + circles

    return {
        "cash": cash,
        "available": available,
        "savings": savings,
        "savings_goals": goals,
        "fixed_deposits": deposits,
        "auto_save": auto_save,
        "investments": investments,
        "markets": markets,
        "venture_funds": funds,
        "circles": circles,
        "net_worth": cash + savings + investments,
    }
