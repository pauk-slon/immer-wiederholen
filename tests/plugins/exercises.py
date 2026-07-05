from typing import TypedDict, NotRequired, Literal, Unpack

from wiederholen.exercises import Exercise, Recall


type Language = Literal["ru", "en"]


class RecallData(TypedDict):
    question: str
    answer: list[str]
    hint: NotRequired[dict[Language, str]]


class ExerciseData(TypedDict):
    topic: str
    question: str
    answer: str
    distractors: list[str]
    explanation: dict[Language, str]
    recall: NotRequired[RecallData]


class ExerciseDataKwargs(TypedDict, total=False):
    topic: str
    answer: str
    recall_question: str
    recall_answer: list[str]
    recall_hint: dict[Language, str]


def make_exercise_data(**kwargs: Unpack[ExerciseDataKwargs]) -> ExerciseData:
    topic = kwargs.pop("topic", "warten")
    exercise_data = ExerciseData(
        question=f"Ich ___ {topic}.",
        topic=topic,
        distractors=["für", "an", "um"],
        answer=kwargs.pop("answer", "auf"),
        explanation={"ru": f"{topic} + Akk", "en": f"{topic} + Acc"},
    )
    recall_keys = {"recall_question", "recall_answer", "recall_hint"}
    if kwargs.keys() & recall_keys:
        exercise_data["recall"] = RecallData(
            question=kwargs.pop("recall_question", "Ich ___ (der Bus)."),
            answer=kwargs.pop("recall_answer", ["Ich warte auf den Bus."]),
        )
        if "recall_hint" in kwargs:
            exercise_data["recall"]["hint"] = kwargs.pop("recall_hint")
    return exercise_data


def make_exercise(**kwargs: Unpack[ExerciseDataKwargs]) -> Exercise:
    data = make_exercise_data(**kwargs)
    recall_data = data.get("recall")
    return Exercise(
        topic=data["topic"],
        question=data["question"],
        answer=data["answer"],
        distractors=data["distractors"],
        explanation=data["explanation"],
        recall=Recall(**recall_data) if recall_data else None,
    )
