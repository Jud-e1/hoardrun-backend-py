"""
Every module that defines database tables, imported once so Base.metadata knows them all.

Alembic and the development create_all both read Base.metadata. A table defined in a module
that isn't imported here would be missed by migrations, so a new module with a table goes here.
"""

# Core and feature tables in app/database
from . import banking_models, circle_models, listing_models, market_models, models, venture_models  # noqa: F401

# Tables that live beside the feature that uses them
from ..services import auth_codes, card_vault, inbox, login_throttle  # noqa: F401
from ..api.v1 import (  # noqa: F401
    apple_auth, bank_links, brokerage, budgets_store, cash, google_auth, identity, issued_cards, savings_store,
)

from .config import Base

metadata = Base.metadata
