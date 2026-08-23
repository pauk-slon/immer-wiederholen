"""An abstract, transport-agnostic book of records — one entry per student —
for exactly one thing: the per-student record dict
`wiederholen.tutoring.StudentRecord`/`Tutor` operate on, addressed by a plain
string `student_id` — for the Telegram bot that's `str(chat_id)`, for any
future non-Telegram frontend (a web chat, say) it'd be whatever notion of
identity that frontend uses.

Deliberately scoped to *only* that record, not the rest of a chat's
per-session state (language, ai_mode, mid-conversation UI bookkeeping, …) —
that's session/UI state a transport keeps by whatever means suits it (e.g.
the Telegram bot's own aiogram FSM storage), since it's not the kind of thing
a web frontend would need to share with a Telegram chat the way the actual
learning record is. `wiederholen.tutoring` (`Tutor`/`StudentRecord`) still
never touches this or any other storage itself — it only ever receives a
plain `dict` — so this module doesn't change that invariant, it's a layer
between a transport and `Tutor`.
"""

import copy
import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Self

from redis.asyncio import Redis


class StudentRecordBook(ABC):
    @abstractmethod
    async def _get(self, student_id: str) -> dict:
        """That student's record dict, or `{}` if they have none yet."""

    @abstractmethod
    async def _save(self, student_id: str, student_record: dict) -> None:
        """Overwrite that student's record dict wholesale."""

    @asynccontextmanager
    async def check_out(self, student_id: str) -> AsyncIterator[dict]:
        student_record = await self._get(student_id)
        before = copy.deepcopy(student_record)
        try:
            yield student_record
        finally:
            if student_record != before:
                await self._save(student_id, student_record)

    @abstractmethod
    def __aiter__(self) -> AsyncIterator[str]:
        """Every `student_id` with a stored record — the only way to
        discover which students exist at all, for a caller that needs to
        sweep all of them (there's no separate registry). Read a given
        student's record itself via `check_out()`.
        """


class RedisStudentRecordBook(StudentRecordBook):
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    @classmethod
    def from_url(cls, url: str) -> Self:
        return cls(Redis.from_url(url))

    @staticmethod
    def _key(student_id: str) -> str:
        return f"student_record:{student_id}"

    async def _get(self, student_id: str) -> dict:
        value = await self.redis.get(self._key(student_id))
        if value is None:
            return {}
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        return json.loads(value)

    async def _save(self, student_id: str, student_record: dict) -> None:
        key = self._key(student_id)
        if not student_record:
            # An empty record is stored as "no key at all" rather than a
            # literal "{}", so a student with nothing recorded yet doesn't
            # linger in __aiter__() as a hollow entry.
            await self.redis.delete(key)
            return
        await self.redis.set(key, json.dumps(student_record))

    async def __aiter__(self) -> AsyncIterator[str]:
        async for raw_key in self.redis.scan_iter(match=self._key("*")):
            key = raw_key.decode() if isinstance(raw_key, bytes) else raw_key
            yield key.removeprefix(self._key(""))

    async def _close(self) -> None:
        await self.redis.aclose(close_connection_pool=True)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        # No public close() — releasing the connection is only ever
        # meaningful as part of the usual `async with RedisStudentRecordBook.
        # from_url(...) as store:` lifecycle, not a method callers reach for
        # on their own. Lives here, not on StudentRecordBook: whether there's a
        # connection to release at all — and how — is specific to this
        # backend, not something every StudentRecordBook is guaranteed to have.
        await self._close()
