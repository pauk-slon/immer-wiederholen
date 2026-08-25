"""Ephemeral per-student UI state for the web frontend — mirrors what
aiogram's own FSM storage holds for the Telegram bot (`shown_exercise`,
`shown_recall`), scoped to just what `wiederholen.web` itself needs.
Deliberately not part of `StudentRecordBook`: this is session/UI state, not
the learning record (see CLAUDE.md's Persistence section for why the
Telegram bot keeps those two separate too).
"""

import json
from typing import Final, NotRequired, Self, TypedDict

from redis.asyncio import Redis

from wiederholen.school import Exercise, Recall, StudentID

# An abandoned session's shown exercise expires rather than lingering
# forever — a student who never answers isn't worth remembering past a
# single sitting.
_TTL_SECONDS: Final = 60 * 60


class _SessionState(TypedDict):
    exercise: dict
    # NotRequired, not `dict | None`, so a session written before this field
    # existed (or one written by set_shown_exercise, which never includes
    # it) round-trips through get_shown_recall() as "no recall shown" rather
    # than needing an explicit null every time.
    recall: NotRequired[dict]


class WebSessionStore:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    @classmethod
    def from_url(cls, url: str) -> Self:
        return cls(Redis.from_url(url))

    @staticmethod
    def _key(student_id: StudentID) -> str:
        return f"web_session:{student_id}"

    async def _get_state(self, student_id: StudentID) -> _SessionState | None:
        raw = await self.redis.get(self._key(student_id))
        if raw is None:
            return None
        return json.loads(raw)

    async def _save_state(self, student_id: StudentID, state: _SessionState) -> None:
        await self.redis.set(self._key(student_id), json.dumps(state), ex=_TTL_SECONDS)

    async def get_shown_exercise(self, student_id: StudentID) -> Exercise | None:
        state = await self._get_state(student_id)
        if state is None:
            return None
        return Exercise.from_dict(state["exercise"])

    async def set_shown_exercise(
        self, student_id: StudentID, exercise: Exercise
    ) -> None:
        # Always a fresh envelope, with no "recall" key — a newly shown
        # exercise means any recall from a previous one is no longer
        # relevant, the same way the bot's own last_exercise record gets
        # replaced wholesale on every new exercise.
        await self._save_state(student_id, {"exercise": exercise.to_dict()})

    async def get_shown_recall(self, student_id: StudentID) -> Recall | None:
        state = await self._get_state(student_id)
        if state is None or "recall" not in state:
            return None
        return Recall.from_dict(state["recall"])

    async def set_shown_recall(self, student_id: StudentID, recall: Recall) -> None:
        state = await self._get_state(student_id)
        # A recall is only ever requested for an already-shown exercise —
        # mirrors Tutor.request_recall()'s own `assert last_exercise is not
        # None`.
        assert state is not None
        state["recall"] = recall.to_dict()
        await self._save_state(student_id, state)

    async def _close(self) -> None:
        await self.redis.aclose(close_connection_pool=True)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self._close()
