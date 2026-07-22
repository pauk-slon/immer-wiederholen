import random
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from enum import Enum
from functools import cached_property
from pathlib import Path
from typing import Annotated, ClassVar, Literal, TypedDict, overload

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
    def from_dict(cls, d: dict) -> "Recall":
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
    def from_dict(cls, d: dict) -> "Exercise":
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


@dataclass(frozen=True)
class Progress:
    total: int
    new: int
    learning: int
    mastered: int
    due: int


def _load_exercises(path: Path) -> list[Exercise]:
    with open(path) as f:
        items = yaml.safe_load(f)
    return [Exercise.from_dict(item) for item in items]


def _load_chained_topics(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    with open(path) as f:
        data = yaml.safe_load(f)
    return data or {}


@dataclass(frozen=True)
class Course:
    exercises: Sequence[Exercise]
    chained_topics: Mapping[str, Sequence[str]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "Course":
        return cls(
            _load_exercises(path / "exercises.yaml"),
            _load_chained_topics(path / "chained_categories.yaml"),
        )


class Tutor:
    MAX_INTERVAL_DAYS: int = 60
    REMIND_AFTER: timedelta = timedelta(hours=24)
    _SCHEDULE_ENTRY_ADAPTER: ClassVar = TypeAdapter(_ScheduleEntry)

    def __init__(self, course: Course, journal: dict) -> None:
        self._exercises = course.exercises
        self._journal = journal
        self._chained_topics = course.chained_topics

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
            word_schedule = self._journal.setdefault("word_schedule", {})
            schedule_entry = word_schedule.get(key)
            if not self._is_valid_schedule_entry(schedule_entry):
                schedule_entry = word_schedule[key] = default
            return schedule_entry
        word_schedule = self._journal.get("word_schedule", {})
        schedule_entry = word_schedule.get(key)
        return schedule_entry if self._is_valid_schedule_entry(schedule_entry) else None

    def _due_date(self, key: str) -> date:
        entry = self._get_schedule_entry(key)
        if entry is None:
            exercise = self._exercises_by_schedule_key[key][0]
            if exercise.topic in self._chained_dependent_topics:
                return date.max
            return date.min
        return date.fromisoformat(entry["due_date"])

    @property
    def _last_answered_question(self) -> str | None:
        return self._journal.get("last_answered_question")

    @_last_answered_question.setter
    def _last_answered_question(self, question: str) -> None:
        self._journal["last_answered_question"] = question

    @property
    def _last_recall_question(self) -> str | None:
        return self._journal.get("last_recall_question")

    @_last_recall_question.setter
    def _last_recall_question(self, question: str) -> None:
        self._journal["last_recall_question"] = question

    @property
    def _last_answered_at(self) -> datetime | None:
        raw = self._journal.get("last_answered_at")
        if raw is None:
            return None
        return datetime.fromisoformat(raw)

    @_last_answered_at.setter
    def _last_answered_at(self, value: datetime) -> None:
        self._journal["last_answered_at"] = value.isoformat()

    @property
    def _last_reminded_at(self) -> datetime | None:
        raw = self._journal.get("last_reminded_at")
        if raw is None:
            return None
        return datetime.fromisoformat(raw)

    @_last_reminded_at.setter
    def _last_reminded_at(self, value: datetime) -> None:
        self._journal["last_reminded_at"] = value.isoformat()

    @cached_property
    def _exercises_by_schedule_key(self) -> dict[str, list[Exercise]]:
        by_key: dict[str, list[Exercise]] = {}
        for exercise in self._exercises:
            by_key.setdefault(self._schedule_key(exercise), []).append(exercise)
        return by_key

    @cached_property
    def _chained_dependent_topics(self) -> set[str]:
        return {
            dependent_topic
            for dependent_topics in self._chained_topics.values()
            for dependent_topic in dependent_topics
        }

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
        last_answered_question = self._last_answered_question
        if last_answered_question is not None:
            if filtered_exercises := [
                exercise
                for exercise in candidates
                if exercise.question != last_answered_question
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
                word_schedule = self._journal.setdefault("word_schedule", {})
                word_schedule[dependent_key] = _ScheduleEntry(
                    interval_days=0, due_date=today.isoformat()
                )
            elif date.fromisoformat(dependent_entry["due_date"]) > today:
                dependent_entry["due_date"] = today.isoformat()

    def check_answer(self, exercise: Exercise, answer: str) -> Mark:
        correct = answer.strip().lower() == exercise.answer.strip().lower()
        self._last_answered_question = exercise.question
        self._last_answered_at = datetime.now(UTC)
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
        return Mark(correct=correct, recall=recall_mode)

    def check_recall(self, recall: Recall, text: str) -> bool:
        def normalize(s: str) -> str:
            return " ".join(s.lower().strip(".,!?").split())

        normalized = normalize(text)
        return any(normalize(a) == normalized for a in recall.answer)

    def pick_recall(self, exercise: Exercise) -> Recall:
        candidates = exercise.recalls
        last_recall_question = self._last_recall_question
        if last_recall_question is not None:
            if filtered := [
                recall
                for recall in candidates
                if recall.question != last_recall_question
            ]:
                candidates = filtered
        recall = random.choice(candidates)
        self._last_recall_question = recall.question
        return recall

    def should_remind(self) -> bool:
        if self.due_topics_count() <= 0:
            return False
        last_answered_at = self._last_answered_at
        if last_answered_at is None:
            return False
        if datetime.now(UTC) - last_answered_at < self.REMIND_AFTER:
            return False
        last_reminded_at = self._last_reminded_at
        if last_reminded_at is not None and last_reminded_at >= last_answered_at:
            return False
        return True

    def record_reminder_sent(self) -> None:
        self._last_reminded_at = datetime.now(UTC)
