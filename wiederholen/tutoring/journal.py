from collections.abc import Iterator
from datetime import UTC, date, datetime
from typing import Annotated, Final, NotRequired, TypedDict, TypeIs

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
    # NotRequired so a last_exercise recorded before this field existed stays
    # valid rather than being treated as malformed — next_exercise()'s
    # same-pair exclusion just no-ops until the next answer refreshes it.
    word: NotRequired[str]
    topic: NotRequired[str]


class ExtraNewWords(TypedDict):
    date: str
    count: int


class AnswerStats(TypedDict):
    date: str
    answered: int
    correct: int


class Journal:
    _SCHEDULE_ENTRY_ADAPTER: Final = TypeAdapter(ScheduleEntry)
    _WORD_SCHEDULE_KEY: Final = "word_schedule"

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
        correct: bool,
        was_recall_optional: bool,
    ) -> tuple[bool, int]:
        self._data["last_exercise"] = LastExercise(
            question=question,
            word=word,
            topic=topic,
            answered_at=datetime.now(UTC).isoformat(),
            is_recall_optional=was_recall_optional,
        )
        answered, right = self.get_answer_stats_today()
        self._data["today_answers"] = AnswerStats(
            date=self._today.isoformat(),
            answered=answered + 1,
            correct=right + (1 if correct else 0),
        )
        schedule_entry = self._get_or_create_schedule_entry(word, topic)
        is_new = schedule_entry.get("introduced_at") is None
        if is_new:
            schedule_entry["introduced_at"] = self._today.isoformat()
        return is_new, schedule_entry["interval_days"]

    @property
    def last_reminded_at(self) -> datetime | None:
        if (raw_value := self._data.get("last_reminded_at")) is not None:
            return datetime.fromisoformat(raw_value)

    @last_reminded_at.setter
    def last_reminded_at(self, value: datetime) -> None:
        self._data["last_reminded_at"] = value.isoformat()

    def get_extra_new_words_today(self) -> int:
        extra = self._data.get("extra_new_words")
        if extra is None or extra["date"] != self._today.isoformat():
            # A grant from a previous day is simply treated as zero rather
            # than needing explicit cleanup — same self-expiring pattern as
            # introduced_at.
            return 0
        return extra["count"]

    def add_extra_new_words_today(self, amount: int) -> int:
        new_count = self.get_extra_new_words_today() + amount
        self._data["extra_new_words"] = ExtraNewWords(
            date=self._today.isoformat(),
            count=new_count,
        )
        return new_count

    def get_answer_stats_today(self) -> tuple[int, int]:
        stats = self._data.get("today_answers")
        if stats is None or stats["date"] != self._today.isoformat():
            return 0, 0
        return stats["answered"], stats["correct"]

    def get_word_schedule(self, *, create_if_missing: bool = False) -> dict:
        if create_if_missing:
            return self._data.setdefault(self._WORD_SCHEDULE_KEY, {})
        return self._data.get(self._WORD_SCHEDULE_KEY, {})

    def get_topic_schedule(self, word: str, *, create_if_missing: bool = False) -> dict:
        word_schedule = self.get_word_schedule(create_if_missing=create_if_missing)
        topic_schedule = word_schedule.get(word)
        if isinstance(topic_schedule, dict):
            return topic_schedule
        if not create_if_missing:
            return {}
        topic_schedule = word_schedule[word] = {}
        return topic_schedule

    @classmethod
    def reset_schedule(cls, data: dict) -> None:
        data[cls._WORD_SCHEDULE_KEY] = {}

    @classmethod
    def _is_valid_schedule_entry(cls, schedule_entry: object) -> TypeIs[ScheduleEntry]:
        try:
            cls._SCHEDULE_ENTRY_ADAPTER.validate_python(schedule_entry, strict=True)
        except ValidationError:
            return False
        return True

    def get_schedule_entry(self, word: str, topic: str) -> ScheduleEntry | None:
        topic_schedule = self.get_topic_schedule(word)
        schedule_entry = topic_schedule.get(topic)
        return schedule_entry if self._is_valid_schedule_entry(schedule_entry) else None

    def _get_or_create_schedule_entry(self, word: str, topic: str) -> ScheduleEntry:
        topic_schedule = self.get_topic_schedule(word, create_if_missing=True)
        schedule_entry = topic_schedule.get(topic)
        if not self._is_valid_schedule_entry(schedule_entry):
            schedule_entry = topic_schedule[topic] = ScheduleEntry(
                interval_days=0, due_date=date.min.isoformat()
            )
        return schedule_entry

    def schedule_pair(
        self, word: str, topic: str, *, due_date: date, interval_days: int
    ) -> None:
        schedule_entry = self._get_or_create_schedule_entry(word, topic)
        schedule_entry["interval_days"] = interval_days
        schedule_entry["due_date"] = due_date.isoformat()

    def is_pair_introduced(self, word: str, topic: str) -> bool:
        entry = self.get_schedule_entry(word, topic)
        return entry is not None and entry.get("introduced_at") is not None

    def due_pairs(self, *, introduced: bool = True) -> Iterator[tuple[str, str]]:
        # Pairs with a real entry, due today, split by whether they've been
        # introduced — introduced=True (the default) is exactly the set
        # _due_review_pairs() needs. Iterates the (typically much smaller)
        # word_schedule instead of every (word, topic) the course defines,
        # since a real entry is required either way — the caller still has
        # to filter this against its own known (word, topic) pairs, since
        # word_schedule can outlive a course change (a word/topic removed
        # from topics.yaml stays in a learner's journal).
        for word, topic_schedule in self.get_word_schedule().items():
            for topic in topic_schedule:
                entry = self.get_schedule_entry(word, topic)
                if (
                    entry is not None
                    and (entry.get("introduced_at") is not None) == introduced
                    and date.fromisoformat(entry["due_date"]) <= self._today
                ):
                    yield word, topic
