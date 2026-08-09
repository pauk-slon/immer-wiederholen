from collections.abc import Generator, Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Final, NotRequired, TypedDict, TypeIs

from pydantic import AfterValidator, TypeAdapter, ValidationError


class _ScheduleEntry(TypedDict):
    repetition_interval: int
    due_date: Annotated[str, AfterValidator(date.fromisoformat)]
    introduced_at: NotRequired[Annotated[str, AfterValidator(date.fromisoformat)]]


class LastExercise(TypedDict):
    question: str
    answered_at: str
    is_recall_optional: bool
    recall_question: NotRequired[str]
    # NotRequired so a last_exercise recorded before this field existed stays
    # valid rather than being treated as malformed — next_exercise()'s
    # same-pair exclusion just no-ops until the next answer refreshes it.
    word: NotRequired[str]
    topic: NotRequired[str]


class NewWordBudget(TypedDict):
    date: str
    count: int


class AnswerStats(TypedDict):
    date: str
    answered: int
    correct: int


class Journal:
    _SCHEDULE_ENTRY_ADAPTER: Final = TypeAdapter(_ScheduleEntry)
    _WORD_SCHEDULE_KEY: Final = "word_schedule"
    _TODAY_ANSWERS_KEY: Final = "today_answers"
    _NEW_WORD_BUDGET_KEY: Final = "new_word_budget"

    def __init__(self, data: dict, *, today: date | None = None) -> None:
        self._data = data
        self._today = today if today is not None else datetime.now(UTC).date()

    def get_last_exercise(self) -> LastExercise | None:
        return self._data.get("last_exercise")

    def record_mark(
        self,
        question: str,
        word: str,
        topic: str,
        *,
        is_answer_correct: bool,
        is_recall_optional: bool,
    ) -> tuple[bool, int]:
        self._data["last_exercise"] = LastExercise(
            question=question,
            word=word,
            topic=topic,
            answered_at=datetime.now(UTC).isoformat(),
            is_recall_optional=is_recall_optional,
        )
        answered, right = self.get_answer_stats_today()
        self._data[self._TODAY_ANSWERS_KEY] = AnswerStats(
            date=self._today.isoformat(),
            answered=answered + 1,
            correct=right + (1 if is_answer_correct else 0),
        )
        schedule_entry = self._get_or_create_schedule_entry(word, topic)
        is_new = "introduced_at" not in schedule_entry
        if is_new:
            schedule_entry["introduced_at"] = self._today.isoformat()
        return is_new, schedule_entry["repetition_interval"]

    @property
    def last_reminded_at(self) -> datetime | None:
        if (raw_value := self._data.get("last_reminded_at")) is not None:
            return datetime.fromisoformat(raw_value)

    @last_reminded_at.setter
    def last_reminded_at(self, value: datetime) -> None:
        self._data["last_reminded_at"] = value.isoformat()

    def _get_self_expiring(self, key: str) -> dict | None:
        # Stale (not-today) values are simply treated as absent — no
        # explicit cleanup needed.
        value = self._data.get(key)
        if value is None or value["date"] != self._today.isoformat():
            return None
        return value

    def get_new_word_budget(self) -> int:
        budget = self._get_self_expiring(self._NEW_WORD_BUDGET_KEY)
        return budget["count"] if budget is not None else 0

    def bump_new_word_budget(self, amount: int) -> int:
        new_count = self.get_new_word_budget() + amount
        self._data[self._NEW_WORD_BUDGET_KEY] = NewWordBudget(
            date=self._today.isoformat(),
            count=new_count,
        )
        return new_count

    def get_answer_stats_today(self) -> tuple[int, int]:
        stats = self._get_self_expiring(self._TODAY_ANSWERS_KEY)
        if stats is None:
            return 0, 0
        return stats["answered"], stats["correct"]

    def _get_word_schedule(self, *, create_if_missing: bool = False) -> dict:
        if create_if_missing:
            return self._data.setdefault(self._WORD_SCHEDULE_KEY, {})
        return self._data.get(self._WORD_SCHEDULE_KEY, {})

    def _get_topic_schedule(
        self, word: str, *, create_if_missing: bool = False
    ) -> dict:
        word_schedule = self._get_word_schedule(create_if_missing=create_if_missing)
        topic_schedule = word_schedule.get(word)
        if isinstance(topic_schedule, dict):
            return topic_schedule
        if not create_if_missing:
            return {}
        topic_schedule = word_schedule[word] = {}
        return topic_schedule

    @classmethod
    def reset_progress(cls, data: dict) -> None:
        data[cls._WORD_SCHEDULE_KEY] = {}
        data.pop(cls._TODAY_ANSWERS_KEY, None)

    @classmethod
    def _is_valid_schedule_entry(cls, schedule_entry: object) -> TypeIs[_ScheduleEntry]:
        try:
            cls._SCHEDULE_ENTRY_ADAPTER.validate_python(schedule_entry, strict=True)
        except ValidationError:
            return False
        return True

    def _get_schedule_entry(self, word: str, topic: str) -> _ScheduleEntry | None:
        topic_schedule = self._get_topic_schedule(word)
        schedule_entry = topic_schedule.get(topic)
        return schedule_entry if self._is_valid_schedule_entry(schedule_entry) else None

    def get_repetition_interval(self, word: str, topic: str) -> int | None:
        schedule_entry = self._get_schedule_entry(word, topic)
        return (
            schedule_entry["repetition_interval"]
            if schedule_entry is not None
            else None
        )

    def _get_or_create_schedule_entry(self, word: str, topic: str) -> _ScheduleEntry:
        topic_schedule = self._get_topic_schedule(word, create_if_missing=True)
        schedule_entry = topic_schedule.get(topic)
        if not self._is_valid_schedule_entry(schedule_entry):
            schedule_entry = topic_schedule[topic] = _ScheduleEntry(
                repetition_interval=0, due_date=date.min.isoformat()
            )
        return schedule_entry

    def schedule_pair(
        self,
        word: str,
        topic: str,
        *,
        repetition_interval: int,
        due_interval: int | None = None,
    ) -> None:
        # If the due date should differ from today + repetition_interval,
        # set it explicitly via due_interval.
        if due_interval is None:
            due_interval = repetition_interval
        schedule_entry = self._get_or_create_schedule_entry(word, topic)
        schedule_entry["repetition_interval"] = repetition_interval
        schedule_entry["due_date"] = (
            self._today + timedelta(days=due_interval)
        ).isoformat()

    def _iter_valid_topics(
        self, topic_schedule: dict
    ) -> Generator[tuple[str, _ScheduleEntry]]:
        for topic, schedule_entry in topic_schedule.items():
            if not isinstance(topic, str):
                continue
            if self._is_valid_schedule_entry(schedule_entry):
                yield topic, schedule_entry

    def _iter_valid_scheduled_pairs(
        self,
    ) -> Generator[tuple[str, Generator[tuple[str, _ScheduleEntry]]]]:
        for word, topic_schedule in self._get_word_schedule().items():
            if not isinstance(word, str) or not isinstance(topic_schedule, dict):
                continue
            yield word, self._iter_valid_topics(topic_schedule)

    def iter_scheduled_pairs(
        self,
        *,
        only_due_today: bool = False,
        is_introduced: bool | None = None,
    ) -> Generator[tuple[str, str]]:
        for word, topic_schedule in self._iter_valid_scheduled_pairs():
            for topic, schedule_entry in topic_schedule:
                if is_introduced is not None and (
                    "introduced_at" in schedule_entry
                ) != is_introduced:
                    continue
                if (
                    only_due_today
                    and date.fromisoformat(schedule_entry["due_date"]) > self._today
                ):
                    continue
                yield word, topic

    @staticmethod
    def _get_introduced_dates(
        topic_schedule: Iterator[tuple[str, _ScheduleEntry]],
    ) -> set[str]:
        return {
            schedule_entry["introduced_at"]
            for _topic, schedule_entry in topic_schedule
            if "introduced_at" in schedule_entry
        }

    def get_words_introduced_today(self) -> set[str]:
        today = self._today.isoformat()
        return {
            word
            for word, topic_schedule in self._iter_valid_scheduled_pairs()
            if self._get_introduced_dates(topic_schedule) == {today}
        }

    def get_words_already_introduced(self) -> set[str]:
        return {
            word
            for word, topic_schedule in self._iter_valid_scheduled_pairs()
            if self._get_introduced_dates(topic_schedule)
        }
