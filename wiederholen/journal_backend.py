"""An abstract, transport-agnostic backend for exactly one thing: the journal
dict `wiederholen.tutoring.Journal`/`Tutor` operate on, addressed by a plain
string `student_id` — for the Telegram bot that's `str(chat_id)`, for any
future non-Telegram frontend (a web chat, say) it'd be whatever notion of
identity that frontend uses.

Deliberately scoped to *only* the journal, not the rest of a chat's per-session
state (language, ai_mode, mid-conversation UI bookkeeping, …) — that's Telegram
session/UI state that stays in aiogram's own FSM storage (see
`wiederholen.bot.bootstrap`), since it's not the kind of thing a web frontend
would need to share with the Telegram bot the way the actual learning record
is. `wiederholen.tutoring` (`Tutor`/`Journal`) still never touches this or any
other storage itself — it only ever receives a plain `dict` — so this module
doesn't change that invariant, it's a layer between a transport and `Tutor`.
"""

import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Self

from redis.asyncio import Redis


class JournalBackend(ABC):
    @abstractmethod
    async def get_journal(self, student_id: str) -> dict:
        """The student's journal dict, or `{}` if they have none yet."""

    @abstractmethod
    async def save_journal(self, student_id: str, journal: dict) -> None:
        """Overwrite the student's journal dict wholesale."""

    @abstractmethod
    def iter_journals(self) -> AsyncIterator[tuple[str, dict]]:
        """Every student with a stored journal, alongside their `student_id`.

        Used by `wiederholen.bot.reminder` to sweep for due reviews — there's
        no separate registry of known students beyond "who has a journal".
        """

    @abstractmethod
    async def close(self) -> None: ...


class RedisJournalBackend(JournalBackend):
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    @classmethod
    def from_url(cls, url: str) -> Self:
        return cls(Redis.from_url(url))

    @staticmethod
    def _key(student_id: str) -> str:
        return f"journal:{student_id}"

    async def get_journal(self, student_id: str) -> dict:
        value = await self.redis.get(self._key(student_id))
        if value is None:
            return {}
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        return json.loads(value)

    async def save_journal(self, student_id: str, journal: dict) -> None:
        key = self._key(student_id)
        if not journal:
            # An empty journal is stored as "no key at all" rather than a
            # literal "{}", so a student with nothing recorded yet doesn't
            # linger in iter_journals() as a hollow entry.
            await self.redis.delete(key)
            return
        await self.redis.set(key, json.dumps(journal))

    async def iter_journals(self) -> AsyncIterator[tuple[str, dict]]:
        async for raw_key in self.redis.scan_iter(match=self._key("*")):
            key = raw_key.decode() if isinstance(raw_key, bytes) else raw_key
            student_id = key.removeprefix(self._key(""))
            yield student_id, await self.get_journal(student_id)

    async def close(self) -> None:
        await self.redis.aclose(close_connection_pool=True)
