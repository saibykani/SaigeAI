"""In-process sliding-window rate limiter.

Adequate for a single instance; replace with a Redis-backed limiter when scaling out.
"""

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


def client_key(request: Request) -> str:
    """Best client identifier: behind Vercel's proxy request.client is the proxy, so prefer the
    forwarded client address. Used only for rate limiting, never for authorisation."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")


class RateLimiter:
    def __init__(self, max_calls: int, window_seconds: float) -> None:
        self.max_calls = max_calls
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str) -> bool:
        now = time.monotonic()
        q = self._hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.max_calls:
            return False
        q.append(now)
        return True

    def reset(self) -> None:
        self._hits.clear()

    def dependency(self, scope: str):
        async def _check(request: Request) -> None:
            if not self.hit(f"{scope}:{client_key(request)}"):
                raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests")

        return _check


auth_limiter = RateLimiter(max_calls=10, window_seconds=60)
# Backstop for every write request (POST/PUT/PATCH/DELETE) per client; feature limits are stricter.
write_limiter = RateLimiter(max_calls=180, window_seconds=60)
upload_limiter = RateLimiter(max_calls=30, window_seconds=60)
