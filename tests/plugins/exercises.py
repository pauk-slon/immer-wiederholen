from wiederholen.exercises import Exercise, Recall


def make_exercise(
    topic: str = "warten",
    answer: str = "auf",
    recall_question: str | None = None,
    recall_answer: list[str] | None = None,
    recall_hint: dict | None = None,
) -> Exercise:
    recall: Recall | None = None
    if recall_question is not None:
        assert recall_answer is not None
        recall = Recall(question=recall_question, answer=recall_answer, hint=recall_hint)
    return Exercise(
        question=f"Ich ___ {topic}.",
        topic=topic,
        distractors=["für", "an", "um"],
        answer=answer,
        explanation={"ru": f"{topic} + Akk", "en": f"{topic} + Acc"},
        recall=recall,
    )
