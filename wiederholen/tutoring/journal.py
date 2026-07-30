from datetime import UTC, date, datetime
from typing import Annotated, Final, Literal, NotRequired, TypedDict, overload

from pydantic import AfterValidator, TypeAdapter, ValidationError


class ScheduleEntry(TypedDict):
    interval_days: int
    due_date: Annotated[str, AfterValidator(date.fromisoformat)]
    introduced_at: NotRequired[Annotated[str, AfterValidator(date.fromisoformat)]]


class LastExercise(TypedDict):
    question: str
    answered_at: str
    is_recall_optional: bool
    recall_question: NotRequired[str]


class ExtraNewWords(TypedDict):
    date: str
    count: int


class Journal:
    _SCHEDULE_ENTRY_ADAPTER: Final = TypeAdapter(ScheduleEntry)

    def __init__(self, data: dict) -> None:
        self._data = data

    def get_last_exercise(self) -> LastExercise | None:
        return self._data.get("last_exercise")

    def record_mark(self, question: str, *, was_recall_optional: bool) -> None:
        self._data["last_exercise"] = LastExercise(
            question=question,
            answered_at=datetime.now(UTC).isoformat(),
            is_recall_optional=was_recall_optional,
        )

    @property
    def last_reminded_at(self) -> datetime | None:
        if (raw_value := self._data.get("last_reminded_at")) is not None:
            return datetime.fromisoformat(raw_value)

    @last_reminded_at.setter
    def last_reminded_at(self, value: datetime) -> None:
        self._data["last_reminded_at"] = value.isoformat()

    def get_extra_new_words(self) -> ExtraNewWords | None:
        return self._data.get("extra_new_words")

    def set_extra_new_words(self, extra: ExtraNewWords) -> None:
        self._data["extra_new_words"] = extra

    def get_word_schedule(self, *, create_if_missing: bool = False) -> dict:
        if create_if_missing:
            return self._data.setdefault("word_schedule", {})
        return self._data.get("word_schedule", {})

    def get_topic_schedule(self, word: str, *, create_if_missing: bool = False) -> dict:
        word_schedule = self.get_word_schedule(create_if_missing=create_if_missing)
        topic_schedule = word_schedule.get(word)
        if isinstance(topic_schedule, dict):
            return topic_schedule
        if not create_if_missing:
            return {}
        topic_schedule = word_schedule[word] = {}
        return topic_schedule

    def reset_schedule(self) -> None:
        self._data["word_schedule"] = {}

    @classmethod
    def _is_valid_schedule_entry(cls, schedule_entry: object) -> bool:
        try:
            cls._SCHEDULE_ENTRY_ADAPTER.validate_python(schedule_entry, strict=True)
        except ValidationError:
            return False
        return True

    @overload
    def get_schedule_entry(
        self,
        word: str,
        topic: str,
        *,
        create_if_missing: Literal[True],
    ) -> ScheduleEntry: ...
    @overload
    def get_schedule_entry(
        self,
        word: str,
        topic: str,
        *,
        create_if_missing: Literal[False] = False,
    ) -> ScheduleEntry | None: ...
    def get_schedule_entry(
        self,
        word: str,
        topic: str,
        *,
        create_if_missing: bool = False,
    ) -> ScheduleEntry | None:
        default = ScheduleEntry(interval_days=0, due_date=date.min.isoformat())
        topic_schedule = self.get_topic_schedule(
            word,
            create_if_missing=create_if_missing,
        )
        schedule_entry = topic_schedule.get(topic)
        if create_if_missing:
            if not self._is_valid_schedule_entry(schedule_entry):
                schedule_entry = topic_schedule[topic] = default
            return schedule_entry
        return schedule_entry if self._is_valid_schedule_entry(schedule_entry) else None
