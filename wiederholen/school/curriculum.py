import hashlib
import random
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Final, Self, TypedDict

import yaml

from wiederholen.school.i18n import LANGUAGES, Language

type Topic = str


def fold_case(text: str) -> str:
    # casefold() is Unicode caseless matching. Unlike lower(), it also
    # matches spellings like ss for ß
    return text.strip().casefold()


def _as_list(answer: object) -> object:
    # A course author writes a single answer as a plain string
    return [answer] if isinstance(answer, str) else answer


def _check_answer_type(answer: object) -> None:
    if not isinstance(answer, list) or not all(
        isinstance(item, str) for item in answer
    ):
        raise ValueError(
            f"answer must be a string or a list of strings, got {answer!r}"
        )


def _is_arrangement(text: str, chunks: Sequence[str]) -> bool:
    # Whether text is all the chunks joined with spaces, in some order. Both
    # are already folded, because a new order can move a capital letter
    if not chunks:
        return text == ""
    tried: set[str] = set()
    for index, chunk in enumerate(chunks):
        if chunk in tried:
            continue
        tried.add(chunk)
        if text == chunk:
            rest = ""
        elif text.startswith(chunk + " "):
            rest = text[len(chunk) + 1 :]
        else:
            continue
        if _is_arrangement(rest, [*chunks[:index], *chunks[index + 1 :]]):
            return True
    return False


@dataclass(frozen=True)
class Recall:
    question: str
    answer: list[str]
    hint: dict[Language, str] | None = None

    def __post_init__(self) -> None:
        _check_answer_type(self.answer)
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
        d = dict(d)
        d["answer"] = _as_list(d.get("answer"))
        return cls(**d)


@dataclass(frozen=True)
class Exercise:
    word: str
    topic: Topic
    question: str
    answer: list[str]
    distractors: list[str]
    explanation: dict[Language, str]
    recalls: list[Recall] = field(default_factory=list)
    description: dict[Language, str] | None = None
    word_bank: list[str] | None = None
    grammar_classes: list[str] | None = None

    def __post_init__(self) -> None:
        _check_answer_type(self.answer)
        if len(self.answer) == 0:
            raise ValueError("answer must not be empty")
        # Compared the way an answer is checked, so that two answers can't
        # differ only in case or surrounding spaces
        if len({fold_case(answer) for answer in self.answer}) != len(self.answer):
            raise ValueError(f"answer {self.answer} must not repeat an answer")
        # Stripped the way an answer is checked, but not folded, because an
        # option can differ from an answer only in case
        if {answer.strip() for answer in self.answer} & {
            distractor.strip() for distractor in self.distractors
        }:
            raise ValueError(f"answer {self.answer} must not be in distractors")
        if set(self.explanation.keys()) != LANGUAGES:
            raise ValueError(
                f"explanation must have keys {LANGUAGES}, got {set(self.explanation.keys())}"
            )
        if self.description is not None and set(self.description.keys()) != LANGUAGES:
            raise ValueError(
                f"description must have keys {LANGUAGES}, got {set(self.description.keys())}"
            )
        if self.word_bank is not None:
            if " ".join(self.word_bank) != self.answer[0]:
                raise ValueError(
                    f"word_bank {self.word_bank} must join into answer '{self.answer[0]}'"
                )
            folded_chunks = [fold_case(chunk) for chunk in self.word_bank]
            for answer in self.answer[1:]:
                if not _is_arrangement(fold_case(answer), folded_chunks):
                    raise ValueError(
                        f"answer '{answer}' must be an order of word_bank {self.word_bank}"
                    )
        if self.grammar_classes is not None and len(self.grammar_classes) == 0:
            raise ValueError("grammar_classes must not be empty if set")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Self:
        d = dict(d)
        d["answer"] = _as_list(d.get("answer"))
        if d.get("recalls") is not None:
            d["recalls"] = [Recall.from_dict(r) for r in d["recalls"]]
        return cls(**d)

    @property
    def answer_text(self) -> str:
        # Every answer, for the line that a frontend shows after a mistake
        return " / ".join(self.answer)

    @property
    def cue_key(self) -> str:
        # A hash of `question`, not a stored field — this is the one place
        # the derivation lives, so wiederholen.school.authoring.cues (the
        # worker, which uploads under this key) and
        # wiederholen.school.cue_store (which
        # looks it up at render time) can never disagree about what an
        # exercise's key is. Deliberately keyed by `question`, not e.g.
        # `word`+`topic`: several exercises in the same _meaning topic can
        # share a word while each describing a distinct, separately-
        # illustrated sentence (see docs/authoring.md).
        # A consequence worth accepting rather than working around: editing
        # `question` later (as the word_bank migration did) changes this
        # hash, silently orphaning whatever cue was generated for the old
        # wording — safe (never a mismatched cue), just means a re-run of
        # the worker is needed after a content edit that touches wording.
        return hashlib.sha256(self.question.encode()).hexdigest()


_SHUFFLE_ATTEMPTS: Final = 100


def shuffle_word_bank(word_bank: Sequence[str], answers: Sequence[str]) -> list[str]:
    # Shared by wiederholen.bot (re-inserted as a "(a / b / c)" parenthetical
    # after the question) and wiederholen.web (rendered as tap-to-arrange
    # tiles) — one shuffle-with-reshuffle-guard implementation rather than
    # each frontend keeping its own copy. A single-chunk word_bank has no
    # other permutation to land on, so it's returned as-is without
    # reshuffling.
    if len(word_bank) < 2:
        return list(word_bank)
    solved = {fold_case(answer) for answer in answers}
    shuffled = list(word_bank)
    # Reshuffle on the chance (real for a short sentence) that shuffle()
    # lands on an order that is an answer — the learner should never be
    # handed an already-solved word bank. The attempts are limited, because
    # every order can be an answer, as for [Ja, ja] with the answer "Ja ja"
    for _ in range(_SHUFFLE_ATTEMPTS):
        random.shuffle(shuffled)
        if fold_case(" ".join(shuffled)) not in solved:
            break
    return shuffled


@dataclass(frozen=True)
class TopicGroup:
    # A learner-facing bundle of topics, chosen as one unit (e.g. via the
    # bot's /topics) — a topic and the topics it chains/gates into belong
    # together, so a learner never picks a gated topic without its source.
    title: dict[Language, str]
    topics: frozenset[Topic]

    def __post_init__(self) -> None:
        if set(self.title.keys()) != LANGUAGES:
            raise ValueError(
                f"topic group title must have keys {LANGUAGES}, got {set(self.title.keys())}"
            )


class _TopicsConfig(TypedDict):
    topic_groups: dict[str, TopicGroup]
    word_chained_topics: dict[str, list[str]]
    answer_chained_topics: dict[str, list[str]]
    gated_topics: frozenset[str]
    topic_instructions: dict[str, dict[Language, str]]
    ai_generatable_topics: frozenset[str]
    cue_generatable_topics: frozenset[str]


@dataclass(frozen=True)
class Course:
    exercises: Sequence[Exercise]
    topic_groups: Mapping[str, TopicGroup] = field(default_factory=dict, kw_only=True)
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
    cue_generatable_topics: frozenset[str] = field(
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
                topic_groups={},
                word_chained_topics={},
                answer_chained_topics={},
                gated_topics=frozenset(),
                topic_instructions={},
                ai_generatable_topics=frozenset(),
                cue_generatable_topics=frozenset(),
            )
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        topic_groups: dict[str, TopicGroup] = {}
        group_by_topic: dict[Topic, str] = {}
        word_chained_topics: dict[str, list[str]] = {}
        gated_topics: set[str] = set()
        gates_by_source: dict[str, list[str]] = {}
        answer_chained_topics: dict[str, list[str]] = {}
        topic_instructions: dict[str, dict[Language, str]] = {}
        ai_generatable_topics: set[str] = set()
        cue_generatable_topics: set[str] = set()
        for group_id, group in data.items():
            topics = group.get("topics") or {}
            topic_groups[group_id] = TopicGroup(
                title=group["title"], topics=frozenset(topics)
            )
            for source, relations in topics.items():
                if source in group_by_topic:
                    raise ValueError(
                        f"topic '{source}' is in both '{group_by_topic[source]}' "
                        f"and '{group_id}' groups"
                    )
                group_by_topic[source] = group_id
                relations = relations or {}
                chains = relations.get("chains", [])
                gates = relations.get("gates", [])
                word_chained_topics[source] = list(dict.fromkeys([*chains, *gates]))
                gated_topics.update(gates)
                gates_by_source[source] = gates
                if chains_by_answer := relations.get("chains_by_answer", []):
                    answer_chained_topics[source] = list(
                        dict.fromkeys(chains_by_answer)
                    )
                if instruction := relations.get("instruction"):
                    topic_instructions[source] = instruction
                if relations.get("ai_generation"):
                    ai_generatable_topics.add(source)
                if relations.get("cue_generation"):
                    cue_generatable_topics.add(source)
        # A gated topic only ever unlocks via its source, so selecting its
        # group without the source's would leave it locked forever — chains
        # crossing groups are fine (an unselected dependent is just never
        # expedited, see restricted_to()), gates aren't.
        for source, gates in gates_by_source.items():
            for gated in gates:
                if group_by_topic.get(gated) != group_by_topic[source]:
                    raise ValueError(
                        f"gated topic '{gated}' must be in the same group as "
                        f"its source '{source}' ('{group_by_topic[source]}')"
                    )
        return _TopicsConfig(
            topic_groups=topic_groups,
            word_chained_topics=word_chained_topics,
            answer_chained_topics=answer_chained_topics,
            gated_topics=frozenset(gated_topics),
            topic_instructions=topic_instructions,
            ai_generatable_topics=frozenset(ai_generatable_topics),
            cue_generatable_topics=frozenset(cue_generatable_topics),
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
        # topic_groups/word_chained_topics/answer_chained_topics/gated_topics/
        # topic_instructions/ai_generatable_topics/cue_generatable_topics are
        # deliberately left untouched rather than filtered down too: a
        # chain/gate pointing at
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
