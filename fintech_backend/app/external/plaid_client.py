"""
Plaid API client for bank account integration.
"""

import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import plaid
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.institutions_get_by_id_request import InstitutionsGetByIdRequest
from plaid.model.country_code import CountryCode
from plaid.model.products import Products
from plaid.model.item_remove_request import ItemRemoveRequest
from plaid.model.auth_get_request import AuthGetRequest
from plaid.model.identity_get_request import IdentityGetRequest

from ..config.logging import get_logger

logger = get_logger(__name__)


class PlaidClient:
    """Plaid API client for financial data integration."""

    def __init__(self):
        self.client_id = os.getenv("PLAID_CLIENT_ID", "68f7c26d7c634d00204cd9a6")
        self.secret = os.getenv("PLAID_SECRET", "5ca72967955faa183961afaee34b44")
        self.environment = os.getenv("PLAID_ENV", "sandbox")

        # Initialize Plaid client
        configuration = plaid.Configuration(
            host=plaid.Environment.Sandbox if self.environment == "sandbox" else plaid.Environment.Development,
            api_key={
                'clientId': self.client_id,
                'secret': self.secret,
            }
        )

        self.api_client = plaid.ApiClient(configuration)
        self.client = plaid_api.PlaidApi(self.api_client)

        logger.info(f"Plaid client initialized for {self.environment} environment")

    async def create_link_token(self, user_id: str, client_name: str = "HoardRun") -> Dict[str, Any]:
        """
        Create a link token for Plaid Link initialization.

        Args:
            user_id: User identifier
            client_name: Name of the client application

        Returns:
            Link token response
        """
        try:
            request = LinkTokenCreateRequest(
                user=LinkTokenCreateRequestUser(
                    client_user_id=user_id
                ),
                client_name=client_name,
                products=[Products("auth"), Products("transactions")],
                country_codes=[CountryCode("US")],
                language="en"
            )

            response = self.client.link_token_create(request)
            link_token = response.link_token

            logger.info(f"Created link token for user {user_id}")
            return {
                "link_token": link_token,
                "expiration": (datetime.utcnow() + timedelta(hours=4)).isoformat(),
                "request_id": response.request_id
            }

        except plaid.ApiException as e:
            logger.error(f"Failed to create link token: {e}")
            raise Exception(f"Plaid API error: {e}")

    async def exchange_public_token(self, public_token: str) -> Dict[str, Any]:
        """
        Exchange a public token for an access token.

        Args:
            public_token: Public token from Plaid Link

        Returns:
            Access token and item ID
        """
        try:
            request = ItemPublicTokenExchangeRequest(
                public_token=public_token
            )

            response = self.client.item_public_token_exchange(request)

            logger.info("Successfully exchanged public token for access token")
            return {
                "access_token": response.access_token,
                "item_id": response.item_id,
                "request_id": response.request_id
            }

        except plaid.ApiException as e:
            logger.error(f"Failed to exchange public token: {e}")
            raise Exception(f"Plaid API error: {e}")

    async def get_accounts(self, access_token: str) -> List[Dict[str, Any]]:
        """
        Get account information for a user.

        Args:
            access_token: Plaid access token

        Returns:
            List of account information
        """
        try:
            request = AccountsGetRequest(access_token=access_token)
            response = self.client.accounts_get(request)

            accounts = []
            for account in response.accounts:
                accounts.append({
                    "account_id": account.account_id,
                    "name": account.name,
                    "official_name": account.official_name,
                    "type": account.type.value if account.type else None,
                    "subtype": account.subtype.value if account.subtype else None,
                    "mask": account.mask,
                    "balances": {
                        "available": float(account.balances.available) if account.balances.available else None,
                        "current": float(account.balances.current) if account.balances.current else None,
                        "limit": float(account.balances.limit) if account.balances.limit else None,
                        "iso_currency_code": account.balances.iso_currency_code,
                        "unofficial_currency_code": account.balances.unofficial_currency_code
                    } if account.balances else None
                })

            logger.info(f"Retrieved {len(accounts)} accounts")
            return accounts

        except plaid.ApiException as e:
            logger.error(f"Failed to get accounts: {e}")
            raise Exception(f"Plaid API error: {e}")

    async def get_transactions(
        self,
        access_token: str,
        start_date: str,
        end_date: str,
        account_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get transaction data for accounts.

        Args:
            access_token: Plaid access token
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            account_ids: Optional list of account IDs to filter

        Returns:
            List of transaction data
        """
        try:
            request = TransactionsGetRequest(
                access_token=access_token,
                start_date=start_date,
                end_date=end_date,
                options={
                    "account_ids": account_ids
                } if account_ids else {}
            )

            response = self.client.transactions_get(request)

            transactions = []
            for transaction in response.transactions:
                transactions.append({
                    "transaction_id": transaction.transaction_id,
                    "account_id": transaction.account_id,
                    "amount": float(transaction.amount),
                    "iso_currency_code": transaction.iso_currency_code,
                    "unofficial_currency_code": transaction.unofficial_currency_code,
                    "date": transaction.date,
                    "authorized_date": transaction.authorized_date,
                    "name": transaction.name,
                    "merchant_name": transaction.merchant_name,
                    "payment_channel": transaction.payment_channel.value if transaction.payment_channel else None,
                    "pending": transaction.pending,
                    "pending_transaction_id": transaction.pending_transaction_id,
                    "account_owner": transaction.account_owner,
                    "transaction_type": transaction.transaction_type.value if transaction.transaction_type else None,
                    "payment_meta": {
                        "reference_number": transaction.payment_meta.reference_number,
                        "ppd_id": transaction.payment_meta.ppd_id,
                        "payee": transaction.payment_meta.payee,
                        "by_order_of": transaction.payment_meta.by_order_of,
                        "payer": transaction.payment_meta.payer,
                        "payment_method": transaction.payment_meta.payment_method,
                        "payment_processor": transaction.payment_meta.payment_processor,
                        "reason": transaction.payment_meta.reason
                    } if transaction.payment_meta else None,
                    "location": {
                        "address": transaction.location.address,
                        "city": transaction.location.city,
                        "region": transaction.location.region,
                        "postal_code": transaction.location.postal_code,
                        "country": transaction.location.country,
                        "lat": float(transaction.location.lat) if transaction.location.lat else None,
                        "lon": float(transaction.location.lon) if transaction.location.lon else None,
                        "store_number": transaction.location.store_number
                    } if transaction.location else None,
                    "transaction_code": transaction.transaction_code.value if transaction.transaction_code else None
                })

            logger.info(f"Retrieved {len(transactions)} transactions")
            return transactions

        except plaid.ApiException as e:
            logger.error(f"Failed to get transactions: {e}")
            raise Exception(f"Plaid API error: {e}")

    async def get_auth_data(self, access_token: str) -> Dict[str, Any]:
        """
        Get authentication data (account numbers, routing numbers).

        Args:
            access_token: Plaid access token

        Returns:
            Authentication data
        """
        try:
            request = AuthGetRequest(access_token=access_token)
            response = self.client.auth_get(request)

            auth_data = {
                "accounts": [],
                "numbers": {
                    "ach": [],
                    "eft": [],
                    "international": [],
                    "bacs": []
                }
            }

            for account in response.accounts:
                auth_data["accounts"].append({
                    "account_id": account.account_id,
                    "name": account.name,
                    "type": account.type.value if account.type else None,
                    "subtype": account.subtype.value if account.subtype else None
                })

            if response.numbers:
                if response.numbers.ach:
                    for ach in response.numbers.ach:
                        auth_data["numbers"]["ach"].append({
                            "account_id": ach.account_id,
                            "account": ach.account,
                            "routing": ach.routing,
                            "wire_routing": ach.wire_routing
                        })

                if response.numbers.eft:
                    for eft in response.numbers.eft:
                        auth_data["numbers"]["eft"].append({
                            "account_id": eft.account_id,
                            "account": eft.account,
                            "institution": eft.institution,
                            "branch": eft.branch
                        })

                if response.numbers.international:
                    for intl in response.numbers.international:
                        auth_data["numbers"]["international"].append({
                            "account_id": intl.account_id,
                            "iban": intl.iban,
                            "bic": intl.bic
                        })

                if response.numbers.bacs:
                    for bacs in response.numbers.bacs:
                        auth_data["numbers"]["bacs"].append({
                            "account_id": bacs.account_id,
                            "account": bacs.account,
                            "sort_code": bacs.sort_code
                        })

            logger.info("Retrieved authentication data")
            return auth_data

        except plaid.ApiException as e:
            logger.error(f"Failed to get auth data: {e}")
            raise Exception(f"Plaid API error: {e}")

    async def get_identity(self, access_token: str) -> Dict[str, Any]:
        """
        Get identity information for accounts.

        Args:
            access_token: Plaid access token

        Returns:
            Identity information
        """
        try:
            request = IdentityGetRequest(access_token=access_token)
            response = self.client.identity_get(request)

            identity_data = {
                "accounts": []
            }

            for account in response.accounts:
                account_info = {
                    "account_id": account.account_id,
                    "owners": []
                }

                if account.owners:
                    for owner in account.owners:
                        owner_info = {
                            "names": owner.names,
                            "emails": [{"email": email.email, "primary": email.primary, "type": email.type} for email in owner.emails] if owner.emails else [],
                            "phone_numbers": [{"number": phone.number, "primary": phone.primary, "type": phone.type} for phone in owner.phone_numbers] if owner.phone_numbers else [],
                            "addresses": []
                        }

                        if owner.addresses:
                            for address in owner.addresses:
                                owner_info["addresses"].append({
                                    "street": address.street,
                                    "city": address.city,
                                    "region": address.region,
                                    "postal_code": address.postal_code,
                                    "country": address.country,
                                    "primary": address.primary
                                })

                        account_info["owners"].append(owner_info)

                identity_data["accounts"].append(account_info)

            logger.info("Retrieved identity information")
            return identity_data

        except plaid.ApiException as e:
            logger.error(f"Failed to get identity: {e}")
            raise Exception(f"Plaid API error: {e}")

    async def remove_item(self, access_token: str) -> Dict[str, Any]:
        """
        Remove an item (disconnect accounts).

        Args:
            access_token: Plaid access token

        Returns:
            Removal confirmation
        """
        try:
            request = ItemRemoveRequest(access_token=access_token)
            response = self.client.item_remove(request)

            logger.info("Successfully removed item")
            return {
                "removed": response.removed,
                "request_id": response.request_id
            }

        except plaid.ApiException as e:
            logger.error(f"Failed to remove item: {e}")
            raise Exception(f"Plaid API error: {e}")

    async def test_connection(self) -> Dict[str, Any]:
        """
        Test the Plaid API connection.

        Returns:
            Connection test results
        """
        try:
            # Try to create a link token as a connection test
            test_result = await self.create_link_token("test_user", "HoardRun Test")

            return {
                "status": "success",
                "message": "Plaid API connection successful",
                "client_id": self.client_id[:8] + "...",  # Partial client ID for security
                "environment": self.environment,
                "test_token_created": bool(test_result.get("link_token"))
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Plaid API connection failed: {str(e)}",
                "client_id": self.client_id[:8] + "...",
                "environment": self.environment
            }


# Global client instance
_plaid_client = None

def get_plaid_client() -> PlaidClient:
    """Get or create Plaid client instance."""
    global _plaid_client
    if _plaid_client is None:
        _plaid_client = PlaidClient()
    return _plaid_client
