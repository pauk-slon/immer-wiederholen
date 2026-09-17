import secrets
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Literal, Self

from redis.asyncio import Redis

from wiederholen.school.student_record_book import StudentID

type AuthProvider = Literal["telegram"]


class IdentityAlreadyLinkedError(ValueError):
    """Raised by link_identity() when (provider, identifier) already
    resolves to a *different* student_id than the one being linked to —
    linking would otherwise silently reassign it to a new owner.
    """


class StudentIdentityStore(ABC):
    @abstractmethod
    async def _get(self, provider: AuthProvider, identifier: str) -> StudentID | None:
        """The student_id (provider, identifier) already resolves to, or
        None if nothing is linked yet."""

    @abstractmethod
    async def _create_if_absent(
        self, provider: AuthProvider, identifier: str, student_id: StudentID
    ) -> StudentID:
        """Atomically store (provider, identifier) -> student_id if no row
        exists yet. Returns whichever student_id ends up stored — the one
        just written, or a pre-existing one a concurrent caller (or an
        earlier link_identity() call) already wrote."""

    async def resolve_or_create_student_id(
        self, provider: AuthProvider, identifier: str
    ) -> StudentID:
        existing = await self._get(provider, identifier)
        if existing is not None:
            return existing
        return await self._create_if_absent(
            provider, identifier, secrets.token_urlsafe(32)
        )

    async def link_identity(
        self, student_id: StudentID, provider: AuthProvider, identifier: str
    ) -> None:
        actual = await self._create_if_absent(provider, identifier, student_id)
        if actual != student_id:
            raise IdentityAlreadyLinkedError(
                f"{provider}:{identifier} is already linked to a different student"
            )

    @abstractmethod
    def iter_identifiers(
        self, provider: AuthProvider
    ) -> AsyncIterator[tuple[str, StudentID]]:
        """Every (identifier, student_id) currently linked for that provider —
        e.g. for reminder.py to sweep every Telegram chat with a linked
        student, without touching StudentRecordBook at all."""


class RedisStudentIdentityStore(StudentIdentityStore):
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    @classmethod
    def from_url(cls, url: str) -> Self:
        return cls(Redis.from_url(url))

    @staticmethod
    def _key(provider: AuthProvider, identifier: str) -> str:
        return f"identity:{provider}:{identifier}"

    async def _get(self, provider: AuthProvider, identifier: str) -> StudentID | None:
        value = await self.redis.get(self._key(provider, identifier))
        if value is None:
            return None
        return value.decode("utf-8") if isinstance(value, bytes) else value

    async def _create_if_absent(
        self, provider: AuthProvider, identifier: str, student_id: StudentID
    ) -> StudentID:
        key = self._key(provider, identifier)
        if await self.redis.set(key, student_id, nx=True):
            return student_id
        # Lost the race (or the row already existed) — read back whatever's
        # actually there now rather than the value we tried to write.
        existing = await self._get(provider, identifier)
        assert existing is not None
        return existing

    async def iter_identifiers(
        self, provider: AuthProvider
    ) -> AsyncIterator[tuple[str, StudentID]]:
        prefix = self._key(provider, "")
        async for raw_key in self.redis.scan_iter(match=f"{prefix}*"):
            key = raw_key.decode() if isinstance(raw_key, bytes) else raw_key
            identifier = key.removeprefix(prefix)
            student_id = await self._get(provider, identifier)
            if student_id is not None:
                yield identifier, student_id

    async def _close(self) -> None:
        await self.redis.aclose(close_connection_pool=True)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self._close()
