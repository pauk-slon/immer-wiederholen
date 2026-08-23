"""Ephemeral per-student UI state for the web frontend — mirrors what
aiogram's own FSM storage holds for the Telegram bot (`shown_exercise`),
scoped to just what `wiederholen.web` itself needs. Deliberately not part
of `StudentRecordBook`: this is session/UI state, not the learning record
(see CLAUDE.md's Persistence section for why the Telegram bot keeps those
two separate too).
"""

import json
from typing import Final, Self

from redis.asyncio import Redis

from wiederholen.school import Exercise, StudentID

# An abandoned session's shown exercise expires rather than lingering
# forever — a student who never answers isn't worth remembering past a
# single sitting.
_TTL_SECONDS: Final = 60 * 60


class WebSessionStore:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    @classmethod
    def from_url(cls, url: str) -> Self:
        return cls(Redis.from_url(url))

    @staticmethod
    def _key(student_id: StudentID) -> str:
        return f"web_session:{student_id}"

    async def get_shown_exercise(self, student_id: StudentID) -> Exercise | None:
        raw = await self.redis.get(self._key(student_id))
        if raw is None:
            return None
        return Exercise.from_dict(json.loads(raw))

    async def set_shown_exercise(
        self, student_id: StudentID, exercise: Exercise
    ) -> None:
        await self.redis.set(
            self._key(student_id),
            json.dumps(exercise.to_dict()),
            ex=_TTL_SECONDS,
        )

    async def _close(self) -> None:
        await self.redis.aclose(close_connection_pool=True)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self._close()
