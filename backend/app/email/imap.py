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
# Gmail returns these attributes in any order (often X-GM-THRID first), so match each on its own.
_MSGID = re.compile(rb"X-GM-MSGID (\d+)")
_THRID = re.compile(rb"X-GM-THRID (\d+)")


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


def _all_mail(conn) -> str:
    """Gmail's "All Mail" folder (its name is localised), so Social / Promotions / Updates tabs are included."""
    try:
        status, boxes = conn.list()
    except Exception:  # noqa: BLE001 - fall back to the inbox
        return "INBOX"
    for line in boxes or []:
        text = line.decode(errors="ignore") if isinstance(line, bytes) else str(line)
        if "\\All" in text:
            m = re.search(r'"([^"]+)"\s*$', text) or re.search(r"(\S+)\s*$", text)
            if m:
                return f'"{m.group(1)}"'
    return "INBOX"


def _since(days: int) -> str:
    from datetime import UTC, datetime, timedelta

    return (datetime.now(UTC) - timedelta(days=days)).strftime("%d-%b-%Y")


def _unknown_newest(conn, uids: list[bytes], skip: set[str], limit: int) -> list[bytes]:
    """The newest `limit` messages not imported yet: ids are fetched cheaply first, so every sync
    backfills the next batch of older mail instead of re-reading the same newest messages."""
    if not skip or not uids:
        return uids[-limit:]
    fresh: list[bytes] = []
    for i in range(len(uids), 0, -400):  # newest chunks first
        chunk = uids[max(0, i - 400):i]
        try:
            status, parts = conn.uid("FETCH", b",".join(chunk).decode(), "(X-GM-MSGID)")
        except (imaplib.IMAP4.error, ValueError):
            return uids[-limit:]
        if status != "OK":
            return uids[-limit:]
        ids: dict[bytes, str] = {}
        for p in parts or []:
            line = p[0] if isinstance(p, tuple) else p
            if not isinstance(line, bytes):
                continue
            u, mid = re.search(rb"UID (\d+)", line), _MSGID.search(line)
            if u and mid:
                ids[u.group(1)] = format(int(mid.group(1)), "x")
        if not ids:  # server didn't echo UIDs: fall back to the plain newest window
            return uids[-limit:]
        for u in reversed(chunk):
            if ids.get(u) not in skip:
                fresh.append(u)
                if len(fresh) >= limit:
                    return list(reversed(fresh))
    return list(reversed(fresh))


def _fetch_sync(address: str, app_password: str, limit: int, skip: set[str], query: str = DEFAULT_QUERY,
                stats: dict | None = None) -> list[dict]:
    stats = stats if stats is not None else {}
    conn = _login(address, app_password)
    try:
        box = _all_mail(conn)
        status, _ = conn.select(box, readonly=True)
        if status != "OK":
            box = "INBOX"
            conn.select(box, readonly=True)
        status, data = conn.uid("SEARCH", "X-GM-RAW", f'"{query}"')
        uids = (data[0] or b"").split() if status == "OK" and data else []
        stats.update({"mailbox": box.strip('"'), "matched": len(uids), "fallback": False})
        if not uids:  # Gmail search unavailable or empty: plain IMAP date search as a safety net
            status, data = conn.uid("SEARCH", None, "SINCE", _since(30))
            uids = (data[0] or b"").split() if status == "OK" and data else []
            stats.update({"matched": len(uids), "fallback": True})
        uids = _unknown_newest(conn, uids, skip, limit)
        me = address.lower()
        out: list[dict] = []
        skipped = {"known": 0, "own": 0, "unreadable": 0}
        for uid in reversed(uids):  # newest first
            try:
                status, parts = conn.uid("FETCH", uid, "(X-GM-MSGID X-GM-THRID BODY.PEEK[])")
                item = next((x for x in (parts or []) if isinstance(x, tuple) and len(x) == 2), None)
                if status != "OK" or item is None:
                    skipped["unreadable"] += 1
                    continue
                meta, raw = item
                mid, tid = _MSGID.search(meta), _THRID.search(meta)
                if not mid:
                    skipped["unreadable"] += 1
                    continue
                gmail_id = format(int(mid.group(1)), "x")
                thread_id = format(int(tid.group(1)), "x") if tid else gmail_id
                if gmail_id in skip:
                    skipped["known"] += 1
                    continue
                msg = email.message_from_bytes(raw, policy=policy.default)
                sender = str(msg["From"] or "")
                if me and me in sender.lower():
                    skipped["own"] += 1
                    continue  # your own sent mail (All Mail includes it)
                try:
                    received_ms = int(parsedate_to_datetime(msg["Date"]).timestamp() * 1000)
                except (TypeError, ValueError):
                    received_ms = 0
                try:
                    body = _text(msg)
                except (LookupError, UnicodeError, KeyError, AttributeError):
                    body = raw.decode("utf-8", errors="ignore")[:20000]
                out.append({"gmail_id": gmail_id, "thread_id": thread_id, "sender": sender,
                            "subject": str(msg["Subject"] or ""), "body": body[:20000], "received_ms": received_ms,
                            "snippet": re.sub(r"\s+", " ", body)[:160]})
            except (imaplib.IMAP4.error, ValueError, TypeError):
                skipped["unreadable"] += 1
        stats["skipped"] = skipped
        stats["fetched"] = len(out)
        return out
    finally:
        with contextlib.suppress(Exception):  # closing is best effort
            conn.logout()


async def verify(address: str, app_password: str) -> None:
    def check() -> None:
        _login(address, app_password).logout()

    await asyncio.to_thread(check)


async def fetch_messages(address: str, app_password: str, limit: int = 50, skip: set[str] | None = None,
                         query: str = DEFAULT_QUERY, stats: dict | None = None) -> list[dict]:
    return await asyncio.to_thread(_fetch_sync, address, app_password, limit, skip or set(), query, stats)
