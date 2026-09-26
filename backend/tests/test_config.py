import pytest
from pydantic import ValidationError

from app.config import Settings

REQUIRED = {"MONGODB_URI": "mongodb://x", "JWT_SECRET": "s" * 40}


def test_blank_variables_fall_back_to_defaults(monkeypatch):
    for key, value in REQUIRED.items():
        monkeypatch.setenv(key, value)
    for key in ("MONGODB_DB", "ACCESS_TOKEN_MINUTES", "COOKIE_SECURE", "MAX_UPLOAD_MB",
                "LLM_MODEL", "ENVIRONMENT", "FRONTEND_URL"):
        monkeypatch.setenv(key, "")
    s = Settings(_env_file=None)
    assert s.mongodb_db == "saige_ai"
    assert s.access_token_minutes == 15
    assert s.cookie_secure is False
    assert s.max_upload_mb == 5
    assert s.llm_model == "claude-opus-5"


def test_blank_jwt_secret_still_rejected(monkeypatch):
    monkeypatch.setenv("MONGODB_URI", "mongodb://x")
    monkeypatch.setenv("JWT_SECRET", "")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_cors_origins_comma_separated(monkeypatch):
    for key, value in REQUIRED.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("CORS_ORIGINS", "https://a.app, https://b.app")
    assert Settings(_env_file=None).cors_origins == ["https://a.app", "https://b.app"]


def test_llm_enabled_only_for_real_anthropic_keys(monkeypatch):
    for key, value in REQUIRED.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")
    assert Settings(_env_file=None).llm_enabled is False
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-example")
    assert Settings(_env_file=None).llm_enabled is True


async def test_write_rate_limit_backstop(client, auth):
    from app.services.rate_limit import write_limiter

    write_limiter.max_calls = 3
    try:
        codes = [(await client.post("/api/notifications/read-all", headers=auth)).status_code for _ in range(5)]
        assert codes == [200, 200, 200, 429, 429]
        # Reads are never limited by the write backstop.
        assert (await client.get("/api/notifications", headers=auth)).status_code == 200
    finally:
        write_limiter.max_calls = 180


def test_client_key_prefers_forwarded_address():
    from starlette.requests import Request

    from app.services.rate_limit import client_key

    req = Request({"type": "http", "headers": [(b"x-forwarded-for", b"203.0.113.9, 10.0.0.1")], "client": ("10.0.0.1", 1)})
    assert client_key(req) == "203.0.113.9"
    assert client_key(Request({"type": "http", "headers": [], "client": ("10.0.0.2", 1)})) == "10.0.0.2"
