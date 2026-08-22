"""A transport-agnostic store of per-student state: journal, language, ai_mode,
whatever else a client needs to remember between turns — one JSON blob per
`student_id`. Deliberately knows nothing about Telegram or aiogram, unlike
`wiederholen.bot.redis_storage.AiogramFsmStorage` which wraps this to satisfy
aiogram's own `BaseStorage` interface for the polling bot. This is what lets
`wiederholen.bot.reminder` (no aiogram FSM routing needs) and any future
non-Telegram frontend (a web chat, say) address the same backend directly with
their own notion of `student_id`, without pulling in aiogram at all.

`wiederholen.tutoring` (`Tutor`/`Journal`) still never touches this or any
other storage — it only ever receives a plain `dict` — so this module doesn't
change that invariant, it just replaces what used to feed that dict in from
aiogram's own Telegram-shaped key format.
"""

import json
from collections.abc import AsyncIterator
from typing import Any, Self

from redis.asyncio import Redis


class StudentStore:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    @classmethod
    def from_url(cls, url: str) -> Self:
        return cls(Redis.from_url(url))

    @staticmethod
    def _key(student_id: str) -> str:
        return f"student:{student_id}"

    async def get(self, student_id: str) -> dict[str, Any]:
        value = await self.redis.get(self._key(student_id))
        if value is None:
            return {}
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        return json.loads(value)

    async def set(self, student_id: str, data: dict[str, Any]) -> None:
        key = self._key(student_id)
        if not data:
            # Mirrors aiogram's own RedisStorage.set_data: an empty dict is
            # stored as "no key at all" rather than a literal "{}", so a
            # student who's never interacted (or whose data was wiped, e.g.
            # via /reset touching only part of it) doesn't linger in
            # iter_items() as a hollow entry.
            await self.redis.delete(key)
            return
        await self.redis.set(key, json.dumps(data))

    async def iter_items(self) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        async for raw_key in self.redis.scan_iter(match=self._key("*")):
            key = raw_key.decode() if isinstance(raw_key, bytes) else raw_key
            student_id = key.removeprefix(self._key(""))
            yield student_id, await self.get(student_id)

    async def close(self) -> None:
        await self.redis.aclose(close_connection_pool=True)
