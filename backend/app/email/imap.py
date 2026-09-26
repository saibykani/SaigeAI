"""Gmail over IMAP with a Google App Password: an alternative to OAuth while the Google Cloud
project is unverified or in Testing mode.

App Passwords are issued by Google for exactly this (myaccount.google.com/apppasswords, requires
2-Step Verification) and can be revoked there at any time. Saige only reads: messages are fetched
with BODY.PEEK so nothing is marked as read, and nothing is sent, moved or deleted. The password is
stored encrypted (services/crypto.py). Message ids are Gmail's own (X-GM-MSGID in hex, the same id
the Gmail API uses), so mail is never imported twice if you later switch to OAuth.
"""

import asyncio
import contextlib
import email
import imaplib
import re
from email import policy
from email.utils import parsedate_to_datetime

from app.email.gmail import DEFAULT_QUERY, GmailError
from app.jobs.jd_parser import html_to_text

HOST = "imap.gmail.com"
IMAP_FACTORY = imaplib.IMAP4_SSL  # patched in tests
_META = re.compile(rb"X-GM-MSGID (\d+).*?X-GM-THRID (\d+)", re.S)


def normalize_password(app_password: str) -> str:
    return re.sub(r"\s+", "", app_password)


def _login(address: str, app_password: str):
    try:
        conn = IMAP_FACTORY(HOST, 993, timeout=20)
    except OSError as exc:
        raise GmailError("Couldn't reach Gmail. Try again in a moment.") from exc
    try:
        conn.login(address, normalize_password(app_password))
    except imaplib.IMAP4.error as exc:
        raise GmailError("Gmail rejected the address or App Password. Create a new App Password and paste it "
                         "exactly (spaces are fine). IMAP must be allowed in Gmail settings.") from exc
    return conn


def _text(msg: email.message.EmailMessage) -> str:
    plain = msg.get_body(preferencelist=("plain",))
    if plain is not None:
        return plain.get_content()
    html = msg.get_body(preferencelist=("html",))
    return html_to_text(html.get_content(), keep_links=True) if html is not None else ""


def _fetch_sync(address: str, app_password: str, limit: int, skip: set[str], query: str = DEFAULT_QUERY) -> list[dict]:
    conn = _login(address, app_password)
    try:
        conn.select("INBOX", readonly=True)
        status, data = conn.uid("SEARCH", "X-GM-RAW", f'"{query}"')
        if status != "OK":
            raise GmailError("Gmail search failed")
        uids = (data[0] or b"").split()[-limit:]
        out = []
        for uid in reversed(uids):  # newest first
            status, parts = conn.uid("FETCH", uid, "(X-GM-MSGID X-GM-THRID BODY.PEEK[])")
            if status != "OK" or not parts or not isinstance(parts[0], tuple):
                continue
            meta, raw = parts[0]
            m = _META.search(meta)
            if not m:
                continue
            gmail_id, thread_id = format(int(m.group(1)), "x"), format(int(m.group(2)), "x")
            if gmail_id in skip:
                continue
            msg = email.message_from_bytes(raw, policy=policy.default)
            try:
                received_ms = int(parsedate_to_datetime(msg["Date"]).timestamp() * 1000)
            except (TypeError, ValueError):
                received_ms = 0
            body = _text(msg)
            out.append({"gmail_id": gmail_id, "thread_id": thread_id, "sender": str(msg["From"] or ""),
                        "subject": str(msg["Subject"] or ""), "body": body[:20000], "received_ms": received_ms,
                        "snippet": re.sub(r"\s+", " ", body)[:160]})
        return out
    finally:
        with contextlib.suppress(Exception):  # closing is best effort
            conn.logout()


async def verify(address: str, app_password: str) -> None:
    def check() -> None:
        _login(address, app_password).logout()

    await asyncio.to_thread(check)


async def fetch_messages(address: str, app_password: str, limit: int = 50, skip: set[str] | None = None,
                         query: str = DEFAULT_QUERY) -> list[dict]:
    return await asyncio.to_thread(_fetch_sync, address, app_password, limit, skip or set(), query)
