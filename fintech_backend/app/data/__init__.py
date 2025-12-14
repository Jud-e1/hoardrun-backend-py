"""
Data layer package for fintech backend.
Provides unified access to data repositories and database operations.
"""

from .repository import (
    RepositoryManager,
    get_repository_manager,
    get_accounts_repository,
    get_cards_repository,
    get_transactions_repository,
    get_transfers_repository,
    get_investments_repository,
    get_savings_goals_repository,
    get_savings_accounts_repository,
    get_beneficiaries_repository,
    get_notifications_repository,
    get_settings_repository,
    get_watchlist_repository,
)

__all__ = [
    'RepositoryManager',
    'get_repository_manager',
    'get_accounts_repository',
    'get_cards_repository',
    'get_transactions_repository',
    'get_transfers_repository',
    'get_investments_repository',
    'get_savings_goals_repository',
    'get_savings_accounts_repository',
    'get_beneficiaries_repository',
    'get_notifications_repository',
    'get_settings_repository',
    'get_watchlist_repository',
]
