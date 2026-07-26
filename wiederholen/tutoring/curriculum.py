from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Self

import yaml

from wiederholen.i18n import LANGUAGES, Language

type Topic = str


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
        return cls(
            cls._load_exercises(path / "exercises.yaml"),
            *cls._load_topics(path / "topics.yaml"),
        )
