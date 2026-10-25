from tests.plugins.curriculum import make_exercise
from wiederholen.school.curriculum import Course
from wiederholen.school.tutoring import Mark, RecallMode, Tutor


def test_check_returns_none_recall_without_recall_field() -> None:
    exercise = make_exercise(answer="auf", recalls=False)
    mark = Tutor(Course([exercise]), {}).check_answer(exercise, "auf")
    assert mark == Mark(is_correct=True, recall=RecallMode.none)


def test_check_returns_required_recall_on_wrong_answer_with_recall() -> None:
    exercise = make_exercise(answer="auf", recalls=True)
    mark = Tutor(Course([exercise]), {}).check_answer(exercise, "für")
    assert mark == Mark(is_correct=False, recall=RecallMode.required)


def test_check_returns_optional_recall_on_correct_answer_with_recall() -> None:
    exercise = make_exercise(answer="auf", recalls=True)
    mark = Tutor(Course([exercise]), {}).check_answer(exercise, "auf")
    assert mark == Mark(is_correct=True, recall=RecallMode.optional)


def test_check_requires_the_exact_option_in_a_multiple_choice_exercise() -> None:
    exercise = make_exercise(answer="Ihr", distractors=["ihr", "sein", "euer"])
    mark = Tutor(Course([exercise]), {}).check_answer(exercise, "ihr")
    assert mark.is_correct is False


def test_check_accepts_an_option_typed_in_another_case() -> None:
    exercise = make_exercise(answer="auf", distractors=["für", "an", "um"])
    mark = Tutor(Course([exercise]), {}).check_answer(exercise, "Auf")
    assert mark.is_correct is True


def test_check_accepts_ss_for_eszett_in_a_typed_option() -> None:
    exercise = make_exercise(answer="heißer", distractors=["heiße", "heißes"])
    mark = Tutor(Course([exercise]), {}).check_answer(exercise, "heisser")
    assert mark.is_correct is True


def test_check_rejects_a_typed_option_that_matches_several_options_without_case() -> (
    None
):
    exercise = make_exercise(answer="Ihr", distractors=["ihr", "sein", "euer"])
    mark = Tutor(Course([exercise]), {}).check_answer(exercise, "IHR")
    assert mark.is_correct is False


def test_check_ignores_case_of_a_typed_answer() -> None:
    exercise = make_exercise(answer="Bus", distractors=[])
    mark = Tutor(Course([exercise]), {}).check_answer(exercise, "bus")
    assert mark.is_correct is True


def test_check_accepts_ss_for_eszett_in_a_typed_answer() -> None:
    exercise = make_exercise(answer="heißer", distractors=[])
    mark = Tutor(Course([exercise]), {}).check_answer(exercise, "heisser")
    assert mark.is_correct is True
