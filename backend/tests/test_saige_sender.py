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


async def test_digest_sender_prefers_saige_and_falls_back(monkeypatch, fresh_settings):
    calls = []

    async def fake_find_sender(db, uid):
        calls.append(uid)
        return {"email": "me@gmail.com"}

    monkeypatch.setattr(outbound, "find_sender", fake_find_sender)
    monkeypatch.delenv("SAIGE_MAIL_USER", raising=False)
    monkeypatch.delenv("SAIGE_MAIL_APP_PASSWORD", raising=False)
    assert (await outbound.find_digest_sender(None, "u1"))["email"] == "me@gmail.com"
    get_settings.cache_clear()
    monkeypatch.setenv("SAIGE_MAIL_USER", "saige.noreply@gmail.com")
    monkeypatch.setenv("SAIGE_MAIL_APP_PASSWORD", "x" * 16)
    assert (await outbound.find_digest_sender(None, "u1"))["email"] == "saige.noreply@gmail.com"
    assert calls == ["u1"]
