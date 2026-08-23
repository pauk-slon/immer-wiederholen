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


def _to_otel_attributes(event: TutoringEvent) -> dict[str, Any]:
    return {
        key: value.value if isinstance(value, Enum) else value
        for key, value in asdict(event).items()
        if value is not None
    }


def emit(event: TutoringEvent) -> None:
    span = trace.get_current_span()
    span.add_event(type(event).__name__, attributes=_to_otel_attributes(event))
