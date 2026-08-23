from dataclasses import dataclass
from enum import Enum
from typing import Literal


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
