from tests.plugins.curriculum import make_exercise
from wiederholen.school.curriculum import Course
from wiederholen.school.tutoring import Tutor


def _schedule(word: str, topic: str, repetition_interval: int) -> dict:
    return {
        "word_schedule": {
            word: {
                topic: {
                    "repetition_interval": repetition_interval,
                    "due_date": "2020-01-01",
                }
            }
        }
    }


def test_get_hint_returns_none_without_grammar_classes() -> None:
    exercise = make_exercise(word="singen", topic="praeteritum")
    other = make_exercise(word="finden", topic="praeteritum", grammar_classes=["i-a-u"])
    course = Course([exercise, other])

    assert Tutor(course, {}).get_hint(exercise) is None


def test_get_hint_returns_none_without_any_matching_class() -> None:
    exercise = make_exercise(
        word="singen", topic="praeteritum", grammar_classes=["i-a-u"]
    )
    other = make_exercise(word="geben", topic="praeteritum", grammar_classes=["e-a-e"])
    course = Course([exercise, other])
    student_record = _schedule("geben", "praeteritum", 5)

    assert Tutor(course, student_record).get_hint(exercise) is None


def test_get_hint_excludes_the_exercises_own_word() -> None:
    exercise = make_exercise(
        word="singen", topic="praeteritum", grammar_classes=["i-a-u"]
    )
    same_word_other_question = make_exercise(
        word="singen", topic="praeteritum", answer="sang", grammar_classes=["i-a-u"]
    )
    course = Course([exercise, same_word_other_question])
    student_record = _schedule("singen", "praeteritum", 5)

    assert Tutor(course, student_record).get_hint(exercise) is None


def test_get_hint_only_considers_exercises_of_the_same_topic() -> None:
    exercise = make_exercise(
        word="singen", topic="praeteritum", grammar_classes=["i-a-u"]
    )
    other = make_exercise(word="finden", topic="partizip_ii", grammar_classes=["i-a-u"])
    course = Course([exercise, other])
    student_record = _schedule("finden", "partizip_ii", 5)

    assert Tutor(course, student_record).get_hint(exercise) is None


def test_get_hint_filters_out_candidates_without_a_durable_interval() -> None:
    exercise = make_exercise(
        word="singen", topic="praeteritum", grammar_classes=["i-a-u"]
    )
    other = make_exercise(word="finden", topic="praeteritum", grammar_classes=["i-a-u"])
    course = Course([exercise, other])
    # 1 is the interval after a pair's second-ever correct answer, not yet a
    # confirmed doubling — see Tutor.get_hint()'s own comment.
    student_record = _schedule("finden", "praeteritum", 1)

    assert Tutor(course, student_record).get_hint(exercise) is None


def test_get_hint_ignores_a_candidate_with_no_schedule_entry_at_all() -> None:
    exercise = make_exercise(
        word="singen", topic="praeteritum", grammar_classes=["i-a-u"]
    )
    other = make_exercise(word="finden", topic="praeteritum", grammar_classes=["i-a-u"])
    course = Course([exercise, other])

    assert Tutor(course, {}).get_hint(exercise) is None


def test_get_hint_returns_the_only_qualifying_candidate() -> None:
    exercise = make_exercise(
        word="singen", topic="praeteritum", grammar_classes=["i-a-u"]
    )
    other = make_exercise(word="finden", topic="praeteritum", grammar_classes=["i-a-u"])
    course = Course([exercise, other])
    student_record = _schedule("finden", "praeteritum", 2)

    assert Tutor(course, student_record).get_hint(exercise) == "finden"


def test_get_hint_prefers_the_candidate_with_the_highest_repetition_interval() -> None:
    exercise = make_exercise(
        word="singen", topic="praeteritum", grammar_classes=["i-a-u"]
    )
    weaker = make_exercise(
        word="finden", topic="praeteritum", grammar_classes=["i-a-u"]
    )
    stronger = make_exercise(
        word="springen", topic="praeteritum", grammar_classes=["i-a-u"]
    )
    course = Course([exercise, weaker, stronger])
    student_record = {
        "word_schedule": {
            "finden": {
                "praeteritum": {"repetition_interval": 2, "due_date": "2020-01-01"}
            },
            "springen": {
                "praeteritum": {"repetition_interval": 8, "due_date": "2020-01-01"}
            },
        }
    }

    assert Tutor(course, student_record).get_hint(exercise) == "springen"


def test_get_hint_breaks_ties_among_equally_strong_candidates() -> None:
    exercise = make_exercise(
        word="singen", topic="praeteritum", grammar_classes=["i-a-u"]
    )
    first = make_exercise(word="finden", topic="praeteritum", grammar_classes=["i-a-u"])
    second = make_exercise(
        word="springen", topic="praeteritum", grammar_classes=["i-a-u"]
    )
    course = Course([exercise, first, second])
    student_record = {
        "word_schedule": {
            "finden": {
                "praeteritum": {"repetition_interval": 4, "due_date": "2020-01-01"}
            },
            "springen": {
                "praeteritum": {"repetition_interval": 4, "due_date": "2020-01-01"}
            },
        }
    }

    for _ in range(20):
        assert Tutor(course, student_record).get_hint(exercise) in {
            "finden",
            "springen",
        }
