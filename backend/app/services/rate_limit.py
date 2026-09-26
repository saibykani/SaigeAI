"""In-process sliding-window rate limiter.

Adequate for a single instance; replace with a Redis-backed limiter when scaling out.
"""

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


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
            client = request.client.host if request.client else "unknown"
            if not self.hit(f"{scope}:{client}"):
                raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests")

        return _check


auth_limiter = RateLimiter(max_calls=10, window_seconds=60)
upload_limiter = RateLimiter(max_calls=30, window_seconds=60)
