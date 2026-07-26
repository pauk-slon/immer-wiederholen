from collections.abc import Sequence
from typing import Literal, NotRequired, TypedDict, Unpack

from wiederholen.tutoring import Exercise, Recall, Topic

type Language = Literal["ru", "en"]


class RecallData(TypedDict):
    question: str
    answer: list[str]
    hint: NotRequired[dict[Language, str]]


class ExerciseData(TypedDict):
    word: str
    topic: Topic
    question: str
    answer: str
    distractors: list[str]
    explanation: dict[Language, str]
    recalls: NotRequired[list[RecallData]]
    description: NotRequired[dict[Language, str]]


class RecallKwargs(TypedDict, total=False):
    answer: list[str]
    question: str
    hint: dict[Language, str]


class ExerciseDataKwargs(TypedDict, total=False):
    word: str
    topic: Topic
    answer: str
    distractors: list[str]
    recalls: bool | Sequence[RecallKwargs]
    description: dict[Language, str]


def _make_recall_data(recall_kwargs: RecallKwargs) -> RecallData:
    recall_data = RecallData(
        question=recall_kwargs.get("question", "Ich ___ (der Bus)."),
        answer=recall_kwargs.get("answer", ["Ich warte auf den Bus."]),
    )
    if "hint" in recall_kwargs:
        recall_data["hint"] = recall_kwargs["hint"]
    return recall_data


def make_exercise_data(**kwargs: Unpack[ExerciseDataKwargs]) -> ExerciseData:
    word = kwargs.pop("word", "warten")
    exercise_data = ExerciseData(
        question=f"Ich ___ {word}.",
        word=word,
        topic=kwargs.pop("topic", "government"),
        distractors=kwargs.pop("distractors", ["für", "an", "um"]),
        answer=kwargs.pop("answer", "auf"),
        explanation={"ru": f"{word} + Akk", "en": f"{word} + Acc"},
    )
    if recalls := kwargs.pop("recalls", False):
        recalls_kwargs = recalls if isinstance(recalls, Sequence) else [RecallKwargs()]
        exercise_data["recalls"] = [_make_recall_data(r) for r in recalls_kwargs]
    if "description" in kwargs:
        exercise_data["description"] = kwargs.pop("description")
    return exercise_data


def make_exercise(**kwargs: Unpack[ExerciseDataKwargs]) -> Exercise:
    data = make_exercise_data(**kwargs)
    recalls_data = data.get("recalls")
    return Exercise(
        word=data["word"],
        topic=data["topic"],
        question=data["question"],
        answer=data["answer"],
        distractors=data["distractors"],
        explanation=data["explanation"],
        recalls=[Recall(**r) for r in recalls_data] if recalls_data else [],
        description=data.get("description"),
    )
