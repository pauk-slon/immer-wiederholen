from datetime import UTC, datetime, timedelta

from tests.plugins.tutoring import make_exercise
from wiederholen.tutoring import (
    Course,
    ExerciseAnswered,
    RecallMode,
    TopicUnlocked,
    Tutor,
)


def test_answering_a_brand_new_pair_reports_is_new_and_no_previous_interval() -> None:
    exercise = make_exercise(word="warten", answer="auf")

    _, events = Tutor(Course([exercise]), {}).check_answer(exercise, "auf")

    assert events[0] == ExerciseAnswered(
        word="warten",
        topic="government",
        is_correct=True,
        is_new=True,
        recall_mode=RecallMode.none,
        previous_repetition_interval=None,
        next_repetition_interval=0,
    )


def test_answering_a_due_review_reports_is_new_false_and_interval_doubling() -> None:
    exercise = make_exercise(word="warten", answer="auf")
    today = datetime.now(UTC).date()
    state = {
        "word_schedule": {
            "warten": {
                "government": {
                    "repetition_interval": 4,
                    "due_date": (today - timedelta(days=1)).isoformat(),
                    "introduced_at": (today - timedelta(days=1)).isoformat(),
                },
            },
        }
    }

    _, events = Tutor(Course([exercise]), state).check_answer(exercise, "auf")

    assert events[0] == ExerciseAnswered(
        word="warten",
        topic="government",
        is_correct=True,
        is_new=False,
        recall_mode=RecallMode.none,
        previous_repetition_interval=4,
        next_repetition_interval=8,
    )


def test_wrong_answer_reports_correct_false_interval_reset_and_recall_mode() -> None:
    exercise = make_exercise(word="warten", answer="auf", recalls=True)
    today = datetime.now(UTC).date()
    state = {
        "word_schedule": {
            "warten": {
                "government": {
                    "repetition_interval": 8,
                    "due_date": (today - timedelta(days=1)).isoformat(),
                    "introduced_at": (today - timedelta(days=1)).isoformat(),
                },
            },
        }
    }

    _, events = Tutor(Course([exercise]), state).check_answer(exercise, "wrong")

    assert events[0] == ExerciseAnswered(
        word="warten",
        topic="government",
        is_correct=False,
        is_new=False,
        recall_mode=RecallMode.required,
        previous_repetition_interval=8,
        next_repetition_interval=1,
    )


def test_creating_a_dependent_entry_reports_topic_unlocked_via_chain() -> None:
    case_exercise = make_exercise(word="mit", topic="preposition_case", answer="Freund")
    meaning_exercise = make_exercise(
        word="mit", topic="preposition_meaning", answer="mit"
    )
    chained_topics = {"preposition_case": ["preposition_meaning"]}
    tutor = Tutor(
        Course([case_exercise, meaning_exercise], word_chained_topics=chained_topics),
        {},
    )

    _, events = tutor.check_answer(case_exercise, "Freund")

    assert (
        TopicUnlocked(
            source_topic="preposition_case",
            dependent_topic="preposition_meaning",
            via="chain",
        )
        in events
    )


def test_creating_a_gated_dependent_entry_reports_topic_unlocked_via_gate() -> None:
    case_exercise = make_exercise(word="mit", topic="preposition_case", answer="Freund")
    meaning_exercise = make_exercise(
        word="mit", topic="preposition_meaning", answer="mit"
    )
    chained_topics = {"preposition_case": ["preposition_meaning"]}
    gated_topics = frozenset({"preposition_meaning"})
    tutor = Tutor(
        Course(
            [case_exercise, meaning_exercise],
            word_chained_topics=chained_topics,
            gated_topics=gated_topics,
        ),
        {},
    )

    _, events = tutor.check_answer(case_exercise, "Freund")

    assert (
        TopicUnlocked(
            source_topic="preposition_case",
            dependent_topic="preposition_meaning",
            via="gate",
        )
        in events
    )


def test_an_already_progressing_dependent_reports_no_unlock_event() -> None:
    case_exercise = make_exercise(word="mit", topic="preposition_case", answer="Freund")
    meaning_exercise = make_exercise(
        word="mit", topic="preposition_meaning", answer="mit"
    )
    today = datetime.now(UTC).date()
    state = {
        "word_schedule": {
            "mit": {
                "preposition_meaning": {
                    "repetition_interval": 8,
                    "due_date": (today + timedelta(days=8)).isoformat(),
                },
            },
        }
    }
    chained_topics = {"preposition_case": ["preposition_meaning"]}
    tutor = Tutor(
        Course([case_exercise, meaning_exercise], word_chained_topics=chained_topics),
        state,
    )

    _, events = tutor.check_answer(case_exercise, "Freund")

    assert not any(isinstance(event, TopicUnlocked) for event in events)


def test_a_dependent_with_no_exercises_reports_no_unlock_event() -> None:
    case_exercise = make_exercise(word="mit", topic="preposition_case", answer="Freund")
    chained_topics = {"preposition_case": ["preposition_meaning"]}
    tutor = Tutor(
        Course([case_exercise], word_chained_topics=chained_topics),
        {},
    )

    _, events = tutor.check_answer(case_exercise, "Freund")

    assert not any(isinstance(event, TopicUnlocked) for event in events)


def test_answer_chained_dependent_reports_topic_unlocked() -> None:
    government_exercise = make_exercise(word="warten", topic="government", answer="auf")
    meaning_exercise = make_exercise(word="auf", topic="preposition_meaning")
    answer_chained_topics = {"government": ["preposition_meaning"]}
    tutor = Tutor(
        Course(
            [government_exercise, meaning_exercise],
            answer_chained_topics=answer_chained_topics,
        ),
        {},
    )

    _, events = tutor.check_answer(government_exercise, "auf")

    assert (
        TopicUnlocked(
            source_topic="government",
            dependent_topic="preposition_meaning",
            via="chain",
        )
        in events
    )
