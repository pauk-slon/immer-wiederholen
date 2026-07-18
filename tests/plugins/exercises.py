from collections.abc import Sequence
from typing import TypedDict, NotRequired, Literal, Unpack

from wiederholen.exercises import Category, Exercise, Recall


type Language = Literal["ru", "en"]


class RecallData(TypedDict):
    question: str
    answer: list[str]
    hint: NotRequired[dict[Language, str]]


class ExerciseData(TypedDict):
    topic: str
    category: Category
    question: str
    answer: str
    distractors: list[str]
    explanation: dict[Language, str]
    recalls: NotRequired[list[RecallData]]


class RecallKwargs(TypedDict, total=False):
    answer: list[str]
    question: str
    hint: dict[Language, str]


class ExerciseDataKwargs(TypedDict, total=False):
    topic: str
    category: Category
    answer: str
    distractors: list[str]
    recalls: bool | Sequence[RecallKwargs]


def _make_recall_data(recall_kwargs: RecallKwargs) -> RecallData:
    recall_data = RecallData(
        question=recall_kwargs.get("question", "Ich ___ (der Bus)."),
        answer=recall_kwargs.get("answer", ["Ich warte auf den Bus."]),
    )
    if "hint" in recall_kwargs:
        recall_data["hint"] = recall_kwargs["hint"]
    return recall_data


def make_exercise_data(**kwargs: Unpack[ExerciseDataKwargs]) -> ExerciseData:
    topic = kwargs.pop("topic", "warten")
    exercise_data = ExerciseData(
        question=f"Ich ___ {topic}.",
        topic=topic,
        category=kwargs.pop("category", "government"),
        distractors=kwargs.pop("distractors", ["für", "an", "um"]),
        answer=kwargs.pop("answer", "auf"),
        explanation={"ru": f"{topic} + Akk", "en": f"{topic} + Acc"},
    )
    if recalls := kwargs.pop("recalls", False):
        recalls_kwargs: list[RecallKwargs]
        if isinstance(recalls, Sequence):
            recalls_kwargs = list(recalls)
        else:
            recalls_kwargs = [RecallKwargs()]
        exercise_data["recalls"] = [_make_recall_data(r) for r in recalls_kwargs]
    return exercise_data


def make_exercise(**kwargs: Unpack[ExerciseDataKwargs]) -> Exercise:
    data = make_exercise_data(**kwargs)
    recalls_data = data.get("recalls")
    return Exercise(
        topic=data["topic"],
        category=data["category"],
        question=data["question"],
        answer=data["answer"],
        distractors=data["distractors"],
        explanation=data["explanation"],
        recalls=[Recall(**r) for r in recalls_data] if recalls_data else [],
    )
