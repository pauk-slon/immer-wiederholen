from datetime import timedelta
from typing import Any, Final

from wiederholen.school import Tutor

REMIND_AFTER_HOURS_OPTIONS: Final = (4, 8, 12, 24)
DEFAULT_REMIND_AFTER_HOURS: Final = int(Tutor.REMIND_AFTER / timedelta(hours=1))
# Stored as remind_after_hours=0 rather than None, so "turned off" stays
# distinguishable from "never chose anything" (which means the default).
REMINDERS_OFF: Final = 0


def get_remind_after_hours(state: dict[str, Any]) -> int:
    # Anything not currently offered (an option dropped since the learner
    # picked it, or garbage) falls back to the default rather than failing.
    hours = state.get("remind_after_hours")
    if hours == REMINDERS_OFF or hours in REMIND_AFTER_HOURS_OPTIONS:
        return hours
    return DEFAULT_REMIND_AFTER_HOURS


def get_remind_after(state: dict[str, Any]) -> timedelta | None:
    hours = get_remind_after_hours(state)
    return None if hours == REMINDERS_OFF else timedelta(hours=hours)
