"""
Emails queued during a request go out before the reply (hosts such as Cloud Run slow a container
down once it has replied), only after the change is saved, and never hold a reply for long.

Run from fintech_backend with:
PYTHONPATH=. python -m pytest tests/unit/test_email_timing.py --noconftest --import-mode=importlib
"""

import os
import threading
import time

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.services import email_service


@pytest.fixture
def setup(monkeypatch):
    sent, lock = [], threading.Lock()

    def slow_deliver(to, subject, html_body, text_body):
        time.sleep(0.4)  # a provider taking its time
        with lock:
            sent.append(to)
        return True

    monkeypatch.setattr(email_service, "deliver", slow_deliver)
    Session = sessionmaker(bind=create_engine("sqlite://"))
    app = FastAPI()
    app.middleware("http")(email_service.finish_request_emails)

    @app.post("/saved")
    def saved():
        with Session() as db:
            email_service.queue(db, "ada@example.com", "s", "<p>h</p>", "t")
            email_service.queue(db, "kofi@example.com", "s", "<p>h</p>", "t")
            db.commit()
        return {"ok": True}

    @app.post("/undone")
    def undone():
        with Session() as db:
            email_service.queue(db, "ada@example.com", "s", "<p>h</p>", "t")
            db.rollback()
        return {"ok": True}

    @app.post("/async-saved")
    async def async_saved():
        with Session() as db:
            email_service.queue(db, "nana@example.com", "s", "<p>h</p>", "t")
            db.commit()
        return {"ok": True}

    return TestClient(app), sent


def test_emails_are_sent_before_the_reply(setup):
    client, sent = setup
    assert client.post("/saved").status_code == 200
    # Both were handed over before the reply came back, sent side by side
    assert sorted(sent) == ["ada@example.com", "kofi@example.com"]


def test_async_routes_wait_too(setup):
    client, sent = setup
    assert client.post("/async-saved").status_code == 200
    assert sent == ["nana@example.com"]


def test_a_rolled_back_change_emails_no_one(setup):
    client, sent = setup
    assert client.post("/undone").status_code == 200
    time.sleep(0.6)
    assert sent == []


def test_a_slow_provider_cant_hold_the_reply(setup, monkeypatch):
    client, sent = setup
    monkeypatch.setattr(email_service, "REQUEST_EMAIL_WAIT", 0.1)
    started = time.monotonic()
    assert client.post("/saved").status_code == 200
    assert time.monotonic() - started < 0.35
    time.sleep(0.6)
    assert len(sent) == 2  # still sent, just after the reply
