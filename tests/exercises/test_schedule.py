import random
from collections import Counter
from datetime import date, timedelta

import pytest

from wiederholen.exercises import Course, Exercise, Tutor

from tests.plugins.exercises import make_exercise


def test_next_exercise_only_picks_due_topics() -> None:
    exercises = [make_exercise(topic="warten"), make_exercise(topic="hoffen")]
    today = date.today()
    state = {
        "topic_schedule": {
            "warten:government": {
                "interval_days": 30,
                "due_date": (today + timedelta(days=20)).isoformat(),
            },
        }
    }
    tutor = Tutor(Course(exercises), state)
    assert tutor.next_exercise().topic == "hoffen"


def test_next_exercise_falls_back_to_earliest_due_when_nothing_due() -> None:
    exercises = [make_exercise(topic="warten"), make_exercise(topic="hoffen")]
    today = date.today()
    state = {
        "topic_schedule": {
            "warten:government": {
                "interval_days": 30,
                "due_date": (today + timedelta(days=29)).isoformat(),
            },
            "hoffen:government": {
                "interval_days": 5,
                "due_date": (today + timedelta(days=8)).isoformat(),
            },
        }
    }
    tutor = Tutor(Course(exercises), state)
    assert tutor.next_exercise().topic == "hoffen"


def test_next_exercise_breaks_earliest_due_ties_randomly() -> None:
    exercises = [make_exercise(topic="warten"), make_exercise(topic="hoffen")]
    today = date.today()
    due_date = (today + timedelta(days=8)).isoformat()
    state = {
        "topic_schedule": {
            "warten:government": {"interval_days": 5, "due_date": due_date},
            "hoffen:government": {"interval_days": 5, "due_date": due_date},
        }
    }
    tutor = Tutor(Course(exercises), state)

    random.seed(1234)
    picks = Counter(tutor.next_exercise().topic for _ in range(2000))

    assert 0.8 < picks["warten"] / picks["hoffen"] < 1.25


def test_new_topic_is_always_due() -> None:
    exercise = make_exercise(topic="warten")
    tutor = Tutor(Course([exercise]), {})
    assert tutor.next_exercise().topic == "warten"


def test_next_exercise_does_not_persist_entries_for_unscheduled_topics() -> None:
    exercises = [make_exercise(topic="warten"), make_exercise(topic="hoffen")]
    state = {
        "topic_schedule": {
            "warten:government": {
                "interval_days": 5,
                "due_date": (date.today() + timedelta(days=20)).isoformat(),
            },
        }
    }
    tutor = Tutor(Course(exercises), state)

    tutor.next_exercise()

    assert "hoffen:government" not in state["topic_schedule"]


def test_correct_answer_doubles_interval() -> None:
    exercise = make_exercise(topic="warten", answer="auf")
    today = date.today()
    state = {
        "topic_schedule": {
            "warten:government": {
                "interval_days": 4,
                "due_date": (today - timedelta(days=11)).isoformat(),
            }
        }
    }
    Tutor(Course([exercise]), state).check_answer(exercise, "auf")
    entry = state["topic_schedule"]["warten:government"]
    assert entry["interval_days"] == 8
    assert entry["due_date"] == (today + timedelta(days=8)).isoformat()


def test_correct_answer_on_new_topic_sets_interval_to_one() -> None:
    exercise = make_exercise(topic="warten", answer="auf")
    state: dict = {}
    Tutor(Course([exercise]), state).check_answer(exercise, "auf")
    entry = state["topic_schedule"]["warten:government"]
    assert entry["interval_days"] == 1
    assert entry["due_date"] == (date.today() + timedelta(days=1)).isoformat()


def test_correct_answer_caps_interval_at_max() -> None:
    exercise = make_exercise(topic="warten", answer="auf")
    today = date.today()
    state = {
        "topic_schedule": {
            "warten:government": {
                "interval_days": 50,
                "due_date": (today - timedelta(days=11)).isoformat(),
            }
        }
    }
    Tutor(Course([exercise]), state).check_answer(exercise, "auf")
    entry = state["topic_schedule"]["warten:government"]
    assert entry["interval_days"] == 60
    assert entry["due_date"] == (today + timedelta(days=60)).isoformat()


def test_wrong_answer_resets_interval_and_is_due_today() -> None:
    exercise = make_exercise(topic="warten", answer="auf")
    today = date.today()
    state = {
        "topic_schedule": {
            "warten:government": {
                "interval_days": 30,
                "due_date": (today - timedelta(days=11)).isoformat(),
            }
        }
    }
    Tutor(Course([exercise]), state).check_answer(exercise, "für")
    entry = state["topic_schedule"]["warten:government"]
    assert entry["interval_days"] == 1
    assert entry["due_date"] == today.isoformat()


def test_check_answer_records_last_answered_question() -> None:
    exercise = make_exercise(topic="warten", answer="auf")
    journal: dict = {}

    Tutor(Course([exercise]), journal).check_answer(exercise, "auf")

    assert journal["last_answered_question"] == exercise.question


def test_check_answer_records_last_answered_at() -> None:
    exercise = make_exercise(topic="warten", answer="auf")
    journal: dict = {}

    Tutor(Course([exercise]), journal).check_answer(exercise, "auf")

    assert "last_answered_at" in journal


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
            "hoffen:government": {
                "interval_days": 30,
                "due_date": (date.today() + timedelta(days=20)).isoformat(),
            },
        }
    }
    tutor = Tutor(Course(exercises), state)
    assert tutor.next_exercise().topic == "warten"


def test_exercises_selected_evenly_across_topics() -> None:
    # "helfen" has two YAML entries for one topic (e.g. two recall variants),
    # "warten" has one. A fixed seed makes the pick counts reproducible: if
    # selection weren't topic-first, "helfen" would come up roughly twice as
    # often as "warten" instead of about equally often.
    single = make_exercise(topic="warten")
    duplicate_1 = make_exercise(topic="helfen")
    duplicate_2 = make_exercise(topic="helfen")
    tutor = Tutor(Course([single, duplicate_1, duplicate_2]), {})

    random.seed(1234)
    picks = Counter(tutor.next_exercise().topic for _ in range(2000))

    assert 0.8 < picks["warten"] / picks["helfen"] < 1.25


def test_next_exercise_avoids_repeating_last_answered_question() -> None:
    mit = Exercise(
        topic="sprechen",
        category="government",
        question="Ich spreche ___ meiner Mutter.",
        answer="mit",
        distractors=["über", "an", "für"],
        explanation={"ru": "x", "en": "y"},
    )
    ueber = Exercise(
        topic="sprechen",
        category="government",
        question="Wir sprechen ___ das Problem.",
        answer="über",
        distractors=["mit", "an", "für"],
        explanation={"ru": "x", "en": "y"},
    )
    state = {"last_answered_question": mit.question}
    tutor = Tutor(Course([mit, ueber]), state)

    result = tutor.next_exercise()

    assert result.question == ueber.question


def test_next_exercise_repeats_question_when_no_other_variant_is_available() -> None:
    # Both partizip_ii entries for one topic render the same question text and
    # differ only in recall — excluding by question leaves no alternative, so
    # the repeat is unavoidable rather than something to filter out.
    duplicate_1 = make_exercise(topic="helfen")
    duplicate_2 = make_exercise(topic="helfen")
    state = {"last_answered_question": duplicate_1.question}
    tutor = Tutor(Course([duplicate_1, duplicate_2]), state)

    result = tutor.next_exercise()

    assert result.question == duplicate_1.question


def test_same_topic_different_categories_are_scheduled_independently() -> None:
    government = make_exercise(topic="sprechen", category="government", answer="auf")
    partizip = make_exercise(
        topic="sprechen", category="partizip_ii", answer="gesprochen"
    )
    state: dict = {}
    tutor = Tutor(Course([government, partizip]), state)

    tutor.check_answer(government, "auf")

    assert "sprechen:government" in state["topic_schedule"]
    assert "sprechen:partizip_ii" not in state["topic_schedule"]


def test_schedule_entry_with_unknown_extra_key_is_still_respected() -> None:
    exercises = [make_exercise(topic="warten"), make_exercise(topic="hoffen")]
    today = date.today()
    state = {
        "topic_schedule": {
            "warten:government": {
                "interval_days": 30,
                "due_date": (today + timedelta(days=20)).isoformat(),
                "extra": "field",
            },
            "hoffen:government": {
                "interval_days": 5,
                "due_date": (today - timedelta(days=11)).isoformat(),
            },
        }
    }
    tutor = Tutor(Course(exercises), state)
    assert tutor.next_exercise().topic == "hoffen"


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
    today = date.today()
    state = {"topic_schedule": {"warten:government": malformed_entry}}
    Tutor(Course([exercise]), state).check_answer(exercise, "auf")
    entry = state["topic_schedule"]["warten:government"]
    assert entry["interval_days"] == 1
    assert entry["due_date"] == (today + timedelta(days=1)).isoformat()


class TestChainedCategories:
    def test_advances_chained_category_due_date_to_today(self) -> None:
        case_exercise = make_exercise(
            topic="mit", category="preposition_case", answer="Freund"
        )
        meaning_exercise = make_exercise(
            topic="mit", category="preposition_meaning", answer="mit"
        )
        today = date.today()
        state = {
            "topic_schedule": {
                "mit:preposition_meaning": {
                    "interval_days": 8,
                    "due_date": (today + timedelta(days=8)).isoformat(),
                },
            }
        }
        chained_categories = {"preposition_case": ["preposition_meaning"]}
        tutor = Tutor(
            Course([case_exercise, meaning_exercise], chained_categories), state
        )

        tutor.check_answer(case_exercise, "Freund")

        entry = state["topic_schedule"]["mit:preposition_meaning"]
        assert entry["due_date"] == today.isoformat()
        assert entry["interval_days"] == 8

    def test_advances_regardless_of_answer_correctness(self) -> None:
        case_exercise = make_exercise(
            topic="mit", category="preposition_case", answer="Freund"
        )
        meaning_exercise = make_exercise(
            topic="mit", category="preposition_meaning", answer="mit"
        )
        today = date.today()
        state = {
            "topic_schedule": {
                "mit:preposition_meaning": {
                    "interval_days": 8,
                    "due_date": (today + timedelta(days=8)).isoformat(),
                },
            }
        }
        chained_categories = {"preposition_case": ["preposition_meaning"]}
        tutor = Tutor(
            Course([case_exercise, meaning_exercise], chained_categories), state
        )

        tutor.check_answer(case_exercise, "wrong answer")

        entry = state["topic_schedule"]["mit:preposition_meaning"]
        assert entry["due_date"] == today.isoformat()

    def test_does_not_push_back_an_already_due_chained_category(self) -> None:
        case_exercise = make_exercise(
            topic="mit", category="preposition_case", answer="Freund"
        )
        meaning_exercise = make_exercise(
            topic="mit", category="preposition_meaning", answer="mit"
        )
        today = date.today()
        overdue_date = today - timedelta(days=3)
        state = {
            "topic_schedule": {
                "mit:preposition_meaning": {
                    "interval_days": 8,
                    "due_date": overdue_date.isoformat(),
                },
            }
        }
        chained_categories = {"preposition_case": ["preposition_meaning"]}
        tutor = Tutor(
            Course([case_exercise, meaning_exercise], chained_categories), state
        )

        tutor.check_answer(case_exercise, "Freund")

        entry = state["topic_schedule"]["mit:preposition_meaning"]
        assert entry["due_date"] == overdue_date.isoformat()

    def test_creates_a_due_today_entry_for_a_never_scheduled_chained_category(
        self,
    ) -> None:
        case_exercise = make_exercise(
            topic="mit", category="preposition_case", answer="Freund"
        )
        meaning_exercise = make_exercise(
            topic="mit", category="preposition_meaning", answer="mit"
        )
        state: dict = {}
        chained_categories = {"preposition_case": ["preposition_meaning"]}
        tutor = Tutor(
            Course([case_exercise, meaning_exercise], chained_categories), state
        )

        tutor.check_answer(case_exercise, "Freund")

        entry = state["topic_schedule"]["mit:preposition_meaning"]
        assert entry["due_date"] == date.today().isoformat()

    def test_ignores_chained_category_with_no_exercises(self) -> None:
        case_exercise = make_exercise(
            topic="mit", category="preposition_case", answer="Freund"
        )
        state: dict = {}
        chained_categories = {"preposition_case": ["preposition_meaning"]}
        tutor = Tutor(Course([case_exercise], chained_categories), state)

        tutor.check_answer(case_exercise, "Freund")

        assert "mit:preposition_meaning" not in state.get("topic_schedule", {})

    def test_ignores_unrelated_category(self) -> None:
        government_exercise = make_exercise(
            topic="warten", category="government", answer="auf"
        )
        meaning_exercise = make_exercise(
            topic="mit", category="preposition_meaning", answer="mit"
        )
        today = date.today()
        state = {
            "topic_schedule": {
                "mit:preposition_meaning": {
                    "interval_days": 8,
                    "due_date": (today + timedelta(days=8)).isoformat(),
                },
            }
        }
        chained_categories = {"preposition_case": ["preposition_meaning"]}
        tutor = Tutor(
            Course([government_exercise, meaning_exercise], chained_categories), state
        )

        tutor.check_answer(government_exercise, "auf")

        entry = state["topic_schedule"]["mit:preposition_meaning"]
        assert entry["due_date"] == (today + timedelta(days=8)).isoformat()


class TestChainedCategoryGating:
    def test_never_answered_parent_locks_the_chained_category(self) -> None:
        case_exercise = make_exercise(
            topic="mit", category="preposition_case", answer="Freund"
        )
        meaning_exercise = make_exercise(
            topic="mit", category="preposition_meaning", answer="mit"
        )
        chained_categories = {"preposition_case": ["preposition_meaning"]}
        tutor = Tutor(Course([case_exercise, meaning_exercise], chained_categories), {})

        assert tutor.next_exercise().category == "preposition_case"

    def test_answering_the_parent_unlocks_the_chained_category(self) -> None:
        case_exercise = make_exercise(
            topic="mit", category="preposition_case", answer="Freund"
        )
        meaning_exercise = make_exercise(
            topic="mit", category="preposition_meaning", answer="mit"
        )
        chained_categories = {"preposition_case": ["preposition_meaning"]}
        course = Course([case_exercise, meaning_exercise], chained_categories)
        state: dict = {}
        Tutor(course, state).check_answer(case_exercise, "Freund")

        assert Tutor(course, state).next_exercise().category == "preposition_meaning"

    def test_locked_category_is_excluded_even_when_it_would_otherwise_tie_for_due(
        self,
    ) -> None:
        # Both keys start unscheduled (date.min fallback), so without gating they'd
        # tie for "due today" and next_exercise() could randomly pick either. Gating
        # must exclude the never-unlocked child regardless of that tie.
        case_exercise = make_exercise(
            topic="mit", category="preposition_case", answer="Freund"
        )
        meaning_exercise = make_exercise(
            topic="mit", category="preposition_meaning", answer="mit"
        )
        chained_categories = {"preposition_case": ["preposition_meaning"]}
        tutor = Tutor(Course([case_exercise, meaning_exercise], chained_categories), {})

        for _ in range(50):
            assert tutor.next_exercise().category == "preposition_case"

    def test_due_topics_count_excludes_locked_categories(self) -> None:
        case_exercise = make_exercise(
            topic="mit", category="preposition_case", answer="Freund"
        )
        meaning_exercise = make_exercise(
            topic="mit", category="preposition_meaning", answer="mit"
        )
        chained_categories = {"preposition_case": ["preposition_meaning"]}
        tutor = Tutor(Course([case_exercise, meaning_exercise], chained_categories), {})

        assert tutor.due_topics_count() == 1

    def test_unrelated_category_is_never_locked(self) -> None:
        government_exercise = make_exercise(topic="warten", category="government")
        chained_categories = {"preposition_case": ["preposition_meaning"]}
        tutor = Tutor(Course([government_exercise], chained_categories), {})

        assert tutor.next_exercise().topic == "warten"
