"""
Daily reconciliation: what Hoardrun owes each customer, and whether the ledger explains it.

A bank partner holds customer money in one pooled "for the benefit of" (FBO) account and
expects owner-level records reconciled every day: the sum of what each customer is owed must
equal that account's balance. This report gives both, plus two integrity checks:

- every cash account's available balance equals its balance less card holds;
- every cash account's balance is explained by its transactions (inbound completed, less
  outbound money that left it).

Run from fintech_backend:

    python -m app.services.reconciliation                       # totals and checks
    python -m app.services.reconciliation --fbo-balance 1234.56 # compare with the bank's figure
    python -m app.services.reconciliation --csv owners.csv      # one row per customer

Exit code 1 means something didn't reconcile.
"""

import argparse
import csv
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database.models import (
    Account, AccountStatusEnum, Transaction, TransactionDirectionEnum, TransactionStatusEnum, TransactionTypeEnum, User,
)

CENT = Decimal("0.01")
ZERO = Decimal("0")
# Outbound money that left the account even though the transaction isn't "completed":
# a withdrawal on its way (pending), or one that failed and was refunded by a separate entry.
LEFT_ANYWAY = {TransactionStatusEnum.PENDING, TransactionStatusEnum.FAILED, TransactionStatusEnum.REVERSED}


@dataclass
class Owner:
    user_id: str
    email: str
    cash: Decimal = ZERO
    card_holds: Decimal = ZERO
    savings: Decimal = ZERO
    pooled_investments: Decimal = ZERO
    at_broker: Decimal = ZERO

    @property
    def held_by_hoardrun(self) -> Decimal:
        # Money in Hoardrun's pooled bank account for this person (card holds are still in their cash)
        return self.cash + self.savings + self.pooled_investments


@dataclass
class Report:
    owners: List[Owner] = field(default_factory=list)
    problems: List[str] = field(default_factory=list)

    def total(self, name: str) -> Decimal:
        return sum((getattr(o, name) for o in self.owners), ZERO)


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT)


def _sum_by_user(db: Session, column, user_column, *filters) -> Dict[str, Decimal]:
    rows = db.query(user_column, func.coalesce(func.sum(column), 0)).filter(*filters).group_by(user_column).all()
    return {user_id: _money(total) for user_id, total in rows}


def explained_balance(db: Session, account: Account) -> Decimal:
    """The balance the account's transactions add up to."""
    inbound = db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.account_id == account.id, Transaction.direction == TransactionDirectionEnum.INBOUND,
        Transaction.status == TransactionStatusEnum.COMPLETED).scalar()
    completed_out = db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.account_id == account.id, Transaction.direction == TransactionDirectionEnum.OUTBOUND,
        Transaction.status == TransactionStatusEnum.COMPLETED).scalar()
    # Bank withdrawals take the cash when they start, whatever happens to them after
    withdrawals_out = db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.account_id == account.id, Transaction.direction == TransactionDirectionEnum.OUTBOUND,
        Transaction.transaction_type == TransactionTypeEnum.WITHDRAWAL, Transaction.status.in_(LEFT_ANYWAY)).scalar()
    return _money(inbound) - _money(completed_out) - _money(withdrawals_out)


def build(db: Session) -> Report:
    from ..api.v1.brokerage import BrokerageAccount
    from ..api.v1.savings_store import AutoSavePlan, FixedDeposit, SavingsGoal
    from ..database.circle_models import CircleMember
    from ..database.market_models import MarketPosition
    from ..database.venture_models import FundShareOrder

    report = Report()
    goals = _sum_by_user(db, SavingsGoal.current_amount, SavingsGoal.user_id)
    deposits = _sum_by_user(db, FixedDeposit.principal, FixedDeposit.user_id, FixedDeposit.status == "active")
    autosave = _sum_by_user(db, AutoSavePlan.saved_total, AutoSavePlan.user_id)
    funds = _sum_by_user(db, FundShareOrder.amount, FundShareOrder.user_id)
    circles = _sum_by_user(db, CircleMember.contributed, CircleMember.user_id)
    positions = _sum_by_user(db, MarketPosition.cost_basis, MarketPosition.user_id, MarketPosition.quantity > 0)
    broker_cash = _sum_by_user(db, BrokerageAccount.uninvested_cash, BrokerageAccount.user_id)
    at_alpaca = {row[0] for row in db.query(BrokerageAccount.user_id).all()}

    accounts_by_user: Dict[str, List[Account]] = {}
    for account in db.query(Account).filter(Account.status == AccountStatusEnum.ACTIVE).all():
        accounts_by_user.setdefault(account.user_id, []).append(account)
        current, available = _money(account.current_balance), _money(account.available_balance)
        reserved, pending = _money(account.reserved_balance), _money(account.pending_balance)
        if available != current - reserved - pending:
            report.problems.append(f"Account {account.id}: available {available} isn't balance {current} less holds {reserved + pending}")
        if available < 0 or current < 0:
            report.problems.append(f"Account {account.id}: negative balance (balance {current}, available {available})")
        explained = explained_balance(db, account)
        if explained != current:
            report.problems.append(f"Account {account.id}: balance {current} but its transactions add up to {explained}")

    users = {u.id: u.email for u in db.query(User.id, User.email).all()}
    everyone = set(accounts_by_user) | set(goals) | set(deposits) | set(autosave) | set(funds) | set(circles) | set(positions) | set(broker_cash)
    for user_id in sorted(everyone):
        owner = Owner(user_id=user_id, email=users.get(user_id, "?"))
        for account in accounts_by_user.get(user_id, []):
            owner.cash += _money(account.current_balance)
            owner.card_holds += _money(account.reserved_balance)
        owner.savings = goals.get(user_id, ZERO) + deposits.get(user_id, ZERO) + autosave.get(user_id, ZERO)
        owner.pooled_investments = funds.get(user_id, ZERO) + circles.get(user_id, ZERO)
        # With an Alpaca account, ETFs and crypto are held there; otherwise they're on Hoardrun's own books
        if user_id in at_alpaca:
            owner.at_broker = positions.get(user_id, ZERO) + broker_cash.get(user_id, ZERO)
        else:
            owner.pooled_investments += positions.get(user_id, ZERO)
        report.owners.append(owner)
    return report


def write_csv(report: Report, path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["user_id", "email", "cash", "card_holds_within_cash", "savings", "pooled_investments",
                         "held_by_hoardrun", "at_broker"])
        for o in report.owners:
            writer.writerow([o.user_id, o.email, o.cash, o.card_holds, o.savings, o.pooled_investments, o.held_by_hoardrun, o.at_broker])


def summary(report: Report, fbo_balance: Optional[Decimal] = None) -> List[str]:
    held = report.total("held_by_hoardrun")
    lines = [
        f"Customers: {len(report.owners)}",
        f"Cash:                {report.total('cash'):>14,.2f}  (of which card holds {report.total('card_holds'):,.2f})",
        f"Savings:             {report.total('savings'):>14,.2f}",
        f"Pooled investments:  {report.total('pooled_investments'):>14,.2f}",
        f"Owed, held by Hoardrun: {held:>11,.2f}  <- should equal the FBO account",
        f"At the broker:       {report.total('at_broker'):>14,.2f}  (held by Alpaca, not in the FBO account)",
    ]
    if fbo_balance is not None:
        gap = (fbo_balance - held).quantize(CENT)
        lines.append(f"FBO account balance: {fbo_balance:>14,.2f}  difference {gap:+,.2f}"
                     + ("" if gap == 0 else "  <- investigate before end of day"))
    lines.append("Checks: " + ("all accounts reconcile" if not report.problems else f"{len(report.problems)} problem(s)"))
    lines.extend(f"  - {problem}" for problem in report.problems[:50])
    return lines


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Daily reconciliation of what Hoardrun owes customers")
    parser.add_argument("--fbo-balance", type=Decimal, help="The bank's figure for the FBO account, to compare")
    parser.add_argument("--csv", help="Write one row per customer (owner-level records) to this file")
    args = parser.parse_args(argv)

    from ..database.config import SessionLocal
    from ..database import registry  # noqa: F401 - every table

    with SessionLocal() as db:
        report = build(db)
    if args.csv:
        write_csv(report, args.csv)
    print("\n".join(summary(report, args.fbo_balance)))
    mismatch = args.fbo_balance is not None and (args.fbo_balance - report.total("held_by_hoardrun")).quantize(CENT) != 0
    return 1 if report.problems or mismatch else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
