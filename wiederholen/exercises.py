import random
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from pathlib import Path
from typing import Literal, TypedDict, overload

import yaml

from wiederholen.i18n import Language, LANGUAGES


class _ScheduleEntry(TypedDict):
    interval_days: int
    due_date: str


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


@dataclass(frozen=True)
class Exercise:
    topic: str
    question: str
    answer: str
    distractors: list[str]
    explanation: dict[Language, str]
    recall: Recall | None = None

    def __post_init__(self) -> None:
        if self.answer in self.distractors:
            raise ValueError(f"answer '{self.answer}' must not be in distractors")
        if set(self.explanation.keys()) != LANGUAGES:
            raise ValueError(
                f"explanation must have keys {LANGUAGES}, got {set(self.explanation.keys())}"
            )

    @classmethod
    def from_dict(cls, d: dict) -> "Exercise":
        d = dict(d)
        if d.get("recall") is not None:
            d["recall"] = Recall(**d["recall"])
        return cls(**d)


class RecallMode(Enum):
    none = "none"
    optional = "optional"
    required = "required"


@dataclass(frozen=True)
class Mark:
    correct: bool
    recall: RecallMode


def load_exercises(path: Path) -> list[Exercise]:
    with open(path) as f:
        items = yaml.safe_load(f)
    return [Exercise.from_dict(item) for item in items]


class Teacher:
    MAX_INTERVAL_DAYS: int = 60

    def __init__(self, exercises: Sequence[Exercise], journal: dict) -> None:
        self._exercises = exercises
        self._journal = journal

    @overload
    def _get_schedule_entry(
        self, topic: str, *, create_if_missing: Literal[True]
    ) -> _ScheduleEntry: ...
    @overload
    def _get_schedule_entry(
        self, topic: str, *, create_if_missing: Literal[False] = False
    ) -> _ScheduleEntry | None: ...
    # TODO: once the journal is backed by persistent storage, validate entries
    # read here against _ScheduleEntry's shape (schema may have changed since
    # they were written) instead of trusting them as-is.
    def _get_schedule_entry(
        self,
        topic: str,
        *,
        create_if_missing: bool = False,
    ) -> _ScheduleEntry | None:
        if create_if_missing:
            default = _ScheduleEntry(interval_days=0, due_date=date.min.isoformat())
            topic_schedule = self._journal.setdefault("topic_schedule", {})
            return topic_schedule.setdefault(topic, default)
        topic_schedule = self._journal.get("topic_schedule", {})
        return topic_schedule.get(topic)

    def _due_date(self, topic: str) -> date:
        entry = self._get_schedule_entry(topic)
        if entry is None:
            return date.min
        return date.fromisoformat(entry["due_date"])

    def next_exercise(self, today: date | None = None) -> Exercise:
        today = today or date.today()
        due = [ex for ex in self._exercises if self._due_date(ex.topic) <= today]
        if due:
            return random.choice(due)
        return min(self._exercises, key=lambda ex: self._due_date(ex.topic))

    def check_answer(
        self, exercise: Exercise, answer: str, today: date | None = None
    ) -> Mark:
        today = today or date.today()
        correct = answer.strip().lower() == exercise.answer.strip().lower()
        entry = self._get_schedule_entry(exercise.topic, create_if_missing=True)
        if correct:
            interval = min(max(entry["interval_days"] * 2, 1), self.MAX_INTERVAL_DAYS)
            due_date = today + timedelta(days=interval)
        else:
            interval = 1
            due_date = today
        entry["interval_days"] = interval
        entry["due_date"] = due_date.isoformat()
        if exercise.recall is None:
            recall_mode = RecallMode.none
        elif correct:
            recall_mode = RecallMode.optional
        else:
            recall_mode = RecallMode.required
        return Mark(correct=correct, recall=recall_mode)

    def check_recall(self, exercise: Exercise, text: str) -> bool:
        assert exercise.recall is not None

        def normalize(s: str) -> str:
            return " ".join(s.lower().strip(".,!?").split())

        normalized = normalize(text)
        return any(normalize(a) == normalized for a in exercise.recall.answer)


class School:
    def __init__(self, exercises: Sequence[Exercise]) -> None:
        self._exercises = exercises

    def __call__(self, journal: dict) -> Teacher:
        return Teacher(self._exercises, journal)
