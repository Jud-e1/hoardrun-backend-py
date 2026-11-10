"""
Hoardrun's emails, sent through Resend.

- Every email has an HTML and a plain-text version, built from one layout, with anything
  user-provided escaped.
- Emails about things saved in the database (money in, a bank linked) are queued on the
  session and sent only after it commits, so a rolled-back change never emails anyone.
  The request then waits for them before replying (finish_request_emails), because hosts
  such as Cloud Run slow the container down once it has replied.
- Without RESEND_API_KEY, development prints the email (codes included) to the server log so
  sign-up and reset can be tried locally; production logs only that an email was skipped.
"""

import asyncio
import html
import logging
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from typing import Optional

import resend
from sqlalchemy import event
from sqlalchemy.orm import Session

from ..auth.signing_key import is_production
from ..config.settings import get_settings

logger = logging.getLogger(__name__)

BLUE = "#2f6bff"
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="email")


# ---------- Sending ----------

def deliver(to: str, subject: str, html_body: str, text_body: str) -> bool:
    """Send one email now. Returns whether Resend accepted it."""
    settings = get_settings()
    if not to or to.endswith(".invalid"):
        return False
    if not settings.resend_api_key:
        if is_production():
            # Not the subject: a sign-up code is in it
            logger.warning("RESEND_API_KEY isn't set; skipped an email")
        else:
            logger.warning("RESEND_API_KEY isn't set. Email to %s\nSubject: %s\n\n%s", to, subject, text_body)
        return False
    resend.api_key = settings.resend_api_key
    try:
        resend.Emails.send({"from": settings.email_from, "to": [to], "subject": subject, "html": html_body, "text": text_body})
        return True
    except Exception as error:  # Resend's errors vary by version; an email failing must never break the request
        logger.error("Resend couldn't send an email: %s", error)
        return False


def queue(db: Session, to: str, subject: str, html_body: str, text_body: str) -> None:
    """Send once this session commits; dropped if it rolls back."""
    db.info.setdefault("hoardrun_outbox", []).append((to, subject, html_body, text_body))


# Emails started during the current request. Hosts such as Cloud Run slow a container down as
# soon as it replies, so the request waits for these before replying (finish_request_emails).
_request_emails: ContextVar[Optional[list]] = ContextVar("hoardrun_request_emails", default=None)
REQUEST_EMAIL_WAIT = 10  # seconds; a slow email provider must not hold a reply for long


@event.listens_for(Session, "after_commit")
def _send_outbox(session: Session) -> None:
    started = _request_emails.get()
    for message in session.info.pop("hoardrun_outbox", []):
        future = _pool.submit(deliver, *message)
        if started is not None:
            started.append(future)


async def finish_request_emails(request, call_next):
    """HTTP middleware: reply only after the emails this request started have been handed to Resend."""
    started: list = []
    token = _request_emails.set(started)
    try:
        response = await call_next(request)
    finally:
        _request_emails.reset(token)
    if started:
        done = asyncio.gather(*(asyncio.wrap_future(f) for f in started), return_exceptions=True)
        try:
            await asyncio.wait_for(done, timeout=REQUEST_EMAIL_WAIT)
        except asyncio.TimeoutError:
            logger.warning("Emails were still sending when the reply went out")
    return response


@event.listens_for(Session, "after_rollback")
def _drop_outbox(session: Session) -> None:
    session.info.pop("hoardrun_outbox", None)


# ---------- Layout ----------

def app_link(path: str = "/") -> str:
    return get_settings().app_url.rstrip("/") + (path if path.startswith("/") else "/" + path)


def layout(heading: str, paragraphs: list[str], *, button: Optional[tuple[str, str]] = None,
           code: Optional[str] = None, note: Optional[str] = None) -> tuple[str, str]:
    """(html, text) for one email. Inputs are plain text; they're escaped here."""
    e = html.escape
    parts = [f'<p style="margin:0 0 16px;font-size:16px;line-height:24px;color:#3a3a40">{e(p)}</p>' for p in paragraphs]
    if code:
        parts.append(
            f'<div style="margin:8px 0 24px;padding:18px 0;border-radius:16px;background:#f2f5ff;text-align:center;'
            f'font:600 34px/1 ui-monospace,Menlo,Consolas,monospace;letter-spacing:10px;color:#111">{e(code)}</div>')
    if button:
        label, url = button
        parts.append(
            f'<p style="margin:8px 0 24px"><a href="{e(url, quote=True)}" style="display:inline-block;padding:14px 26px;'
            f'border-radius:999px;background:{BLUE};color:#fff;font-weight:600;font-size:16px;text-decoration:none">{e(label)}</a></p>'
            f'<p style="margin:0 0 16px;font-size:13px;line-height:20px;color:#8e8e93">Or paste this link into your browser:<br>'
            f'<span style="word-break:break-all">{e(url)}</span></p>')
    if note:
        parts.append(f'<p style="margin:16px 0 0;font-size:13px;line-height:20px;color:#8e8e93">{e(note)}</p>')
    body = "".join(parts)
    page = (
        '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        f'<title>{e(heading)}</title></head>'
        '<body style="margin:0;padding:0;background:#f4f4f6;font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,Arial,sans-serif">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f6;padding:32px 16px">'
        '<tr><td align="center"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px">'
        f'<tr><td style="padding:0 8px 16px;font-size:20px;font-weight:700;letter-spacing:-0.02em;color:{BLUE}">Hoardrun</td></tr>'
        '<tr><td style="background:#fff;border-radius:24px;padding:32px 28px">'
        f'<h1 style="margin:0 0 16px;font-size:24px;line-height:30px;letter-spacing:-0.02em;color:#111">{e(heading)}</h1>{body}'
        '</td></tr>'
        '<tr><td style="padding:16px 8px;font-size:12px;line-height:18px;color:#8e8e93">'
        'You got this email because you have a Hoardrun account. Hoardrun will never ask for your password or a code by phone or email.'
        '</td></tr></table></td></tr></table></body></html>'
    )
    text = "\n\n".join([heading, *paragraphs, *( [code] if code else [] ),
                        *([f"{button[0]}: {button[1]}"] if button else []), *([note] if note else []),
                        "Hoardrun will never ask for your password or a code by phone or email."])
    return page, text


def hello(name: Optional[str]) -> str:
    return f"Hi {name}," if name else "Hi,"


# ---------- The emails ----------

def verification_email(code: str, name: Optional[str] = None) -> tuple[str, str, str]:
    subject = f"{code} is your Hoardrun code"
    page, text = layout("Confirm your email", [hello(name), "Enter this code to finish setting up your Hoardrun account:"],
                        code=code, note="The code works for 24 hours. If you didn't sign up for Hoardrun, you can ignore this email.")
    return subject, page, text


def reset_email(url: str, name: Optional[str] = None) -> tuple[str, str, str]:
    page, text = layout("Reset your password", [hello(name), "Someone asked to reset the password for your Hoardrun account. If that was you, choose a new one:"],
                        button=("Choose a new password", url),
                        note="The link works once, for 1 hour. If you didn't ask, ignore this email and your password stays the same.")
    return "Reset your Hoardrun password", page, text


def password_changed_email(name: Optional[str] = None) -> tuple[str, str, str]:
    page, text = layout("Your password was changed", [hello(name), "The password for your Hoardrun account was just changed."],
                        button=("Open Hoardrun", app_link("/signin")),
                        note="If this wasn't you, reset your password right away from the sign-in page and contact support.")
    return "Your Hoardrun password was changed", page, text


def event_email(title: str, message: str, link: Optional[str] = None) -> tuple[str, str, str]:
    page, text = layout(title, [message], button=("Open Hoardrun", app_link(link or "/home")))
    return f"{title} · Hoardrun", page, text


def goodbye_email(name: Optional[str] = None) -> tuple[str, str, str]:
    page, text = layout("Your account is closed", [hello(name), "Your Hoardrun account is now closed and your personal details have been removed. "
                        "Records of past transactions are kept as the law requires."],
                        note="If you didn't close your account, contact Hoardrun support right away.")
    return "Your Hoardrun account is closed", page, text


# ---------- Kept for existing callers ----------

class EmailService:
    """Async wrappers used by sign-up and password reset."""

    async def send_email(self, to: str, subject: str, html_content: str, text_content: Optional[str] = None, **_) -> bool:
        return await asyncio.to_thread(deliver, to, subject, html_content, text_content or subject)

    async def send_verification_email(self, to: str, verification_token: str, user_name: Optional[str] = None) -> bool:
        return await asyncio.to_thread(deliver, to, *verification_email(verification_token, user_name))

    async def send_password_reset_email(self, to: str, reset_token: str, user_name: Optional[str] = None) -> bool:
        return await asyncio.to_thread(deliver, to, *reset_email(app_link(f"/reset-password?token={reset_token}"), user_name))

    async def send_password_changed_email(self, to: str, user_name: Optional[str] = None) -> bool:
        return await asyncio.to_thread(deliver, to, *password_changed_email(user_name))


email_service = EmailService()


def get_email_service() -> EmailService:
    return email_service
