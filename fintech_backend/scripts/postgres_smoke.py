"""
Walk through the app's main flows against a real PostgreSQL database.

Unit tests run on SQLite; this catches what only Postgres enforces (types, enums, constraints,
row locks). Point it at an EMPTY database it may fill with test users, never production:

    DATABASE_URL=postgresql://... python -m alembic upgrade head
    DATABASE_URL=postgresql://... PYTHONPATH=. python scripts/postgres_smoke.py

Emails are captured instead of sent, so sign-up codes can be read.
"""

import os
import re
import sys
import uuid

if os.getenv("ENVIRONMENT", "").lower() == "production":
    sys.exit("Refusing to run against production")

from fastapi.testclient import TestClient  # noqa: E402

from app.database.config import SessionLocal, engine  # noqa: E402
from app.database.migrate import require_up_to_date  # noqa: E402
from app.database.url import safe_url  # noqa: E402
from app.services import email_service  # noqa: E402
from app.services.deposit_ledger import credit_deposit  # noqa: E402

outbox = []
email_service.deliver = lambda to, subject, html, text_body: outbox.append((to, subject, text_body)) or True


class Now:
    @staticmethod
    def submit(fn, *args):
        fn(*args)


email_service._pool = Now()

from app.main import app  # noqa: E402

checks = []


def check(name, response, *ok):
    passed = response.status_code in (ok or (200, 201))
    checks.append((name, passed, response.status_code))
    print(f"{'ok ' if passed else 'FAIL'} {response.status_code} {name}" + ("" if passed else f": {response.text[:300]}"))
    return response


def sign_up(client, first):
    email = f"smoke-{first.lower()}-{uuid.uuid4().hex[:8]}@example.com"
    password = "Smoke-" + uuid.uuid4().hex[:10] + "A1"
    check(f"register {first}", client.post("/api/v1/auth/register", json={
        "email": email, "password": password, "first_name": first, "last_name": "Smoke", "terms_accepted": True}))
    code = re.search(r"\b(\d{6})\b", [m for m in outbox if m[0] == email][-1][2]).group(1)
    check(f"verify {first}", client.post("/api/v1/auth/verify-email", json={"email": email, "token": code}))
    login = check(f"login {first}", client.post("/api/v1/auth/login", json={"email": email, "password": password}))
    data = login.json()["data"]
    return email, data["user"]["id"], {"Authorization": f"Bearer {data['access_token']}"}


def main() -> int:
    print(f"Database: {safe_url(str(engine.url))}")
    require_up_to_date(engine)
    with TestClient(app) as client:
        ada_email, ada_id, ada = sign_up(client, "Ada")
        kofi_email, _, kofi = sign_up(client, "Kofi")

        with SessionLocal() as db:
            credit_deposit(db, user_id=ada_id, reference=f"smoke-{uuid.uuid4().hex}", amount_minor=50000, currency="USD")
        check("dashboard", client.get("/api/v1/dashboard/", headers=ada), 200, 307)

        goal = check("create savings goal", client.post("/api/v1/savings/goals", headers=ada, json={
            "name": "Rainy day", "targetAmount": 1000, "monthlyContribution": 50}))
        goal_id = goal.json().get("data", goal.json()).get("id")
        check("save into goal", client.post(f"/api/v1/savings/goals/{goal_id}/contribute", headers=ada, json={"amount": 40}))
        check("fixed deposit", client.post("/api/v1/savings/fixed-deposits", headers=ada, json={"amount": 100, "termMonths": 6}))
        check("create budget", client.post("/api/v1/budgets", headers=ada, json={"name": "Transfers", "category": "transfers", "budgeted_amount": 30}))
        check("send to a member", client.post("/api/v1/cash/send", headers=ada, json={"recipient_email": kofi_email, "amount": 35, "note": "smoke"}))
        check("budget summary", client.get("/api/v1/budgets/summary", headers=ada))
        check("transactions", client.get("/api/v1/transactions/", headers=ada))
        check("notifications", client.get("/api/v1/notifications", headers=kofi))
        check("email preference", client.put("/api/v1/notifications/preferences", headers=ada, json={"email": False}))
        check("bank links", client.get("/api/v1/plaid/accounts", headers=ada))
        check("hoardrun cards", client.get("/api/v1/issuing/cards", headers=ada))
        check("identity status", client.get("/api/v1/identity/status", headers=ada))
        check("investing positions", client.get("/api/v1/markets/positions?asset_type=etf", headers=ada), 200, 503)
        check("export my data", client.get("/api/v1/account/export", headers=ada))
        check("close check", client.get("/api/v1/account/close-check", headers=ada))
        check("forgot password", client.post("/api/v1/auth/forgot-password", json={"email": ada_email}))
        check("database health", client.get("/api/health/database"))
    failed = [name for name, passed, _ in checks if not passed]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} passed" + (f"; failed: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
