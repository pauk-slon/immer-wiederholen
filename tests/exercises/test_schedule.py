from datetime import date

from wiederholen.exercises import School

from tests.plugins.exercises import make_exercise


def test_next_exercise_only_picks_due_topics() -> None:
    exercises = [make_exercise(topic="warten"), make_exercise(topic="hoffen")]
    today = date(2026, 7, 12)
    state = {
        "topic_schedule": {
            "warten": {"interval_days": 30, "due_date": "2026-08-01"},
        }
    }
    teacher = School(exercises)(state)
    assert teacher.next_exercise(today).topic == "hoffen"


def test_next_exercise_falls_back_to_earliest_due_when_nothing_due() -> None:
    exercises = [make_exercise(topic="warten"), make_exercise(topic="hoffen")]
    today = date(2026, 7, 12)
    state = {
        "topic_schedule": {
            "warten": {"interval_days": 30, "due_date": "2026-08-10"},
            "hoffen": {"interval_days": 5, "due_date": "2026-07-20"},
        }
    }
    teacher = School(exercises)(state)
    assert teacher.next_exercise(today).topic == "hoffen"


def test_new_topic_is_always_due() -> None:
    exercise = make_exercise(topic="warten")
    teacher = School([exercise])({})
    assert teacher.next_exercise(date(2026, 7, 12)).topic == "warten"


def test_next_exercise_does_not_persist_entries_for_unscheduled_topics() -> None:
    exercises = [make_exercise(topic="warten"), make_exercise(topic="hoffen")]
    state = {
        "topic_schedule": {
            "warten": {"interval_days": 5, "due_date": "2026-08-01"},
        }
    }
    teacher = School(exercises)(state)

    teacher.next_exercise(date(2026, 7, 12))

    assert "hoffen" not in state["topic_schedule"]


def test_correct_answer_doubles_interval() -> None:
    exercise = make_exercise(topic="warten", answer="auf")
    state = {
        "topic_schedule": {"warten": {"interval_days": 4, "due_date": "2026-07-01"}}
    }
    today = date(2026, 7, 12)
    School([exercise])(state).check_answer(exercise, "auf", today)
    entry = state["topic_schedule"]["warten"]
    assert entry["interval_days"] == 8
    assert entry["due_date"] == "2026-07-20"


def test_correct_answer_on_new_topic_sets_interval_to_one() -> None:
    exercise = make_exercise(topic="warten", answer="auf")
    state: dict = {}
    today = date(2026, 7, 12)
    School([exercise])(state).check_answer(exercise, "auf", today)
    entry = state["topic_schedule"]["warten"]
    assert entry["interval_days"] == 1
    assert entry["due_date"] == "2026-07-13"


def test_correct_answer_caps_interval_at_max() -> None:
    exercise = make_exercise(topic="warten", answer="auf")
    state = {
        "topic_schedule": {"warten": {"interval_days": 50, "due_date": "2026-07-01"}}
    }
    today = date(2026, 7, 12)
    School([exercise])(state).check_answer(exercise, "auf", today)
    entry = state["topic_schedule"]["warten"]
    assert entry["interval_days"] == 60
    assert entry["due_date"] == "2026-09-10"


def test_wrong_answer_resets_interval_and_is_due_today() -> None:
    exercise = make_exercise(topic="warten", answer="auf")
    state = {
        "topic_schedule": {"warten": {"interval_days": 30, "due_date": "2026-07-01"}}
    }
    today = date(2026, 7, 12)
    School([exercise])(state).check_answer(exercise, "für", today)
    entry = state["topic_schedule"]["warten"]
    assert entry["interval_days"] == 1
    assert entry["due_date"] == "2026-07-12"
