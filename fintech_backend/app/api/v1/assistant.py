"""
Hoardrun AI: a chat assistant that knows the app and the signed-in person's own numbers.

It reads the user's accounts, recent transactions, market positions and circles, then
answers with Claude. It explains, guides and points to the right page; it never moves money.
"""

import logging
import os
from decimal import Decimal
from typing import List, Literal, Optional

import anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...auth.dependencies import get_current_user_id
from ...database.circle_models import CircleMember, InvestmentCircle
from ...database.config import get_db
from ...database.market_models import MarketPosition
from ...database.models import Account, AccountStatusEnum, Transaction, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assistant", tags=["Assistant"])

MODEL = "claude-opus-5-5"
MAX_TURNS = 20

# Stable instructions first, so the prefix can be cached; the user's numbers follow in a second block.
SYSTEM_PROMPT = """You are Hoardrun AI, the assistant inside Hoardrun, a US money app for saving, sending and investing.

You help the person you're talking to understand their money and use the app. You can see a snapshot of their own accounts and activity below the line "Their numbers". Use it to make answers specific to them; never invent numbers that aren't there. If something they ask about isn't in the snapshot, say you can't see it.

What you do:
- Explain how to do things in Hoardrun, step by step, and link to the page. Write links as markdown with the app path, for example [Open Savings](/savings).
- Help them plan saving: goals, monthly amounts, how long a goal will take, fixed deposits and auto-save.
- Teach investing in plain words: diversification, risk, fees, time horizons, ETFs, crypto volatility, group investing in Circles, venture funds.
- Look at their spending and suggest realistic changes.

Limits:
- You can't move money, place orders or change settings. Tell them where to do it themselves.
- You're not a licensed financial adviser. Give education and general guidance, not instructions to buy or sell a particular security, and say so briefly when they ask what to buy.
- Never ask for passwords, card numbers, PINs or one-time codes. If they share one, tell them not to.

Pages in the app:
/home (balance and quick actions), /savings (goals, fixed deposits, auto-save), /budget (budget categories), /transactions (history and search), /analytics (income and spending charts), /send-money (send to Hoardrun users or banks), /cards (cards, lock, details), /investment (investing hub), /crypto and /etfs (live markets), /circles (invest as a group and vote), /venture-capital (buy shares in venture funds), /investment-opportunities (company listings), /startupregistration (list a company), /security (password and two-factor), /settings, /profile, /help.
Money is added with the Add Money button (card or bank, through Paystack's secure checkout).

Style: warm, short and direct, like a good banker who's also a friend. Use short paragraphs or a few bullets. Amounts in US dollars."""


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    messages: List[ChatTurn] = Field(min_length=1)


def money(value) -> str:
    return f"${Decimal(str(value or 0)):,.2f}"


def build_snapshot(db: Session, user_id: str) -> str:
    """The user's own numbers, as plain text for the model. Each part is optional."""
    lines: List[str] = []

    user = db.get(User, user_id)
    if user:
        lines.append(f"Name: {user.first_name}")

    accounts = (
        db.query(Account)
        .filter(Account.user_id == user_id, Account.status == AccountStatusEnum.ACTIVE)
        .all()
    )
    if accounts:
        total = sum(Decimal(str(a.available_balance or 0)) for a in accounts)
        lines.append(f"Accounts (available total {money(total)}):")
        for account in accounts:
            kind = getattr(account.account_type, "value", account.account_type)
            lines.append(f"- {account.account_name} ({kind}, {account.currency}): {money(account.available_balance)} available")
    else:
        lines.append("Accounts: none yet, so their balance is $0.")

    recent = (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id)
        .order_by(Transaction.created_at.desc())
        .limit(15)
        .all()
    )
    if recent:
        lines.append("Recent transactions (newest first):")
        for tx in recent:
            direction = getattr(tx.direction, "value", tx.direction)
            category = getattr(tx.merchant_category, "value", tx.merchant_category) or "other"
            when = tx.created_at.strftime("%Y-%m-%d") if tx.created_at else "unknown date"
            lines.append(f"- {when} {direction} {money(tx.amount)} {tx.description} [{category}]")
    else:
        lines.append("Recent transactions: none yet.")

    positions = db.query(MarketPosition).filter(MarketPosition.user_id == user_id, MarketPosition.quantity > 0).all()
    if positions:
        lines.append("Market positions:")
        for p in positions:
            lines.append(f"- {p.asset_type} {p.symbol}: {Decimal(str(p.quantity)).normalize()} units, cost {money(p.cost_basis)}")

    circles = (
        db.query(CircleMember, InvestmentCircle)
        .join(InvestmentCircle, InvestmentCircle.id == CircleMember.circle_id)
        .filter(CircleMember.user_id == user_id)
        .all()
    )
    if circles:
        lines.append("Investment circles:")
        for member, circle in circles:
            total = Decimal(str(circle.total_contributed or 0))
            share = (Decimal(str(member.contributed or 0)) / total * 100) if total else Decimal(0)
            lines.append(f"- {circle.name}: contributed {money(member.contributed)} ({share:.1f}% stake)")

    lines.append("Savings goals and budgets aren't in this snapshot; ask them or point them to /savings and /budget.")
    return "\n".join(lines)


_client: Optional[anthropic.AsyncAnthropic] = None


def get_client() -> anthropic.AsyncAnthropic:
    """One client for the process. Raises 503 when the server has no Anthropic credentials."""
    global _client
    if _client is None:
        try:
            # The backend's settings live in .env, which isn't always exported to the environment
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        if not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Hoardrun AI isn't set up yet. Add ANTHROPIC_API_KEY to the backend settings.",
            )
        _client = anthropic.AsyncAnthropic(timeout=60.0)
    return _client


@router.post("/chat")
async def chat(
    request: ChatRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    turns = request.messages[-MAX_TURNS:]
    # The API needs the conversation to open with the user
    while turns and turns[0].role != "user":
        turns = turns[1:]
    if not turns or turns[-1].role != "user":
        raise HTTPException(status_code=400, detail="The last message must be from you.")

    client = get_client()
    snapshot = build_snapshot(db, user_id)

    try:
        response = await client.beta.messages.create(
            model=MODEL,
            max_tokens=4000,
            # Chat answers don't need deep reasoning; low effort keeps replies quick
            output_config={"effort": "low"},
            # If a request is declined by a safety classifier, retry it server-side on Anthropic's recommended model
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=[
                {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": f"Their numbers:\n{snapshot}"},
            ],
            messages=[{"role": t.role, "content": t.content} for t in turns],
        )
    except anthropic.AuthenticationError:
        logger.error("Hoardrun AI: Anthropic rejected the API key")
        raise HTTPException(status_code=503, detail="Hoardrun AI isn't available right now: the server's AI key was rejected.")
    except anthropic.RateLimitError:
        raise HTTPException(status_code=429, detail="Hoardrun AI is busy. Try again in a moment.")
    except anthropic.BadRequestError as error:
        logger.error("Hoardrun AI bad request: %s", error.message)
        raise HTTPException(status_code=502, detail="Hoardrun AI couldn't answer that. Try rephrasing.")
    except anthropic.APIStatusError as error:
        logger.error("Hoardrun AI API error %s: %s", error.status_code, error.message)
        raise HTTPException(status_code=502, detail="Hoardrun AI isn't responding. Try again shortly.")
    except anthropic.APIConnectionError:
        raise HTTPException(status_code=502, detail="Hoardrun AI couldn't be reached. Check the connection and try again.")

    if response.stop_reason == "refusal":
        return {"reply": "I can't help with that one. Ask me about your money, saving, investing or how to use Hoardrun."}

    reply = "".join(block.text for block in response.content if block.type == "text").strip()
    if not reply:
        reply = "I didn't catch that. Could you ask again?"
    return {"reply": reply}
