from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Literal

from opentelemetry import trace


class RecallMode(Enum):
    none = "none"
    optional = "optional"
    required = "required"


@dataclass(frozen=True)
class ExerciseAnswered:
    word: str
    topic: str
    is_correct: bool
    is_new: bool
    recall_mode: RecallMode
    prev_repetition_interval: int | None
    next_repetition_interval: int


@dataclass(frozen=True)
class TopicUnlocked:
    source_topic: str
    dependent_topic: str
    via: Literal["chain", "gate"]


@dataclass(frozen=True)
class NoExerciseAvailable:
    # "nothing_available": no due review and no available new pair at all.
    # "daily_cap_reached": pairs exist, but the new-word budget is
    #   exhausted and no already-introduced word is available either.
    reason: Literal["nothing_available", "daily_cap_reached"]


TutoringEvent = ExerciseAnswered | TopicUnlocked | NoExerciseAvailable


def _attributes(event: TutoringEvent) -> dict[str, Any]:
    # Enum values (e.g. RecallMode) aren't valid span event attribute types,
    # so unwrap them to their plain value; None isn't valid either (e.g.
    # ExerciseAnswered.prev_repetition_interval for a pair's very first
    # answer, which has no previous interval at all) — omit it rather than
    # invent a sentinel that could be mistaken for a real value like 0.
    # Everything else in a TutoringEvent is already a span-attribute-safe
    # type (str/bool/int).
    return {
        key: value.value if isinstance(value, Enum) else value
        for key, value in asdict(event).items()
        if value is not None
    }


def emit(event: TutoringEvent) -> None:
    span = trace.get_current_span()
    span.add_event(type(event).__name__, attributes=_attributes(event))
