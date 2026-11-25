"""How many lesson recalls a chat gets per day (see docs/bot.md)."""

import time
from typing import Final

from .feature_flags import LESSON_RECALL_UNLIMITED_FLAG, has_feature

DAILY_LESSON_RECALLS: Final = 3
_DAY_SECONDS: Final = 24 * 60 * 60

# Lasting chat state: when each lesson recall of the last day started
STARTED_AT_KEY: Final = "lesson_recall_started_at"


def _started_in_the_last_day(state_data: dict, now: float) -> list[float]:
    return [
        started_at
        for started_at in state_data.get(STARTED_AT_KEY, [])
        if now - started_at < _DAY_SECONDS
    ]


def has_lesson_recall_left(
    feature_flags: dict[str, frozenset[int]] | None, chat_id: int, state_data: dict
) -> bool:
    if has_feature(feature_flags or {}, LESSON_RECALL_UNLIMITED_FLAG, chat_id):
        return True
    started = _started_in_the_last_day(state_data, time.time())
    return len(started) < DAILY_LESSON_RECALLS


def seconds_until_lesson_recall(state_data: dict) -> float:
    """How long until the oldest lesson recall of the last day stops counting.
    Only for a chat that has used up the limit."""
    now = time.time()
    return min(_started_in_the_last_day(state_data, now)) + _DAY_SECONDS - now


def count_lesson_recall(state_data: dict) -> dict:
    """The FSM data update that counts a new lesson recall."""
    now = time.time()
    return {STARTED_AT_KEY: [*_started_in_the_last_day(state_data, now), now]}
