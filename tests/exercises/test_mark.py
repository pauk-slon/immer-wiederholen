from wiederholen.exercises import Course, Mark, RecallMode, Tutor

from tests.plugins.exercises import make_exercise


def test_check_returns_none_recall_without_recall_field() -> None:
    exercise = make_exercise(answer="auf", recalls=False)
    assert Tutor(Course([exercise]), {}).check_answer(exercise, "auf") == Mark(
        correct=True, recall=RecallMode.none
    )


def test_check_returns_required_recall_on_wrong_answer_with_recall() -> None:
    exercise = make_exercise(answer="auf", recalls=True)
    assert Tutor(Course([exercise]), {}).check_answer(exercise, "für") == Mark(
        correct=False, recall=RecallMode.required
    )


def test_check_returns_optional_recall_on_correct_answer_with_recall() -> None:
    exercise = make_exercise(answer="auf", recalls=True)
    assert Tutor(Course([exercise]), {}).check_answer(exercise, "auf") == Mark(
        correct=True, recall=RecallMode.optional
    )
