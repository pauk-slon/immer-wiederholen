import random
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

from wiederholen.i18n import Language, LANGUAGES


@dataclass(frozen=True)
class Exercise:
    question: str
    topic: str
    distractors: list[str]
    answer: str
    explanation: dict[Language, str]
    recall: str | None = None
    recall_answer: list[str] | None = None
    recall_hint: dict[Language, str] | None = None

    def __post_init__(self) -> None:
        if self.answer in self.distractors:
            raise ValueError(f"answer '{self.answer}' must not be in distractors")
        if set(self.explanation.keys()) != LANGUAGES:
            raise ValueError(
                f"explanation must have keys {LANGUAGES}, got {set(self.explanation.keys())}"
            )
        if (self.recall is None) != (self.recall_answer is None):
            raise ValueError(
                "recall and recall_answer must both be set or both be None"
            )
        if self.recall_answer is not None and len(self.recall_answer) == 0:
            raise ValueError("recall_answer must not be empty")
        if self.recall_hint is not None and not set(self.recall_hint.keys()).issubset(
            LANGUAGES
        ):
            raise ValueError(
                f"recall_hint keys must be a subset of {LANGUAGES}, got {set(self.recall_hint.keys())}"
            )


@dataclass(frozen=True)
class Mark:
    correct: bool
    show_recall: bool


def load_exercises(path: Path) -> list[Exercise]:
    with open(path) as f:
        items = yaml.safe_load(f)
    return [Exercise(**item) for item in items]


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
        return Mark(correct=correct, show_recall=not correct and exercise.recall is not None)

    def check_recall(self, exercise: Exercise, text: str) -> bool:
        if exercise.recall_answer is None:
            return False

        def normalize(s: str) -> str:
            return " ".join(s.lower().strip(".,!?").split())

        normalized = normalize(text)
        return any(normalize(a) == normalized for a in exercise.recall_answer)


class School:
    def __init__(self, exercises: Sequence[Exercise]) -> None:
        self._exercises = exercises

    def __call__(self, journal: dict) -> Teacher:
        return Teacher(self._exercises, journal)
