"""An abstract, transport-agnostic backend for exactly one thing: the journal
dict `wiederholen.tutoring.Journal`/`Tutor` operate on, addressed by a plain
string `student_id` — for the Telegram bot that's `str(chat_id)`, for any
future non-Telegram frontend (a web chat, say) it'd be whatever notion of
identity that frontend uses.

Deliberately scoped to *only* the journal, not the rest of a chat's per-session
state (language, ai_mode, mid-conversation UI bookkeeping, …) — that's
session/UI state a transport keeps by whatever means suits it (e.g. the
Telegram bot's own aiogram FSM storage), since it's not the kind of thing a
web frontend would need to share with a Telegram chat the way the actual
learning record is. `wiederholen.tutoring` (`Tutor`/`Journal`) still never
touches this or any other storage itself — it only ever receives a plain
`dict` — so this module doesn't change that invariant, it's a layer between a
transport and `Tutor`.
"""

import copy
import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Self

from redis.asyncio import Redis


class JournalBackend(ABC):
    @abstractmethod
    async def _get(self, student_id: str) -> dict:
        """The student's journal dict, or `{}` if they have none yet."""

    @abstractmethod
    async def _save(self, student_id: str, journal: dict) -> None:
        """Overwrite the student's journal dict wholesale."""

    @asynccontextmanager
    async def open(self, student_id: str) -> AsyncIterator[dict]:
        """Fetch a student's journal and yield it for in-place mutation via
        `Tutor`. Saved back on exit only if it actually changed from what was
        fetched — regardless of whether the body raised, so a mutation
        already applied (e.g. `check_answer()` recording an answer) isn't
        lost just because something *after* it, like sending a reply, failed;
        and a caller that only reads never triggers a write at all. This is
        the sole public way to read or write one student's journal — built on
        `_get()`/`_save()` alone, which no caller outside this class needs
        directly.
        """
        journal = await self._get(student_id)
        before = copy.deepcopy(journal)
        try:
            yield journal
        finally:
            if journal != before:
                await self._save(student_id, journal)

    @abstractmethod
    def __aiter__(self) -> AsyncIterator[str]:
        """Every `student_id` with a stored journal — the only way to
        discover which students exist at all, for a caller that needs to
        sweep all of them (there's no separate registry). Read a given
        student's journal itself via `open()`.
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

    async def _get(self, student_id: str) -> dict:
        value = await self.redis.get(self._key(student_id))
        if value is None:
            return {}
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        return json.loads(value)

    async def _save(self, student_id: str, journal: dict) -> None:
        key = self._key(student_id)
        if not journal:
            # An empty journal is stored as "no key at all" rather than a
            # literal "{}", so a student with nothing recorded yet doesn't
            # linger in __aiter__() as a hollow entry.
            await self.redis.delete(key)
            return
        await self.redis.set(key, json.dumps(journal))

    async def __aiter__(self) -> AsyncIterator[str]:
        async for raw_key in self.redis.scan_iter(match=self._key("*")):
            key = raw_key.decode() if isinstance(raw_key, bytes) else raw_key
            yield key.removeprefix(self._key(""))

    async def close(self) -> None:
        await self.redis.aclose(close_connection_pool=True)
