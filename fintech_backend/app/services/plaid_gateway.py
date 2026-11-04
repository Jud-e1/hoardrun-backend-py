"""
A thin wrapper over the Plaid SDK: plain dicts in and out, one error type.

Only what Hoardrun uses: Link, accounts, transactions, and Transfer (ACH to and from
the user's own linked bank). Tests swap the whole gateway for a fake.
"""

import json
from datetime import date
from decimal import Decimal
from typing import Optional

import plaid
from plaid.api import plaid_api
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.ach_class import ACHClass
from plaid.model.country_code import CountryCode
from plaid.model.institutions_get_by_id_request import InstitutionsGetByIdRequest
from plaid.model.item_get_request import ItemGetRequest
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.item_remove_request import ItemRemoveRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.sandbox_transfer_simulate_request import SandboxTransferSimulateRequest
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.transactions_get_request_options import TransactionsGetRequestOptions
from plaid.model.transfer_authorization_create_request import TransferAuthorizationCreateRequest
from plaid.model.transfer_authorization_user_in_request import TransferAuthorizationUserInRequest
from plaid.model.transfer_create_request import TransferCreateRequest
from plaid.model.transfer_event_sync_request import TransferEventSyncRequest
from plaid.model.transfer_network import TransferNetwork
from plaid.model.transfer_type import TransferType


class PlaidError(Exception):
    def __init__(self, code: str, message: str, display: Optional[str] = None):
        super().__init__(message)
        self.code = code
        self.display = display


def text(value) -> Optional[str]:
    """Plaid enums arrive as objects; everything else as is."""
    if value is None:
        return None
    return str(getattr(value, "value", value))


class PlaidGateway:
    def __init__(self, client_id: str, secret: str, env: str = "sandbox"):
        self.sandbox = env != "production"
        configuration = plaid.Configuration(
            host=plaid.Environment.Sandbox if self.sandbox else plaid.Environment.Production,
            api_key={"clientId": client_id, "secret": secret},
        )
        self.api = plaid_api.PlaidApi(plaid.ApiClient(configuration))

    def _call(self, method, request):
        try:
            return method(request).to_dict()
        except plaid.ApiException as error:
            try:
                body = json.loads(error.body or "{}")
            except ValueError:
                body = {}
            raise PlaidError(body.get("error_code") or "PLAID_ERROR", body.get("error_message") or str(error),
                             body.get("display_message"))

    def link_token(self, user_id: str, webhook: Optional[str] = None, access_token: Optional[str] = None) -> dict:
        """A new link, or with access_token, a reconnect for a bank that needs the user to sign in again."""
        params = dict(
            client_name="Hoardrun", language="en", country_codes=[CountryCode("US")],
            user=LinkTokenCreateRequestUser(client_user_id=user_id),
        )
        if access_token:
            params["access_token"] = access_token
        else:
            params["products"] = [Products("transfer")]
            params["optional_products"] = [Products("transactions")]
        if webhook:
            params["webhook"] = webhook
        result = self._call(self.api.link_token_create, LinkTokenCreateRequest(**params))
        return {"link_token": result["link_token"], "expiration": str(result["expiration"])}

    def exchange(self, public_token: str) -> dict:
        result = self._call(self.api.item_public_token_exchange, ItemPublicTokenExchangeRequest(public_token=public_token))
        return {"access_token": result["access_token"], "item_id": result["item_id"]}

    def item(self, access_token: str) -> dict:
        item = self._call(self.api.item_get, ItemGetRequest(access_token=access_token))["item"]
        name = None
        if item.get("institution_id"):
            try:
                found = self._call(self.api.institutions_get_by_id, InstitutionsGetByIdRequest(
                    institution_id=item["institution_id"], country_codes=[CountryCode("US")]))
                name = found["institution"]["name"]
            except PlaidError:
                pass
        error = item.get("error") or {}
        return {"item_id": item["item_id"], "institution_id": item.get("institution_id"), "institution_name": name,
                "error_code": error.get("error_code")}

    def accounts(self, access_token: str) -> list[dict]:
        result = self._call(self.api.accounts_get, AccountsGetRequest(access_token=access_token))
        return [{
            "account_id": a["account_id"], "name": a.get("name"), "official_name": a.get("official_name"),
            "mask": a.get("mask"), "type": text(a.get("type")), "subtype": text(a.get("subtype")),
            "available": (a.get("balances") or {}).get("available"), "current": (a.get("balances") or {}).get("current"),
            "limit": (a.get("balances") or {}).get("limit"),
            "currency": (a.get("balances") or {}).get("iso_currency_code") or "USD",
        } for a in result["accounts"]]

    def transactions(self, access_token: str, start: date, end: date, count: int = 100) -> list[dict]:
        result = self._call(self.api.transactions_get, TransactionsGetRequest(
            access_token=access_token, start_date=start, end_date=end, options=TransactionsGetRequestOptions(count=count)))
        return [{
            "transaction_id": t["transaction_id"], "account_id": t["account_id"], "amount": t["amount"],
            "currency": t.get("iso_currency_code") or "USD", "date": str(t["date"]), "name": t.get("name"),
            "merchant_name": t.get("merchant_name"), "pending": bool(t.get("pending")),
            "category": t.get("category") or [],
        } for t in result["transactions"]]

    def remove(self, access_token: str) -> None:
        self._call(self.api.item_remove, ItemRemoveRequest(access_token=access_token))

    def authorize(self, *, access_token: str, account_id: str, kind: str, amount: Decimal, legal_name: str,
                  idempotency_key: str) -> dict:
        """kind is debit (bank to Hoardrun) or credit (Hoardrun to bank)."""
        result = self._call(self.api.transfer_authorization_create, TransferAuthorizationCreateRequest(
            access_token=access_token, account_id=account_id, type=TransferType(kind), network=TransferNetwork("ach"),
            amount=f"{amount:.2f}", ach_class=ACHClass("ppd"), user=TransferAuthorizationUserInRequest(legal_name=legal_name),
            idempotency_key=idempotency_key))["authorization"]
        rationale = result.get("decision_rationale") or {}
        return {"id": result["id"], "decision": text(result["decision"]),
                "reason": rationale.get("description") if isinstance(rationale, dict) else None}

    def create_transfer(self, *, access_token: str, account_id: str, authorization_id: str, description: str) -> dict:
        result = self._call(self.api.transfer_create, TransferCreateRequest(
            access_token=access_token, account_id=account_id, authorization_id=authorization_id,
            description=description[:15]))["transfer"]
        return {"id": result["id"], "status": text(result["status"])}

    def events(self, after_id: int, count: int = 25) -> list[dict]:
        result = self._call(self.api.transfer_event_sync, TransferEventSyncRequest(after_id=after_id, count=count))
        return [{
            "event_id": e["event_id"], "transfer_id": e.get("transfer_id"), "event_type": text(e["event_type"]),
            "failure_reason": ((e.get("failure_reason") or {}).get("description")),
        } for e in result["transfer_events"]]

    def simulate(self, transfer_id: str, event_type: str) -> None:
        """Sandbox only: move a test transfer along (posted, settled, failed, returned)."""
        self._call(self.api.sandbox_transfer_simulate, SandboxTransferSimulateRequest(
            transfer_id=transfer_id, event_type=event_type))
