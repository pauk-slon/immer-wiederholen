from tests.plugins.tutoring import make_exercise
from wiederholen.tutoring import Course, Tutor


def test_request_recall_records_last_recall_question() -> None:
    exercise = make_exercise(recalls=True)
    student_record = {"last_exercise": {"is_recall_optional": True}}

    recall = Tutor(Course([exercise]), student_record).request_recall(exercise)

    assert student_record["last_exercise"]["recall_question"] == recall.question


def test_request_recall_avoids_repeating_last_recall_question() -> None:
    exercise = make_exercise(
        recalls=[
            {"question": "Er hat mir ___.", "answer": ["Er hat mir geholfen."]},
            {"question": "Sie hat ihr ___.", "answer": ["Sie hat ihr geholfen."]},
        ],
    )
    student_record = {
        "last_exercise": {
            "is_recall_optional": True,
            "recall_question": exercise.recalls[0].question,
        }
    }

    recall = Tutor(Course([exercise]), student_record).request_recall(exercise)

    assert recall.question == exercise.recalls[1].question


def test_request_recall_repeats_question_when_no_other_variant_is_available() -> None:
    exercise = make_exercise(recalls=True)
    student_record = {
        "last_exercise": {
            "is_recall_optional": True,
            "recall_question": exercise.recalls[0].question,
        }
    }

    recall = Tutor(Course([exercise]), student_record).request_recall(exercise)

    assert recall.question == exercise.recalls[0].question
