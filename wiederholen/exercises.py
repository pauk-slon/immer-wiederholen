import random
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import yaml

from wiederholen.i18n import Language, LANGUAGES


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


class RecallMode(Enum):
    none = "none"
    optional = "optional"
    required = "required"


@dataclass(frozen=True)
class Mark:
    correct: bool
    recall: RecallMode


def _exercise_from_dict(d: dict) -> Exercise:
    if d.get("recall") is not None:
        d = {**d, "recall": Recall(**d["recall"])}
    return Exercise(**d)


def load_exercises(path: Path) -> list[Exercise]:
    with open(path) as f:
        items = yaml.safe_load(f)
    return [_exercise_from_dict(item) for item in items]


class Teacher:
    WEIGHT_ON_WRONG: float = 2.0
    WEIGHT_ON_CORRECT: float = 0.5
    WEIGHT_MIN: float = 1.0

    def __init__(self, exercises: Sequence[Exercise], journal: dict) -> None:
        self._exercises = exercises
        self._journal = journal

    def ask(self) -> Exercise:
        topic_weights: dict[str, float] = self._journal.get("topic_weights", {})
        weights = [
            topic_weights.get(exercise.topic, self.WEIGHT_MIN)
            for exercise in self._exercises
        ]
        return random.choices(self._exercises, weights=weights, k=1)[0]

    def check_answer(self, exercise: Exercise, answer: str) -> Mark:
        correct = answer == exercise.answer
        topic_weights: dict[str, float] = self._journal.get("topic_weights", {})
        current = topic_weights.get(exercise.topic, self.WEIGHT_MIN)
        if correct:
            topic_weights[exercise.topic] = max(
                self.WEIGHT_MIN, current * self.WEIGHT_ON_CORRECT
            )
        else:
            topic_weights[exercise.topic] = current * self.WEIGHT_ON_WRONG
        self._journal["topic_weights"] = topic_weights
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
