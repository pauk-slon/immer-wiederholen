from datetime import date, timedelta

from wiederholen.exercises import School

from tests.plugins.exercises import make_exercise


def test_progress_total_counts_distinct_schedule_keys() -> None:
    exercises = [make_exercise(topic="warten"), make_exercise(topic="hoffen")]

    assert School(exercises)({}).progress().total == 2


def test_progress_counts_shared_schedule_key_once() -> None:
    duplicate_1 = make_exercise(topic="helfen")
    duplicate_2 = make_exercise(topic="helfen")

    assert School([duplicate_1, duplicate_2])({}).progress().total == 1


def test_progress_unscheduled_topic_is_new() -> None:
    exercise = make_exercise(topic="warten")

    progress = School([exercise])({}).progress()

    assert progress.new == 1
    assert progress.learning == 0
    assert progress.mastered == 0


def test_progress_topic_below_max_interval_is_learning() -> None:
    exercise = make_exercise(topic="warten")
    journal = {
        "topic_schedule": {
            "warten:government": {
                "interval_days": 30,
                "due_date": (date.today() + timedelta(days=20)).isoformat(),
            },
        }
    }

    progress = School([exercise])(journal).progress()

    assert progress.learning == 1
    assert progress.new == 0
    assert progress.mastered == 0


def test_progress_topic_at_max_interval_is_mastered() -> None:
    exercise = make_exercise(topic="warten")
    journal = {
        "topic_schedule": {
            "warten:government": {
                "interval_days": 60,
                "due_date": (date.today() + timedelta(days=60)).isoformat(),
            },
        }
    }

    progress = School([exercise])(journal).progress()

    assert progress.mastered == 1
    assert progress.new == 0
    assert progress.learning == 0


def test_progress_due_matches_due_topics_count() -> None:
    exercise = make_exercise(topic="warten")
    journal = {
        "topic_schedule": {
            "warten:government": {
                "interval_days": 30,
                "due_date": (date.today() - timedelta(days=1)).isoformat(),
            },
        }
    }
    teacher = School([exercise])(journal)

    assert teacher.progress().due == teacher.due_topics_count() == 1


def test_progress_does_not_persist_entries_for_unscheduled_topics() -> None:
    exercise = make_exercise(topic="warten")
    journal: dict = {}

    School([exercise])(journal).progress()

    assert journal == {}
