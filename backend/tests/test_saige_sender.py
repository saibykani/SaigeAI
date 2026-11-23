"""Job digests go out from Saige's own mailbox when SAIGE_MAIL_* is set; otherwise from the user's Gmail."""
import pytest

from app.config import get_settings
from app.email import outbound
from app.services import crypto


@pytest.fixture
def fresh_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_saige_sender_unset_returns_none(monkeypatch, fresh_settings):
    monkeypatch.delenv("SAIGE_MAIL_USER", raising=False)
    monkeypatch.delenv("SAIGE_MAIL_APP_PASSWORD", raising=False)
    assert outbound.saige_sender() is None


def test_saige_sender_configured(monkeypatch, fresh_settings):
    monkeypatch.setenv("SAIGE_MAIL_USER", "saige.noreply@gmail.com")
    monkeypatch.setenv("SAIGE_MAIL_APP_PASSWORD", "abcd efgh ijkl mnop")
    s = outbound.saige_sender()
    assert s and s["email"] == "saige.noreply@gmail.com" and s["system"] is True
    assert s["from_name"] == "Saige AI"
    assert crypto.decrypt(s["app_password_enc"]) == "abcdefghijklmnop"


async def test_digest_sender_order(monkeypatch, fresh_settings):
    """Resend (own domain) > the user's own Gmail (never spam to yourself) > Saige's Gmail mailbox."""
    user_gmail = {"email": "me@gmail.com"}

    async def has_gmail(db, uid):
        return user_gmail

    async def no_gmail(db, uid):
        return None

    for k in ("RESEND_API_KEY", "RESEND_FROM"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("SAIGE_MAIL_USER", "hello.saigeai@gmail.com")
    monkeypatch.setenv("SAIGE_MAIL_APP_PASSWORD", "x" * 16)
    monkeypatch.setattr(outbound, "find_sender", has_gmail)
    assert (await outbound.find_digest_sender(None, "u1"))["email"] == "me@gmail.com"
    monkeypatch.setattr(outbound, "find_sender", no_gmail)
    assert (await outbound.find_digest_sender(None, "u1"))["email"] == "hello.saigeai@gmail.com"
    get_settings.cache_clear()
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("RESEND_FROM", "noreply@saige-ai.in")
    monkeypatch.setattr(outbound, "find_sender", has_gmail)
    s = await outbound.find_digest_sender(None, "u1")
    assert s["email"] == "noreply@saige-ai.in" and s["resend"] is True


async def test_resend_send_posts_to_api(monkeypatch, fresh_settings):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("RESEND_FROM", "noreply@saige-ai.in")
    seen = {}

    class Res:
        status_code = 200

        def json(self):
            return {"id": "msg_1"}

    class Client:
        def __init__(self, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json, headers):
            seen.update(url=url, json=json, headers=headers)
            return Res()

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", Client)
    mid = await outbound.send(outbound.resend_sender(), "Saige AI", "u@gmail.com", "Jobs", "text", html="<p>x</p>")
    assert mid == "msg_1"
    assert seen["url"] == "https://api.resend.com/emails"
    assert seen["json"]["from"] == "Saige AI <noreply@saige-ai.in>" and seen["json"]["to"] == ["u@gmail.com"]
    assert seen["headers"]["Authorization"] == "Bearer re_test"


def test_messages_have_date_and_saige_digests_have_unsubscribe():
    from app.email import smtp
    m = smtp.build_message("a@gmail.com", "Saige AI", "b@gmail.com", "s", "body", html="<p>x</p>")
    assert m["Date"]
