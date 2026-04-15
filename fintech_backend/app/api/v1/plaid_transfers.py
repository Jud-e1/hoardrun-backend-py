"""
DEPRECATED: plaid_transfers.py has been merged into plaid.py.

All Plaid transfer routes are now served from /plaid/transfers/* by the
router defined in app.api.v1.plaid. This module is kept only to avoid
import errors in any code that referenced it directly.
"""
from app.api.v1.plaid import router  # noqa: F401
