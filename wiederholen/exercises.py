import random
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from enum import Enum
from functools import cached_property
from pathlib import Path
from typing import Annotated, Final, Literal, Self, TypedDict, overload

import yaml
from pydantic import AfterValidator, TypeAdapter, ValidationError

from wiederholen.i18n import Language, LANGUAGES

type Topic = str


def _parse_iso_date(value: str) -> str:
    date.fromisoformat(value)
    return value


class _ScheduleEntry(TypedDict):
    interval_days: int
    due_date: Annotated[str, AfterValidator(_parse_iso_date)]


@dataclass(frozen=True)
class Recall:
    question: str
    answer: list[str]
    hint: dict[Language, str] | None = None

    def __post_init__(self) -> None:
        if len(self.answer) == 0:
            raise ValueError("recall.answer must not be empty")
        if self.hint is not None and not set(self.hint.keys()).issubset(LANGUAGES):
            raise ValueError(
                f"recall.hint keys must be a subset of {LANGUAGES}, got {set(self.hint.keys())}"
            )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Self:
        return cls(**d)


@dataclass(frozen=True)
class Exercise:
    word: str
    topic: Topic
    question: str
    answer: str
    distractors: list[str]
    explanation: dict[Language, str]
    recalls: list[Recall] = field(default_factory=list)
    description: dict[Language, str] | None = None

    def __post_init__(self) -> None:
        if self.answer in self.distractors:
            raise ValueError(f"answer '{self.answer}' must not be in distractors")
        if set(self.explanation.keys()) != LANGUAGES:
            raise ValueError(
                f"explanation must have keys {LANGUAGES}, got {set(self.explanation.keys())}"
            )
        if self.description is not None and set(self.description.keys()) != LANGUAGES:
            raise ValueError(
                f"description must have keys {LANGUAGES}, got {set(self.description.keys())}"
            )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Self:
        d = dict(d)
        if d.get("recalls") is not None:
            d["recalls"] = [Recall.from_dict(r) for r in d["recalls"]]
        return cls(**d)


class RecallMode(Enum):
    none = "none"
    optional = "optional"
    required = "required"


@dataclass(frozen=True)
class Mark:
    correct: bool
    recall: RecallMode

    def to_dict(self) -> dict:
        return {"correct": self.correct, "recall": self.recall.value}

    @classmethod
    def from_dict(cls, d: dict) -> Self:
        return cls(correct=d["correct"], recall=RecallMode(d["recall"]))


@dataclass(frozen=True)
class Progress:
    total: int
    new: int
    learning: int
    mastered: int
    due: int


@dataclass(frozen=True)
class Course:
    exercises: Sequence[Exercise]
    chained_topics: Mapping[str, Sequence[str]] = field(default_factory=dict)
    gated_topics: frozenset[str] = field(default_factory=frozenset)

    @staticmethod
    def _load_exercises(path: Path) -> list[Exercise]:
        with open(path) as f:
            items = yaml.safe_load(f)
        return [Exercise.from_dict(item) for item in items]

    @staticmethod
    def _load_topics(path: Path) -> tuple[dict[str, list[str]], frozenset[str]]:
        if not path.exists():
            return {}, frozenset()
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        chained_topics: dict[str, list[str]] = {}
        gated_topics: set[str] = set()
        for source, relations in data.items():
            chains = relations.get("chains", [])
            gates = relations.get("gates", [])
            chained_topics[source] = list(dict.fromkeys([*chains, *gates]))
            gated_topics.update(gates)
        return chained_topics, frozenset(gated_topics)

    @classmethod
    def load(cls, path: Path) -> Self:
        chained_topics, gated_topics = cls._load_topics(path / "topics.yaml")
        return cls(
            cls._load_exercises(path / "exercises.yaml"), chained_topics, gated_topics
        )


class Journal:
    def __init__(self, data: dict) -> None:
        self._data = data

    @property
    def last_answered_question(self) -> str | None:
        return self._data.get("last_answered_question")

    @last_answered_question.setter
    def last_answered_question(self, question: str) -> None:
        self._data["last_answered_question"] = question

    @property
    def last_recall_question(self) -> str | None:
        return self._data.get("last_recall_question")

    @last_recall_question.setter
    def last_recall_question(self, question: str) -> None:
        self._data["last_recall_question"] = question

    @property
    def last_mark(self) -> Mark | None:
        raw = self._data.get("last_mark")
        return Mark.from_dict(raw) if raw is not None else None

    @last_mark.setter
    def last_mark(self, value: Mark) -> None:
        self._data["last_mark"] = value.to_dict()

    @property
    def recall_requested(self) -> bool:
        return self._data.get("recall_requested", False)

    @recall_requested.setter
    def recall_requested(self, value: bool) -> None:
        self._data["recall_requested"] = value

    @property
    def last_answered_at(self) -> datetime | None:
        if (raw := self._data.get("last_answered_at")) is None:
            return None
        return datetime.fromisoformat(raw)

    @last_answered_at.setter
    def last_answered_at(self, value: datetime) -> None:
        self._data["last_answered_at"] = value.isoformat()

    @property
    def last_reminded_at(self) -> datetime | None:
        raw = self._data.get("last_reminded_at")
        if raw is None:
            return None
        return datetime.fromisoformat(raw)

    @last_reminded_at.setter
    def last_reminded_at(self, value: datetime) -> None:
        self._data["last_reminded_at"] = value.isoformat()

    def get_word_schedule(self, *, create_if_missing: bool = False) -> dict:
        if create_if_missing:
            return self._data.setdefault("word_schedule", {})
        return self._data.get("word_schedule", {})


class Tutor:
    MAX_INTERVAL_DAYS: Final = 60
    REMIND_AFTER: Final = timedelta(hours=24)
    _SCHEDULE_ENTRY_ADAPTER: Final = TypeAdapter(_ScheduleEntry)

    def __init__(self, course: Course, journal: dict) -> None:
        self._exercises = course.exercises
        self._journal = Journal(journal)
        self._chained_topics = course.chained_topics
        self._gated_topics = course.gated_topics

    @classmethod
    def _is_valid_schedule_entry(cls, schedule_entry: object) -> bool:
        try:
            cls._SCHEDULE_ENTRY_ADAPTER.validate_python(schedule_entry, strict=True)
        except ValidationError:
            return False
        return True

    @staticmethod
    def _schedule_key(exercise: Exercise) -> str:
        return f"{exercise.word}:{exercise.topic}"

    @overload
    def _get_schedule_entry(
        self,
        key: str,
        *,
        create_if_missing: Literal[True],
    ) -> _ScheduleEntry: ...
    @overload
    def _get_schedule_entry(
        self,
        key: str,
        *,
        create_if_missing: Literal[False] = False,
    ) -> _ScheduleEntry | None: ...
    def _get_schedule_entry(
        self,
        key: str,
        *,
        create_if_missing: bool = False,
    ) -> _ScheduleEntry | None:
        default = _ScheduleEntry(interval_days=0, due_date=date.min.isoformat())
        if create_if_missing:
            word_schedule = self._journal.get_word_schedule(create_if_missing=True)
            schedule_entry = word_schedule.get(key)
            if not self._is_valid_schedule_entry(schedule_entry):
                schedule_entry = word_schedule[key] = default
            return schedule_entry
        word_schedule = self._journal.get_word_schedule()
        schedule_entry = word_schedule.get(key)
        return schedule_entry if self._is_valid_schedule_entry(schedule_entry) else None

    def _due_date(self, key: str) -> date:
        entry = self._get_schedule_entry(key)
        if entry is None:
            exercise = self._exercises_by_schedule_key[key][0]
            if exercise.topic in self._gated_topics:
                return date.max
            return date.min
        return date.fromisoformat(entry["due_date"])

    @cached_property
    def _exercises_by_schedule_key(self) -> dict[str, list[Exercise]]:
        by_key: dict[str, list[Exercise]] = {}
        for exercise in self._exercises:
            by_key.setdefault(self._schedule_key(exercise), []).append(exercise)
        return by_key

    def next_exercise(self) -> Exercise:
        today = date.today()
        due_schedule_keys = [
            schedule_key
            for schedule_key in self._exercises_by_schedule_key
            if self._due_date(schedule_key) <= today
        ]
        if due_schedule_keys:
            schedule_key = random.choice(due_schedule_keys)
        else:
            earliest_due_date = min(
                self._due_date(schedule_key)
                for schedule_key in self._exercises_by_schedule_key
            )
            earliest_schedule_keys = [
                schedule_key
                for schedule_key in self._exercises_by_schedule_key
                if self._due_date(schedule_key) == earliest_due_date
            ]
            schedule_key = random.choice(earliest_schedule_keys)
        candidates = self._exercises_by_schedule_key[schedule_key]
        if self._journal.last_answered_question is not None:
            if filtered_exercises := [
                exercise
                for exercise in candidates
                if exercise.question != self._journal.last_answered_question
            ]:
                candidates = filtered_exercises
        return random.choice(candidates)

    def due_topics_count(self) -> int:
        today = date.today()
        return sum(
            1
            for schedule_key in self._exercises_by_schedule_key
            if self._due_date(schedule_key) <= today
        )

    def progress(self) -> Progress:
        new = 0
        learning = 0
        mastered = 0
        for schedule_key in self._exercises_by_schedule_key:
            entry = self._get_schedule_entry(schedule_key)
            if entry is None:
                new += 1
            elif entry["interval_days"] >= self.MAX_INTERVAL_DAYS:
                mastered += 1
            else:
                learning += 1
        return Progress(
            total=len(self._exercises_by_schedule_key),
            new=new,
            learning=learning,
            mastered=mastered,
            due=self.due_topics_count(),
        )

    def _expedite_chained_topics(self, exercise: Exercise) -> None:
        today = date.today()
        for dependent_topic in self._chained_topics.get(exercise.topic, []):
            dependent_key = f"{exercise.word}:{dependent_topic}"
            if dependent_key not in self._exercises_by_schedule_key:
                continue
            dependent_entry = self._get_schedule_entry(dependent_key)
            if dependent_entry is None:
                word_schedule = self._journal.get_word_schedule(create_if_missing=True)
                word_schedule[dependent_key] = _ScheduleEntry(
                    interval_days=0, due_date=today.isoformat()
                )
            elif date.fromisoformat(dependent_entry["due_date"]) > today:
                dependent_entry["due_date"] = today.isoformat()

    def check_answer(self, exercise: Exercise, answer: str) -> Mark:
        correct = answer.strip().lower() == exercise.answer.strip().lower()
        self._journal.last_answered_question = exercise.question
        self._journal.last_answered_at = datetime.now(UTC)
        self._journal.recall_requested = False
        schedule_entry = self._get_schedule_entry(
            self._schedule_key(exercise),
            create_if_missing=True,
        )
        if correct:
            interval = min(
                max(schedule_entry["interval_days"] * 2, 1), self.MAX_INTERVAL_DAYS
            )
            due_date = date.today() + timedelta(days=interval)
        else:
            interval = 1
            due_date = date.today()
        schedule_entry["interval_days"] = interval
        schedule_entry["due_date"] = due_date.isoformat()
        self._expedite_chained_topics(exercise)
        if not exercise.recalls:
            recall_mode = RecallMode.none
        elif correct:
            recall_mode = RecallMode.optional
        else:
            recall_mode = RecallMode.required
        mark = Mark(correct=correct, recall=recall_mode)
        self._journal.last_mark = mark
        return mark

    def check_recall(self, recall: Recall, text: str) -> bool:
        def normalize(s: str) -> str:
            return " ".join(s.lower().strip(".,!?").split())

        normalized = normalize(text)
        return any(normalize(a) == normalized for a in recall.answer)

    def request_recall(self, exercise: Exercise) -> Recall:
        last_mark = self._journal.last_mark
        is_optional_recall = (
            last_mark is not None and last_mark.recall == RecallMode.optional
        )
        if is_optional_recall and not self._journal.recall_requested:
            schedule_entry = self._get_schedule_entry(
                self._schedule_key(exercise), create_if_missing=True
            )
            interval = max(schedule_entry["interval_days"] // 2, 1)
            schedule_entry["interval_days"] = interval
            schedule_entry["due_date"] = (
                date.today() + timedelta(days=interval)
            ).isoformat()
            self._journal.recall_requested = True
        candidates = exercise.recalls
        if self._journal.last_recall_question is not None:
            if filtered := [
                recall
                for recall in candidates
                if recall.question != self._journal.last_recall_question
            ]:
                candidates = filtered
        recall = random.choice(candidates)
        self._journal.last_recall_question = recall.question
        return recall

    def should_remind(self) -> bool:
        if self.due_topics_count() <= 0:
            return False
        if self._journal.last_answered_at is None:
            return False
        if datetime.now(UTC) - self._journal.last_answered_at < self.REMIND_AFTER:
            return False
        if (
            self._journal.last_reminded_at is not None
            and self._journal.last_reminded_at >= self._journal.last_answered_at
        ):
            return False
        return True

    def record_reminder_sent(self) -> None:
        self._journal.last_reminded_at = datetime.now(UTC)
