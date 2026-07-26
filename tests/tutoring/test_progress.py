from datetime import UTC, datetime, timedelta

from tests.plugins.tutoring import make_exercise
from wiederholen.tutoring import Course, Tutor


def test_progress_total_counts_distinct_schedule_keys() -> None:
    exercises = [make_exercise(word="warten"), make_exercise(word="hoffen")]

    assert Tutor(Course(exercises), {}).progress().total == 2


def test_progress_counts_shared_schedule_key_once() -> None:
    duplicate_1 = make_exercise(word="helfen")
    duplicate_2 = make_exercise(word="helfen")

    assert Tutor(Course([duplicate_1, duplicate_2]), {}).progress().total == 1


def test_progress_unscheduled_topic_is_new() -> None:
    exercise = make_exercise(word="warten")

    progress = Tutor(Course([exercise]), {}).progress()

    assert progress.new == 1
    assert progress.learning == 0
    assert progress.mastered == 0


def test_progress_topic_below_max_interval_is_learning() -> None:
    exercise = make_exercise(word="warten")
    journal = {
        "word_schedule": {
            "warten:government": {
                "interval_days": 30,
                "due_date": (datetime.now(UTC).date() + timedelta(days=20)).isoformat(),
            },
        }
    }

    progress = Tutor(Course([exercise]), journal).progress()

    assert progress.learning == 1
    assert progress.new == 0
    assert progress.mastered == 0


def test_progress_topic_at_max_interval_is_mastered() -> None:
    exercise = make_exercise(word="warten")
    journal = {
        "word_schedule": {
            "warten:government": {
                "interval_days": 60,
                "due_date": (datetime.now(UTC).date() + timedelta(days=60)).isoformat(),
            },
        }
    }

    progress = Tutor(Course([exercise]), journal).progress()

    assert progress.mastered == 1
    assert progress.new == 0
    assert progress.learning == 0


def test_progress_counts_overdue_topic_as_due() -> None:
    exercise = make_exercise(word="warten")
    journal = {
        "word_schedule": {
            "warten:government": {
                "interval_days": 30,
                "due_date": (datetime.now(UTC).date() - timedelta(days=1)).isoformat(),
            },
        }
    }
    tutor = Tutor(Course([exercise]), journal)

    assert tutor.progress().due == 1


def test_progress_does_not_persist_entries_for_unscheduled_topics() -> None:
    exercise = make_exercise(word="warten")
    journal: dict = {}

    Tutor(Course([exercise]), journal).progress()

    assert journal == {}
