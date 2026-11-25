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


def seconds_until_lesson_recall(
    feature_flags: dict[str, frozenset[int]] | None, chat_id: int, state_data: dict
) -> float | None:
    """None if the chat has a lesson recall left. Otherwise, how long until
    the last day has fewer than DAILY_LESSON_RECALLS of them. The day can have
    more, for example from a time with the unlimited flag."""
    if has_feature(feature_flags or {}, LESSON_RECALL_UNLIMITED_FLAG, chat_id):
        return None
    now = time.time()
    started = sorted(_started_in_the_last_day(state_data, now))
    if len(started) < DAILY_LESSON_RECALLS:
        return None
    return started[len(started) - DAILY_LESSON_RECALLS] + _DAY_SECONDS - now


def has_lesson_recall_left(
    feature_flags: dict[str, frozenset[int]] | None, chat_id: int, state_data: dict
) -> bool:
    return seconds_until_lesson_recall(feature_flags, chat_id, state_data) is None


def count_lesson_recall(state_data: dict) -> dict:
    """The FSM data update that counts a new lesson recall."""
    now = time.time()
    return {STARTED_AT_KEY: [*_started_in_the_last_day(state_data, now), now]}
