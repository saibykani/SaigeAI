import os

# Test configuration must be in place before the app (and its settings) are imported.
os.environ.setdefault("MONGODB_URI", "mongodb://unused-in-tests")
os.environ.setdefault("JWT_SECRET", "test-secret-" + "x" * 40)
os.environ.setdefault("ENVIRONMENT", "test")

import httpx  # noqa: E402
import pytest  # noqa: E402
from mongomock_motor import AsyncMongoMockClient  # noqa: E402

from app.database import mongo  # noqa: E402
from app.main import app  # noqa: E402
from app.services.rate_limit import auth_limiter, upload_limiter  # noqa: E402

CSRF = {"X-Requested-With": "saige"}


@pytest.fixture
async def db():
    database = AsyncMongoMockClient(tz_aware=True)["saige_test"]
    mongo.set_db(database)
    await mongo.ensure_indexes(database)
    auth_limiter.reset()
    upload_limiter.reset()
    yield database
    mongo.set_db(None)


@pytest.fixture
async def client(db):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


async def register(client: httpx.AsyncClient, email: str = "asha@example.com",
                   password: str = "correct-horse-battery", name: str = "Asha Rao") -> dict:
    r = await client.post("/api/auth/register",
                          json={"email": email, "password": password, "name": name})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
async def auth(client) -> dict:
    return await register(client)
