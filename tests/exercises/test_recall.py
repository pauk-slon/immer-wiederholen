from wiederholen.exercises import Course, Tutor

from tests.plugins.exercises import make_exercise


def test_request_recall_records_last_recall_question() -> None:
    exercise = make_exercise(recalls=True)
    journal: dict = {}

    recall = Tutor(Course([exercise]), journal).request_recall(exercise)

    assert journal["last_recall_question"] == recall.question


def test_request_recall_avoids_repeating_last_recall_question() -> None:
    exercise = make_exercise(
        recalls=[
            {"question": "Er hat mir ___.", "answer": ["Er hat mir geholfen."]},
            {"question": "Sie hat ihr ___.", "answer": ["Sie hat ihr geholfen."]},
        ],
    )
    journal = {"last_recall_question": exercise.recalls[0].question}

    recall = Tutor(Course([exercise]), journal).request_recall(exercise)

    assert recall.question == exercise.recalls[1].question


def test_request_recall_repeats_question_when_no_other_variant_is_available() -> None:
    exercise = make_exercise(recalls=True)
    journal = {"last_recall_question": exercise.recalls[0].question}

    recall = Tutor(Course([exercise]), journal).request_recall(exercise)

    assert recall.question == exercise.recalls[0].question
