import random
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import yaml

from wiederholen.i18n import Language, LANGUAGES


@dataclass(frozen=True)
class Card:
    question: str
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


type CardPicker = Callable[[], Card]


def make_card_picker(cards: list[Card]) -> CardPicker:
    return lambda: random.choice(cards)
