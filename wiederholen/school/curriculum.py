from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Self, TypedDict

import yaml

from wiederholen.school.i18n import LANGUAGES, Language

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


class _TopicsConfig(TypedDict):
    word_chained_topics: dict[str, list[str]]
    answer_chained_topics: dict[str, list[str]]
    gated_topics: frozenset[str]
    topic_instructions: dict[str, dict[Language, str]]
    ai_generatable_topics: frozenset[str]


@dataclass(frozen=True)
class Course:
    exercises: Sequence[Exercise]
    word_chained_topics: Mapping[str, Sequence[str]] = field(
        default_factory=dict,
        kw_only=True,
    )
    answer_chained_topics: Mapping[str, Sequence[str]] = field(
        default_factory=dict,
        kw_only=True,
    )
    gated_topics: frozenset[str] = field(default_factory=frozenset, kw_only=True)
    topic_instructions: Mapping[str, Mapping[Language, str]] = field(
        default_factory=dict,
        kw_only=True,
    )
    ai_generatable_topics: frozenset[str] = field(
        default_factory=frozenset, kw_only=True
    )

    @staticmethod
    def _load_exercises(path: Path) -> list[Exercise]:
        with open(path) as f:
            items = yaml.safe_load(f)
        return [Exercise.from_dict(item) for item in items]

    @staticmethod
    def _load_topics(path: Path) -> _TopicsConfig:
        if not path.exists():
            return _TopicsConfig(
                word_chained_topics={},
                answer_chained_topics={},
                gated_topics=frozenset(),
                topic_instructions={},
                ai_generatable_topics=frozenset(),
            )
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        word_chained_topics: dict[str, list[str]] = {}
        gated_topics: set[str] = set()
        answer_chained_topics: dict[str, list[str]] = {}
        topic_instructions: dict[str, dict[Language, str]] = {}
        ai_generatable_topics: set[str] = set()
        for source, relations in data.items():
            chains = relations.get("chains", [])
            gates = relations.get("gates", [])
            word_chained_topics[source] = list(dict.fromkeys([*chains, *gates]))
            gated_topics.update(gates)
            if chains_by_answer := relations.get("chains_by_answer", []):
                answer_chained_topics[source] = list(dict.fromkeys(chains_by_answer))
            if instruction := relations.get("instruction"):
                topic_instructions[source] = instruction
            if relations.get("ai_generation"):
                ai_generatable_topics.add(source)
        return _TopicsConfig(
            word_chained_topics=word_chained_topics,
            answer_chained_topics=answer_chained_topics,
            gated_topics=frozenset(gated_topics),
            topic_instructions=topic_instructions,
            ai_generatable_topics=frozenset(ai_generatable_topics),
        )

    @classmethod
    def load(cls, path: Path) -> Self:
        return cls(
            cls._load_exercises(path / "exercises.yaml"),
            **cls._load_topics(path / "topics.yaml"),
        )

    def restricted_to(self, topics: Iterable[Topic]) -> Self:
        # A narrower view of this course, e.g. for a web widget embedded on
        # a page about specific grammar topics — same student_record works
        # against either view, since schedule entries are keyed by
        # (word, topic), not by which Course object selected them.
        #
        # word_chained_topics/answer_chained_topics/gated_topics/
        # topic_instructions/ai_generatable_topics are deliberately left
        # untouched rather than filtered down too: a chain/gate pointing at
        # a topic excluded here just never finds an exercise to expedite
        # (Tutor._expedite_dependent() already treats "dependent topic has
        # no exercises" as a no-op, the same case a topic with genuinely no
        # exercises in the full course hits), and the rest are inert,
        # unused data for a topic that can never appear in this view's
        # exercises anyway.
        allowed = frozenset(topics)
        return replace(
            self,
            exercises=[
                exercise for exercise in self.exercises if exercise.topic in allowed
            ],
        )
