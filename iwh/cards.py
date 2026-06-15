from dataclasses import dataclass
from pathlib import Path
from typing import get_args

import yaml

from iwh.locales import Language


@dataclass(frozen=True)
class Card:
    question: str
    distractors: list[str]
    answer: str
    explanation: dict[Language, str]

    def __post_init__(self) -> None:
        if self.answer in self.distractors:
            raise ValueError(f"answer '{self.answer}' must not be in distractors")
        valid = set(get_args(Language.__value__))
        if set(self.explanation.keys()) != valid:
            raise ValueError(
                f"explanation must have keys {valid}, got {set(self.explanation.keys())}"
            )


def load_cards(path: Path) -> list[Card]:
    with open(path) as f:
        items = yaml.safe_load(f)
    return [Card(**item) for item in items]
