from datetime import date
from typing import Final


class Lesson:
    # A lesson is conversation state, not learning state: each frontend keeps
    # its own as a plain dict next to the exercise it shows (the bot in FSM
    # data, the web app in WebSessionStore), and Tutor reads and writes it
    # through this class, the way StudentRecord wraps the student record.
    # The dict holds Exercise.content_key values, not exercises, so an
    # exercise that is no longer in the (possibly restricted) course is
    # skipped instead of shown in an outdated form.
    _DATE_KEY: Final = "date"
    _SIZE_KEY: Final = "size"
    _EXERCISE_KEYS_KEY: Final = "exercise_keys"
    _FINISHED_KEY: Final = "finished"

    def __init__(self, data: dict, *, today: date) -> None:
        self._data = data
        self._today = today

    def _is_current(self) -> bool:
        # A lesson from an earlier day is dropped, not continued: its pairs
        # come back as due reviews anyway
        return self._data.get(self._DATE_KEY) == self._today.isoformat()

    def _get_exercise_keys(self) -> list[str]:
        exercise_keys = self._data.get(self._EXERCISE_KEYS_KEY)
        if not isinstance(exercise_keys, list):
            return []
        return [key for key in exercise_keys if isinstance(key, str)]

    @property
    def size(self) -> int:
        size = self._data.get(self._SIZE_KEY)
        return size if isinstance(size, int) else 0

    def start(self, exercise_keys: list[str]) -> None:
        self._data.clear()
        self._data.update(
            {
                self._DATE_KEY: self._today.isoformat(),
                self._SIZE_KEY: len(exercise_keys),
                self._EXERCISE_KEYS_KEY: list(exercise_keys),
            }
        )

    def take_exercise_key(self) -> str | None:
        if not self._is_current():
            return None
        exercise_keys = self._get_exercise_keys()
        if not exercise_keys:
            return None
        # A new list, not pop(): the frontend may hand in a shallow copy of
        # its stored dict, and the stored list must change only when the
        # frontend saves the lesson
        self._data[self._EXERCISE_KEYS_KEY] = exercise_keys[1:]
        return exercise_keys[0]

    def finish(self) -> bool:
        # True only once per lesson, for the answer to its last exercise
        if (
            not self._is_current()
            or self._get_exercise_keys()
            or self._data.get(self._FINISHED_KEY)
        ):
            return False
        self._data[self._FINISHED_KEY] = True
        return True
