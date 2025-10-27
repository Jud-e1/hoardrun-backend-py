"""
Plaid client extension for money transfers.
"""

import os
from typing import Dict, Any, Optional
from plaid import ApiClient
from plaid.model.transfer_create_request import TransferCreateRequest
from plaid.model.transfer_get_request import TransferGetRequest
from plaid.model.transfer_authorization_create_request import TransferAuthorizationCreateRequest
from plaid.model.transfer_type import TransferType as PlaidTransferType
from plaid.model.transfer_network import TransferNetwork
from plaid.model.transfer_user_in_request import TransferUserInRequest
from plaid.model.ach_class import ACHClass
import plaid

from ..config.logging import get_logger

logger = get_logger(__name__)


class PlaidClient:
    """Extended Plaid client with transfer support."""

    def __init__(self):
        configuration = plaid.Configuration(
            host=plaid.Environment.Sandbox,  # Use Production for live
            api_key={
                'clientId': os.getenv('PLAID_CLIENT_ID'),
                'secret': os.getenv('PLAID_SECRET'),
            }
        )
        
        api_client = plaid.ApiClient(configuration)
        self.client = plaid.PlaidApi(api_client)

    async def create_transfer(self, transfer_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a transfer using Plaid Transfer API.
        
        Args:
            transfer_data: Transfer request data containing:
                - access_token: Plaid access token
                - account_id: Source account ID
                - amount: Transfer amount
                - description: Transfer description
                - ach_class: ACH class (ppd, ccd, web)
                - user: User information
                
        Returns:
            Transfer creation response
        """
        try:
            # First, create a transfer authorization
            authorization = await self._create_transfer_authorization(transfer_data)
            
            if not authorization or authorization.get('decision') != 'approved':
                raise Exception(f"Transfer authorization failed: {authorization}")
            
            # Create the actual transfer
            transfer_request = TransferCreateRequest(
                access_token=transfer_data['access_token'],
                account_id=transfer_data['account_id'],
                authorization_id=authorization['authorization']['id'],
                description=transfer_data['description'],
                type=PlaidTransferType('debit')
            )
            
            response = self.client.transfer_create(transfer_request)
            
            return {
                'transfer_id': response['transfer']['id'],
                'status': response['transfer']['status'],
                'amount': response['transfer']['amount'],
                'created': response['transfer']['created'],
                'authorization_id': authorization['authorization']['id']
            }
            
        except plaid.ApiException as e:
            logger.error(f"Plaid transfer creation failed: {e}")
            raise Exception(f"Transfer creation failed: {str(e)}")

    async def _create_transfer_authorization(
        self, 
        transfer_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a transfer authorization before initiating transfer.
        
        Args:
            transfer_data: Transfer data
            
        Returns:
            Authorization response
        """
        try:
            user = TransferUserInRequest(
                legal_name=transfer_data['user']['legal_name']
            )
            
            auth_request = TransferAuthorizationCreateRequest(
                access_token=transfer_data['access_token'],
                account_id=transfer_data['account_id'],
                type=PlaidTransferType('debit'),
                network=TransferNetwork('ach'),
                amount=transfer_data['amount'],
                ach_class=ACHClass(transfer_data.get('ach_class', 'ppd')),
                user=user
            )
            
            response = self.client.transfer_authorization_create(auth_request)
            
            return {
                'authorization': {
                    'id': response['authorization']['id'],
                    'decision': response['authorization']['decision'],
                    'decision_rationale': response['authorization'].get('decision_rationale')
                }
            }
            
        except plaid.ApiException as e:
            logger.error(f"Transfer authorization failed: {e}")
            return {
                'authorization': {
                    'decision': 'declined',
                    'decision_rationale': str(e)
                }
            }

    async def get_transfer_status(self, transfer_id: str) -> Dict[str, Any]:
        """
        Get the status of a transfer.
        
        Args:
            transfer_id: Plaid transfer ID
            
        Returns:
            Transfer status information
        """
        try:
            request = TransferGetRequest(transfer_id=transfer_id)
            response = self.client.transfer_get(request)
            
            return {
                'transfer_id': response['transfer']['id'],
                'status': response['transfer']['status'],
                'amount': response['transfer']['amount'],
                'created': response['transfer']['created'],
                'failure_reason': response['transfer'].get('failure_reason')
            }
            
        except plaid.ApiException as e:
            logger.error(f"Failed to get transfer status: {e}")
            raise Exception(f"Failed to get transfer status: {str(e)}")

    async def cancel_transfer(self, transfer_id: str) -> Dict[str, Any]:
        """
        Cancel a pending transfer.
        
        Args:
            transfer_id: Plaid transfer ID
            
        Returns:
            Cancellation response
        """
        try:
            from plaid.model.transfer_cancel_request import TransferCancelRequest
            
            request = TransferCancelRequest(transfer_id=transfer_id)
            response = self.client.transfer_cancel(request)
            
            return {
                'transfer_id': response['transfer']['id'],
                'status': response['transfer']['status'],
                'cancelled': True
            }
            
        except plaid.ApiException as e:
            logger.error(f"Failed to cancel transfer: {e}")
            raise Exception(f"Failed to cancel transfer: {str(e)}")

    async def create_link_token(
        self,
        user_id: str,
        client_name: str = "HoardRun",
        products: Optional[list] = None,
        country_codes: Optional[list] = None,
        language: str = "en",
        webhook: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a Plaid Link token.

        Args:
            user_id: User identifier
            client_name: Application name
            products: List of Plaid products (e.g., ['auth', 'transactions'])
            country_codes: List of country codes (e.g., ['US'])
            language: Language code
            webhook: Webhook URL

        Returns:
            Link token response
        """
        try:
            from plaid.model.link_token_create_request import LinkTokenCreateRequest
            from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
            from plaid.model.products import Products
            from plaid.model.country_code import CountryCode

            # Default products if not specified
            if products is None:
                products = ['auth', 'transactions']

            # Default country codes if not specified
            if country_codes is None:
                country_codes = ['US']

            request = LinkTokenCreateRequest(
                user=LinkTokenCreateRequestUser(client_user_id=user_id),
                client_name=client_name,
                products=[Products(p) for p in products],
                country_codes=[CountryCode(c) for c in country_codes],
                language=language
            )

            if webhook:
                request.webhook = webhook

            response = self.client.link_token_create(request)

            return {
                'link_token': response['link_token'],
                'expiration': response['expiration'],
                'request_id': response.get('request_id')
            }

        except plaid.ApiException as e:
            logger.error(f"Failed to create link token: {e}")
            raise Exception(f"Failed to create link token: {str(e)}")

    async def create_debit_card_link_token(
        self,
        user_id: str,
        client_name: str = "HoardRun"
    ) -> Dict[str, Any]:
        """
        Create a Plaid Link token specifically for debit card verification.

        Args:
            user_id: User identifier
            client_name: Application name

        Returns:
            Link token response for debit card verification
        """
        try:
            from plaid.model.link_token_create_request import LinkTokenCreateRequest
            from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
            from plaid.model.products import Products
            from plaid.model.country_code import CountryCode

            request = LinkTokenCreateRequest(
                user=LinkTokenCreateRequestUser(client_user_id=user_id),
                client_name=client_name,
                products=[Products('card_verification')],
                country_codes=[CountryCode('US')],
                language='en'
            )

            response = self.client.link_token_create(request)

            return {
                'link_token': response['link_token'],
                'expiration': response['expiration'],
                'request_id': response.get('request_id')
            }

        except plaid.ApiException as e:
            logger.error(f"Failed to create debit card link token: {e}")
            raise Exception(f"Failed to create debit card link token: {str(e)}")

    async def verify_debit_card(
        self,
        public_token: str,
        account_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Verify a debit card using Plaid.

        Args:
            public_token: Public token from Plaid Link
            account_id: Specific account ID to verify (optional)

        Returns:
            Debit card verification response
        """
        try:
            # First exchange the public token for access token
            token_response = await self.exchange_public_token(public_token)
            access_token = token_response['access_token']

            # Get accounts to verify the debit card
            accounts = await self.get_accounts(access_token)

            # Filter for debit card accounts if account_id is specified
            if account_id:
                accounts = [acc for acc in accounts if acc['account_id'] == account_id]

            # Look for debit card accounts (typically checking or savings with card access)
            debit_accounts = [
                acc for acc in accounts
                if acc.get('type') in ['checking', 'savings'] and acc.get('subtype') in ['checking', 'savings']
            ]

            if not debit_accounts:
                raise Exception("No eligible debit card accounts found")

            # For verification, we consider the card verified if we can access account details
            # In a real implementation, you might want to perform additional verification steps
            verified_account = debit_accounts[0]

            return {
                'verified': True,
                'account_id': verified_account['account_id'],
                'account_name': verified_account['name'],
                'account_type': verified_account['type'],
                'account_subtype': verified_account['subtype'],
                'access_token': access_token,
                'item_id': token_response['item_id']
            }

        except plaid.ApiException as e:
            logger.error(f"Failed to verify debit card: {e}")
            raise Exception(f"Failed to verify debit card: {str(e)}")
        except Exception as e:
            logger.error(f"Debit card verification error: {e}")
            raise Exception(f"Debit card verification failed: {str(e)}")

    async def exchange_public_token(self, public_token: str) -> Dict[str, Any]:
        """
        Exchange public token for access token.
        
        Args:
            public_token: Public token from Plaid Link
            
        Returns:
            Access token and item ID
        """
        try:
            from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
            
            request = ItemPublicTokenExchangeRequest(public_token=public_token)
            response = self.client.item_public_token_exchange(request)
            
            return {
                'access_token': response['access_token'],
                'item_id': response['item_id']
            }
            
        except plaid.ApiException as e:
            logger.error(f"Failed to exchange public token: {e}")
            raise Exception(f"Failed to exchange token: {str(e)}")

    async def get_accounts(self, access_token: str) -> list:
        """
        Get accounts for an access token.
        
        Args:
            access_token: Plaid access token
            
        Returns:
            List of accounts
        """
        try:
            from plaid.model.accounts_get_request import AccountsGetRequest
            
            request = AccountsGetRequest(access_token=access_token)
            response = self.client.accounts_get(request)
            
            accounts = []
            for account in response['accounts']:
                accounts.append({
                    'account_id': account['account_id'],
                    'name': account['name'],
                    'official_name': account.get('official_name'),
                    'type': account['type'],
                    'subtype': account.get('subtype'),
                    'mask': account.get('mask'),
                    'balances': {
                        'available': account['balances'].get('available'),
                        'current': account['balances']['current'],
                        'limit': account['balances'].get('limit'),
                        'iso_currency_code': account['balances'].get('iso_currency_code'),
                        'unofficial_currency_code': account['balances'].get('unofficial_currency_code')
                    }
                })
            
            return accounts
            
        except plaid.ApiException as e:
            logger.error(f"Failed to get accounts: {e}")
            raise Exception(f"Failed to get accounts: {str(e)}")

    async def get_transactions(
        self, 
        access_token: str, 
        start_date: str, 
        end_date: str
    ) -> list:
        """
        Get transactions for an access token.
        
        Args:
            access_token: Plaid access token
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            List of transactions
        """
        try:
            from plaid.model.transactions_get_request import TransactionsGetRequest
            from datetime import datetime
            
            request = TransactionsGetRequest(
                access_token=access_token,
                start_date=datetime.strptime(start_date, '%Y-%m-%d').date(),
                end_date=datetime.strptime(end_date, '%Y-%m-%d').date()
            )
            
            response = self.client.transactions_get(request)
            
            transactions = []
            for txn in response['transactions']:
                transactions.append({
                    'transaction_id': txn['transaction_id'],
                    'account_id': txn['account_id'],
                    'amount': txn['amount'],
                    'iso_currency_code': txn.get('iso_currency_code'),
                    'unofficial_currency_code': txn.get('unofficial_currency_code'),
                    'date': str(txn['date']),
                    'authorized_date': str(txn.get('authorized_date')) if txn.get('authorized_date') else None,
                    'name': txn['name'],
                    'merchant_name': txn.get('merchant_name'),
                    'payment_channel': txn.get('payment_channel'),
                    'pending': txn.get('pending', False),
                    'pending_transaction_id': txn.get('pending_transaction_id'),
                    'account_owner': txn.get('account_owner'),
                    'transaction_type': txn.get('transaction_type'),
                    'payment_meta': txn.get('payment_meta'),
                    'location': txn.get('location'),
                    'transaction_code': txn.get('transaction_code')
                })
            
            return transactions
            
        except plaid.ApiException as e:
            logger.error(f"Failed to get transactions: {e}")
            raise Exception(f"Failed to get transactions: {str(e)}")

    async def remove_item(self, access_token: str) -> Dict[str, Any]:
        """
        Remove a Plaid item (disconnect).
        
        Args:
            access_token: Plaid access token
            
        Returns:
            Removal confirmation
        """
        try:
            from plaid.model.item_remove_request import ItemRemoveRequest
            
            request = ItemRemoveRequest(access_token=access_token)
            response = self.client.item_remove(request)
            
            return {
                'removed': True,
                'request_id': response['request_id']
            }
            
        except plaid.ApiException as e:
            logger.error(f"Failed to remove item: {e}")
            raise Exception(f"Failed to remove item: {str(e)}")

    async def test_connection(self) -> Dict[str, Any]:
        """
        Test Plaid API connection.
        
        Returns:
            Connection test results
        """
        try:
            # Simple test by trying to get categories
            from plaid.model.categories_get_request import CategoriesGetRequest
            
            request = CategoriesGetRequest()
            response = self.client.categories_get(request)
            
            return {
                'status': 'success',
                'message': 'Plaid API connection successful',
                'categories_count': len(response['categories'])
            }
            
        except Exception as e:
            logger.error(f"Plaid connection test failed: {e}")
            return {
                'status': 'error',
                'message': f'Connection test failed: {str(e)}'
            }


def get_plaid_client() -> PlaidClient:
    """Dependency provider for Plaid client."""
    return PlaidClient()
