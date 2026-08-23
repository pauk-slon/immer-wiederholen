from tests.plugins.curriculum import make_exercise
from wiederholen.school.curriculum import Course
from wiederholen.school.tutoring import Mark, RecallMode, Tutor


def test_check_returns_none_recall_without_recall_field() -> None:
    exercise = make_exercise(answer="auf", recalls=False)
    mark, _ = Tutor(Course([exercise]), {}).check_answer(exercise, "auf")
    assert mark == Mark(is_correct=True, recall=RecallMode.none)


def test_check_returns_required_recall_on_wrong_answer_with_recall() -> None:
    exercise = make_exercise(answer="auf", recalls=True)
    mark, _ = Tutor(Course([exercise]), {}).check_answer(exercise, "für")
    assert mark == Mark(is_correct=False, recall=RecallMode.required)


def test_check_returns_optional_recall_on_correct_answer_with_recall() -> None:
    exercise = make_exercise(answer="auf", recalls=True)
    mark, _ = Tutor(Course([exercise]), {}).check_answer(exercise, "auf")
    assert mark == Mark(is_correct=True, recall=RecallMode.optional)
