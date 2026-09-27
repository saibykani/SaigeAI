"""Serverless entrypoint (Vercel). Local and container runs use `uvicorn app.main:app`."""

import json

try:
    from app.main import app
except Exception as exc:  # noqa: BLE001 - surface a startup failure instead of an opaque 500
    _body = json.dumps({"detail": "Backend failed to start", "reason": f"{type(exc).__name__}: {exc}"[:300]}).encode()

    async def app(scope, receive, send):  # minimal ASGI app reporting why startup failed
        if scope["type"] != "http":
            return
        await send({"type": "http.response.start", "status": 503, "headers": [(b"content-type", b"application/json")]})
        await send({"type": "http.response.body", "body": _body})

__all__ = ["app"]
