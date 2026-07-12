import random
from collections import Counter
from datetime import date

import pytest

from wiederholen.exercises import School

from tests.plugins.exercises import make_exercise


def test_next_exercise_only_picks_due_topics() -> None:
    exercises = [make_exercise(topic="warten"), make_exercise(topic="hoffen")]
    today = date(2026, 7, 12)
    state = {
        "topic_schedule": {
            "warten:government": {"interval_days": 30, "due_date": "2026-08-01"},
        }
    }
    teacher = School(exercises)(state)
    assert teacher.next_exercise(today).topic == "hoffen"


def test_next_exercise_falls_back_to_earliest_due_when_nothing_due() -> None:
    exercises = [make_exercise(topic="warten"), make_exercise(topic="hoffen")]
    today = date(2026, 7, 12)
    state = {
        "topic_schedule": {
            "warten:government": {"interval_days": 30, "due_date": "2026-08-10"},
            "hoffen:government": {"interval_days": 5, "due_date": "2026-07-20"},
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
            "warten:government": {"interval_days": 5, "due_date": "2026-08-01"},
        }
    }
    teacher = School(exercises)(state)

    teacher.next_exercise(date(2026, 7, 12))

    assert "hoffen:government" not in state["topic_schedule"]


def test_correct_answer_doubles_interval() -> None:
    exercise = make_exercise(topic="warten", answer="auf")
    state = {
        "topic_schedule": {
            "warten:government": {"interval_days": 4, "due_date": "2026-07-01"}
        }
    }
    today = date(2026, 7, 12)
    School([exercise])(state).check_answer(exercise, "auf", today)
    entry = state["topic_schedule"]["warten:government"]
    assert entry["interval_days"] == 8
    assert entry["due_date"] == "2026-07-20"


def test_correct_answer_on_new_topic_sets_interval_to_one() -> None:
    exercise = make_exercise(topic="warten", answer="auf")
    state: dict = {}
    today = date(2026, 7, 12)
    School([exercise])(state).check_answer(exercise, "auf", today)
    entry = state["topic_schedule"]["warten:government"]
    assert entry["interval_days"] == 1
    assert entry["due_date"] == "2026-07-13"


def test_correct_answer_caps_interval_at_max() -> None:
    exercise = make_exercise(topic="warten", answer="auf")
    state = {
        "topic_schedule": {
            "warten:government": {"interval_days": 50, "due_date": "2026-07-01"}
        }
    }
    today = date(2026, 7, 12)
    School([exercise])(state).check_answer(exercise, "auf", today)
    entry = state["topic_schedule"]["warten:government"]
    assert entry["interval_days"] == 60
    assert entry["due_date"] == "2026-09-10"


def test_wrong_answer_resets_interval_and_is_due_today() -> None:
    exercise = make_exercise(topic="warten", answer="auf")
    state = {
        "topic_schedule": {
            "warten:government": {"interval_days": 30, "due_date": "2026-07-01"}
        }
    }
    today = date(2026, 7, 12)
    School([exercise])(state).check_answer(exercise, "für", today)
    entry = state["topic_schedule"]["warten:government"]
    assert entry["interval_days"] == 1
    assert entry["due_date"] == "2026-07-12"


@pytest.mark.parametrize(
    "malformed_entry",
    [
        "not a dict",
        {"interval_days": 30},
        {"due_date": "2026-07-01"},
        {"interval_days": "30", "due_date": "2026-07-01"},
        {"interval_days": 30, "due_date": 20260701},
        {"interval_days": 30, "due_date": "not a date"},
    ],
)
def test_malformed_schedule_entry_is_treated_as_unscheduled(malformed_entry) -> None:
    exercises = [make_exercise(topic="warten"), make_exercise(topic="hoffen")]
    state = {
        "topic_schedule": {
            "warten:government": malformed_entry,
            "hoffen:government": {"interval_days": 30, "due_date": "2026-08-01"},
        }
    }
    teacher = School(exercises)(state)
    assert teacher.next_exercise(date(2026, 7, 12)).topic == "warten"


def test_exercises_selected_evenly_across_topics() -> None:
    # "helfen" has two YAML entries for one topic (e.g. two recall variants),
    # "warten" has one. A fixed seed makes the pick counts reproducible: if
    # selection weren't topic-first, "helfen" would come up roughly twice as
    # often as "warten" instead of about equally often.
    single = make_exercise(topic="warten")
    duplicate_1 = make_exercise(topic="helfen")
    duplicate_2 = make_exercise(topic="helfen")
    teacher = School([single, duplicate_1, duplicate_2])({})

    random.seed(1234)
    picks = Counter(teacher.next_exercise().topic for _ in range(2000))

    assert 0.8 < picks["warten"] / picks["helfen"] < 1.25


def test_same_topic_different_categories_are_scheduled_independently() -> None:
    government = make_exercise(topic="sprechen", category="government", answer="auf")
    partizip = make_exercise(
        topic="sprechen", category="partizip_ii", answer="gesprochen"
    )
    today = date(2026, 7, 12)
    state: dict = {}
    teacher = School([government, partizip])(state)

    teacher.check_answer(government, "auf", today)

    assert "sprechen:government" in state["topic_schedule"]
    assert "sprechen:partizip_ii" not in state["topic_schedule"]


def test_schedule_entry_with_unknown_extra_key_is_still_respected() -> None:
    exercises = [make_exercise(topic="warten"), make_exercise(topic="hoffen")]
    state = {
        "topic_schedule": {
            "warten:government": {
                "interval_days": 30,
                "due_date": "2026-08-01",
                "extra": "field",
            },
            "hoffen:government": {"interval_days": 5, "due_date": "2026-07-01"},
        }
    }
    teacher = School(exercises)(state)
    assert teacher.next_exercise(date(2026, 7, 12)).topic == "hoffen"


@pytest.mark.parametrize(
    "malformed_entry",
    [
        "not a dict",
        {"interval_days": 30},
        {"interval_days": "30", "due_date": "2026-07-01"},
        {"interval_days": 30, "due_date": "not a date"},
    ],
)
def test_malformed_schedule_entry_is_overwritten_on_check_answer(
    malformed_entry,
) -> None:
    exercise = make_exercise(topic="warten", answer="auf")
    state = {"topic_schedule": {"warten:government": malformed_entry}}
    today = date(2026, 7, 12)
    School([exercise])(state).check_answer(exercise, "auf", today)
    entry = state["topic_schedule"]["warten:government"]
    assert entry["interval_days"] == 1
    assert entry["due_date"] == "2026-07-13"
