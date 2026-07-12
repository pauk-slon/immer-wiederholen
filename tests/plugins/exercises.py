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
    recall: NotRequired[RecallData]


class RecallKwargs(TypedDict, total=False):
    answer: list[str]
    question: str
    hint: dict[Language, str]


class ExerciseDataKwargs(TypedDict, total=False):
    topic: str
    category: Category
    answer: str
    distractors: list[str]
    recall: bool | RecallKwargs


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
    if recall := kwargs.pop("recall", False):
        recall_kwargs = {} if isinstance(recall, bool) else recall
        exercise_data["recall"] = RecallData(
            question=recall_kwargs.pop("question", "Ich ___ (der Bus)."),
            answer=recall_kwargs.pop("answer", ["Ich warte auf den Bus."]),
        )
        if "hint" in recall_kwargs:
            exercise_data["recall"]["hint"] = recall_kwargs.pop("hint")
    return exercise_data


def make_exercise(**kwargs: Unpack[ExerciseDataKwargs]) -> Exercise:
    data = make_exercise_data(**kwargs)
    recall_data = data.get("recall")
    return Exercise(
        topic=data["topic"],
        category=data["category"],
        question=data["question"],
        answer=data["answer"],
        distractors=data["distractors"],
        explanation=data["explanation"],
        recall=Recall(**recall_data) if recall_data else None,
    )
