import random
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

from wiederholen.i18n import Language, LANGUAGES


@dataclass(frozen=True)
class Card:
    question: str
    topic: str
    distractors: list[str]
    answer: str
    explanation: dict[Language, str]

    def __post_init__(self) -> None:
        if self.answer in self.distractors:
            raise ValueError(f"answer '{self.answer}' must not be in distractors")
        if set(self.explanation.keys()) != LANGUAGES:
            raise ValueError(
                f"explanation must have keys {LANGUAGES}, got {set(self.explanation.keys())}"
            )


def load_cards(path: Path) -> list[Card]:
    with open(path) as f:
        items = yaml.safe_load(f)
    return [Card(**item) for item in items]


class Teacher:
    WEIGHT_ON_WRONG: float = 2.0
    WEIGHT_ON_CORRECT: float = 0.5
    WEIGHT_MIN: float = 1.0

    def __init__(self, cards: Sequence[Card], state: dict) -> None:
        self._cards = cards
        self._state = state

    def ask(self) -> Card:
        topic_weights: dict[str, float] = self._state.get("topic_weights", {})
        weights = [
            topic_weights.get(card.topic, self.WEIGHT_MIN) for card in self._cards
        ]
        return random.choices(self._cards, weights=weights, k=1)[0]

    def check(self, card: Card, answer: str) -> bool:
        correct = answer == card.answer
        topic_weights: dict[str, float] = self._state.get("topic_weights", {})
        current = topic_weights.get(card.topic, self.WEIGHT_MIN)
        if correct:
            topic_weights[card.topic] = max(
                self.WEIGHT_MIN, current * self.WEIGHT_ON_CORRECT
            )
        else:
            topic_weights[card.topic] = current * self.WEIGHT_ON_WRONG
        self._state["topic_weights"] = topic_weights
        return correct


class School:
    def __init__(self, cards: Sequence[Card]) -> None:
        self._cards = cards

    def __call__(self, state: dict) -> Teacher:
        return Teacher(self._cards, state)
