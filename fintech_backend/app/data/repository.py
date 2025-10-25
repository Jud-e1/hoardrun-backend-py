"""
Data layer repository interfaces and implementations.
Provides unified access to data repositories for the application.
"""

from ..repositories.mock_repository import (
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
    get_plaid_connections_repository,
    get_plaid_accounts_repository,
    get_plaid_transactions_repository,
    get_plaid_link_tokens_repository,
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
    'get_plaid_connections_repository',
    'get_plaid_accounts_repository',
    'get_plaid_transactions_repository',
    'get_plaid_link_tokens_repository',
]
