import random
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
    # Only for word-order exercises (konjunktion_wortstellung/
    # nebensatzkonjunktion_wortstellung): answer's own words, grouped into
    # meaningful phrase chunks (e.g. "in Hamburg" stays one chunk, not two),
    # in the *correct* order — not shuffled. Both frontends shuffle their own
    # copy fresh at render time (see curriculum.shuffle_word_bank()) rather
    # than reading a scramble baked in once at authoring time, which is what
    # question's own hand-written parenthetical hint used to be before this
    # field replaced it (see issue #191) — a single source of truth instead
    # of a copy an author had to keep in sync by hand.
    word_bank: list[str] | None = None

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
        if self.word_bank is not None and " ".join(self.word_bank) != self.answer:
            raise ValueError(
                f"word_bank {self.word_bank} must join into answer '{self.answer}'"
            )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Self:
        d = dict(d)
        if d.get("recalls") is not None:
            d["recalls"] = [Recall.from_dict(r) for r in d["recalls"]]
        return cls(**d)


def shuffle_word_bank(word_bank: Sequence[str]) -> list[str]:
    # Shared by wiederholen.bot (re-inserted as a "(a / b / c)" parenthetical
    # after the question) and wiederholen.web (rendered as tap-to-arrange
    # tiles) — one shuffle-with-reshuffle-guard implementation rather than
    # each frontend keeping its own copy. A single-chunk word_bank has no
    # other permutation to land on, so reshuffling would loop forever —
    # returned as-is instead.
    if len(word_bank) < 2:
        return list(word_bank)
    shuffled = list(word_bank)
    # Reshuffle on the chance (real for a short sentence) that shuffle()
    # lands back on the original order — the learner should never be handed
    # an already-solved word bank.
    while shuffled == list(word_bank):
        random.shuffle(shuffled)
    return shuffled


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
