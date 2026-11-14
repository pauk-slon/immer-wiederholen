from collections.abc import Container
from datetime import datetime, timedelta
from typing import Final


class Lesson:
    # A lesson is conversation state, not learning state: each frontend keeps
    # its own as a plain dict next to the exercise it shows (the bot in FSM
    # data, the web app in WebSessionStore), and Tutor reads and writes it
    # through this class, the way StudentRecord wraps the student record.
    # The dict holds Exercise.content_key values, not exercises, so an
    # exercise that is no longer in the (possibly restricted) course is
    # skipped instead of shown in an outdated form.
    _ACTIVE_AT_KEY: Final = "active_at"
    _SIZE_KEY: Final = "size"
    _EXERCISE_KEYS_KEY: Final = "exercise_keys"
    _FINISHED_KEY: Final = "finished"
    _CORRECT_KEY: Final = "correct"
    # A lesson that nobody used for this long is dropped, not continued: its
    # pairs come back as due reviews anyway. A time since the last activity,
    # not a calendar day, which the bot can't know without a time zone (see
    # ADR 0028)
    EXPIRES_AFTER: Final = timedelta(hours=2)

    def __init__(self, data: dict, *, now: datetime) -> None:
        self._data = data
        self._now = now

    def _is_started(self) -> bool:
        return self._ACTIVE_AT_KEY in self._data

    def _touch(self) -> None:
        self._data[self._ACTIVE_AT_KEY] = self._now.isoformat()

    def is_current(self) -> bool:
        active_at = self._data.get(self._ACTIVE_AT_KEY)
        if not isinstance(active_at, str):
            return False
        try:
            return self._now - datetime.fromisoformat(active_at) <= self.EXPIRES_AFTER
        except ValueError:
            return False

    def _get_exercise_keys(self) -> list[str]:
        exercise_keys = self._data.get(self._EXERCISE_KEYS_KEY)
        if not isinstance(exercise_keys, list):
            return []
        return [key for key in exercise_keys if isinstance(key, str)]

    @property
    def size(self) -> int:
        size = self._data.get(self._SIZE_KEY)
        return size if isinstance(size, int) else 0

    @property
    def given(self) -> int:
        # The exercises that the lesson gave, the shown one included
        return max(self.size - len(self._get_exercise_keys()), 0)

    @property
    def correct(self) -> int:
        correct = self._data.get(self._CORRECT_KEY)
        return correct if isinstance(correct, int) else 0

    def retain_exercise_keys(self, known_keys: Container[str]) -> None:
        # Drops the keys that the caller can't give, all at once, so the size
        # counts only the exercises that the lesson gives, and "3/5" and the
        # summary stay true from the next exercise on
        exercise_keys = self._get_exercise_keys()
        retained = [key for key in exercise_keys if key in known_keys]
        if len(retained) == len(exercise_keys):
            return
        # A new list, as in take_exercise_key()
        self._data[self._EXERCISE_KEYS_KEY] = retained
        self._data[self._SIZE_KEY] = max(
            self.size - (len(exercise_keys) - len(retained)), 0
        )

    def record_answer(self, *, is_correct: bool) -> None:
        # An answer is activity too, so an answer to an exercise that waited
        # longer than EXPIRES_AFTER lets the lesson continue
        if not self._is_started() or self._data.get(self._FINISHED_KEY):
            return
        self._touch()
        if is_correct:
            self._data[self._CORRECT_KEY] = self.correct + 1

    def start(self, exercise_keys: list[str]) -> None:
        self._data.clear()
        self._data.update(
            {
                self._ACTIVE_AT_KEY: self._now.isoformat(),
                self._SIZE_KEY: len(exercise_keys),
                self._EXERCISE_KEYS_KEY: list(exercise_keys),
            }
        )

    def take_exercise_key(self) -> str | None:
        if not self.is_current():
            return None
        exercise_keys = self._get_exercise_keys()
        if not exercise_keys:
            return None
        # A new list, not pop(): the frontend may hand in a shallow copy of
        # its stored dict, and the stored list must change only when the
        # frontend saves the lesson
        self._data[self._EXERCISE_KEYS_KEY] = exercise_keys[1:]
        self._touch()
        return exercise_keys[0]

    def finish(self) -> bool:
        # True only once per lesson, for the answer to its last exercise.
        # Also for an expired lesson: it gives no more exercises, but the
        # learner can still answer the one that it gave last
        if (
            not self._is_started()
            or self._get_exercise_keys()
            or self._data.get(self._FINISHED_KEY)
        ):
            return False
        self._data[self._FINISHED_KEY] = True
        return True
