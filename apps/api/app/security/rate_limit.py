"""Fixed-window login rate limit in Redis. Keys do not store the raw email."""

import hashlib

from redis.asyncio import Redis

from app.problems import PROBLEM_RATE_LIMIT, ProblemError


class RedisRateLimiter:
    def __init__(
        self,
        client: Redis,
        limit: int = 10,
        window_seconds: int = 60,
        detail: str = "Too many login attempts. Try again later.",
    ) -> None:
        self.client = client
        self.limit = limit
        self.window_seconds = window_seconds
        self.detail = detail

    async def check(self, ip: str, email: str) -> None:
        email_hash = hashlib.sha256(email.lower().encode("utf-8")).hexdigest()
        keys = (f"rl:login:ip:{ip}", f"rl:login:email:{email_hash}")
        for key in keys:
            await self._bump(key)

    async def hit(self, scope: str, *parts: str) -> None:
        for index, part in enumerate(parts):
            digest = hashlib.sha256(f"{index}:{part}".encode()).hexdigest()
            await self._bump(f"rl:{scope}:{digest}")

    async def _bump(self, key: str) -> None:
        count = int(await self.client.incr(key))
        if count == 1:
            await self.client.expire(key, self.window_seconds)
        else:
            ttl = int(await self.client.ttl(key))
            if ttl < 0:
                await self.client.expire(key, self.window_seconds)
        if count > self.limit:
            raise ProblemError(
                429,
                "Too Many Requests",
                self.detail,
                PROBLEM_RATE_LIMIT,
            )
