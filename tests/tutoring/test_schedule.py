import random
from collections import Counter
from datetime import date, timedelta

import pytest

from wiederholen.tutoring import Course, Exercise, Tutor

from tests.plugins.tutoring import make_exercise


def test_next_exercise_only_picks_due_topics() -> None:
    exercises = [make_exercise(word="warten"), make_exercise(word="hoffen")]
    today = date.today()
    state = {
        "word_schedule": {
            "warten:government": {
                "interval_days": 30,
                "due_date": (today + timedelta(days=20)).isoformat(),
            },
        }
    }
    tutor = Tutor(Course(exercises), state)
    assert tutor.next_exercise().word == "hoffen"


def test_next_exercise_falls_back_to_earliest_due_when_nothing_due() -> None:
    exercises = [make_exercise(word="warten"), make_exercise(word="hoffen")]
    today = date.today()
    state = {
        "word_schedule": {
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
    assert tutor.next_exercise().word == "hoffen"


def test_next_exercise_breaks_earliest_due_ties_randomly() -> None:
    exercises = [make_exercise(word="warten"), make_exercise(word="hoffen")]
    today = date.today()
    due_date = (today + timedelta(days=8)).isoformat()
    state = {
        "word_schedule": {
            "warten:government": {"interval_days": 5, "due_date": due_date},
            "hoffen:government": {"interval_days": 5, "due_date": due_date},
        }
    }
    tutor = Tutor(Course(exercises), state)

    random.seed(1234)
    picks = Counter(tutor.next_exercise().word for _ in range(2000))

    assert 0.8 < picks["warten"] / picks["hoffen"] < 1.25


def test_new_topic_is_always_due() -> None:
    exercise = make_exercise(word="warten")
    tutor = Tutor(Course([exercise]), {})
    assert tutor.next_exercise().word == "warten"


def test_next_exercise_does_not_persist_entries_for_unscheduled_topics() -> None:
    exercises = [make_exercise(word="warten"), make_exercise(word="hoffen")]
    state = {
        "word_schedule": {
            "warten:government": {
                "interval_days": 5,
                "due_date": (date.today() + timedelta(days=20)).isoformat(),
            },
        }
    }
    tutor = Tutor(Course(exercises), state)

    tutor.next_exercise()

    assert "hoffen:government" not in state["word_schedule"]


def test_correct_answer_doubles_interval() -> None:
    exercise = make_exercise(word="warten", answer="auf")
    today = date.today()
    state = {
        "word_schedule": {
            "warten:government": {
                "interval_days": 4,
                "due_date": (today - timedelta(days=11)).isoformat(),
            }
        }
    }
    Tutor(Course([exercise]), state).check_answer(exercise, "auf")
    entry = state["word_schedule"]["warten:government"]
    assert entry["interval_days"] == 8
    assert entry["due_date"] == (today + timedelta(days=8)).isoformat()


def test_correct_answer_on_new_topic_sets_interval_to_one() -> None:
    exercise = make_exercise(word="warten", answer="auf")
    state: dict = {}
    Tutor(Course([exercise]), state).check_answer(exercise, "auf")
    entry = state["word_schedule"]["warten:government"]
    assert entry["interval_days"] == 1
    assert entry["due_date"] == (date.today() + timedelta(days=1)).isoformat()


def test_correct_answer_caps_interval_at_max() -> None:
    exercise = make_exercise(word="warten", answer="auf")
    today = date.today()
    state = {
        "word_schedule": {
            "warten:government": {
                "interval_days": 50,
                "due_date": (today - timedelta(days=11)).isoformat(),
            }
        }
    }
    Tutor(Course([exercise]), state).check_answer(exercise, "auf")
    entry = state["word_schedule"]["warten:government"]
    assert entry["interval_days"] == 60
    assert entry["due_date"] == (today + timedelta(days=60)).isoformat()


def test_wrong_answer_resets_interval_and_is_due_today() -> None:
    exercise = make_exercise(word="warten", answer="auf")
    today = date.today()
    state = {
        "word_schedule": {
            "warten:government": {
                "interval_days": 30,
                "due_date": (today - timedelta(days=11)).isoformat(),
            }
        }
    }
    Tutor(Course([exercise]), state).check_answer(exercise, "für")
    entry = state["word_schedule"]["warten:government"]
    assert entry["interval_days"] == 1
    assert entry["due_date"] == today.isoformat()


def test_check_answer_records_last_answered_question() -> None:
    exercise = make_exercise(word="warten", answer="auf")
    journal: dict = {}

    Tutor(Course([exercise]), journal).check_answer(exercise, "auf")

    assert journal["last_exercise"]["question"] == exercise.question


def test_check_answer_records_last_answered_at() -> None:
    exercise = make_exercise(word="warten", answer="auf")
    journal: dict = {}

    Tutor(Course([exercise]), journal).check_answer(exercise, "auf")

    assert "answered_at" in journal["last_exercise"]


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
    exercises = [make_exercise(word="warten"), make_exercise(word="hoffen")]
    state = {
        "word_schedule": {
            "warten:government": malformed_entry,
            "hoffen:government": {
                "interval_days": 30,
                "due_date": (date.today() + timedelta(days=20)).isoformat(),
            },
        }
    }
    tutor = Tutor(Course(exercises), state)
    assert tutor.next_exercise().word == "warten"


def test_exercises_selected_evenly_across_words() -> None:
    # "helfen" has two YAML entries for one word (e.g. two recall variants),
    # "warten" has one. A fixed seed makes the pick counts reproducible: if
    # selection weren't word-first, "helfen" would come up roughly twice as
    # often as "warten" instead of about equally often.
    single = make_exercise(word="warten")
    duplicate_1 = make_exercise(word="helfen")
    duplicate_2 = make_exercise(word="helfen")
    tutor = Tutor(Course([single, duplicate_1, duplicate_2]), {})

    random.seed(1234)
    picks = Counter(tutor.next_exercise().word for _ in range(2000))

    assert 0.8 < picks["warten"] / picks["helfen"] < 1.25


def test_next_exercise_avoids_repeating_last_answered_question() -> None:
    mit = Exercise(
        word="sprechen",
        topic="government",
        question="Ich spreche ___ meiner Mutter.",
        answer="mit",
        distractors=["über", "an", "für"],
        explanation={"ru": "x", "en": "y"},
    )
    ueber = Exercise(
        word="sprechen",
        topic="government",
        question="Wir sprechen ___ das Problem.",
        answer="über",
        distractors=["mit", "an", "für"],
        explanation={"ru": "x", "en": "y"},
    )
    state = {"last_exercise": {"question": mit.question}}
    tutor = Tutor(Course([mit, ueber]), state)

    result = tutor.next_exercise()

    assert result.question == ueber.question


def test_next_exercise_repeats_question_when_no_other_variant_is_available() -> None:
    # Both partizip_ii entries for one word render the same question text and
    # differ only in recall — excluding by question leaves no alternative, so
    # the repeat is unavoidable rather than something to filter out.
    duplicate_1 = make_exercise(word="helfen")
    duplicate_2 = make_exercise(word="helfen")
    state = {"last_exercise": {"question": duplicate_1.question}}
    tutor = Tutor(Course([duplicate_1, duplicate_2]), state)

    result = tutor.next_exercise()

    assert result.question == duplicate_1.question


def test_same_word_different_topics_are_scheduled_independently() -> None:
    government = make_exercise(word="sprechen", topic="government", answer="auf")
    partizip = make_exercise(word="sprechen", topic="partizip_ii", answer="gesprochen")
    state: dict = {}
    tutor = Tutor(Course([government, partizip]), state)

    tutor.check_answer(government, "auf")

    assert "sprechen:government" in state["word_schedule"]
    assert "sprechen:partizip_ii" not in state["word_schedule"]


def test_schedule_entry_with_unknown_extra_key_is_still_respected() -> None:
    exercises = [make_exercise(word="warten"), make_exercise(word="hoffen")]
    today = date.today()
    state = {
        "word_schedule": {
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
    assert tutor.next_exercise().word == "hoffen"


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
    exercise = make_exercise(word="warten", answer="auf")
    today = date.today()
    state = {"word_schedule": {"warten:government": malformed_entry}}
    Tutor(Course([exercise]), state).check_answer(exercise, "auf")
    entry = state["word_schedule"]["warten:government"]
    assert entry["interval_days"] == 1
    assert entry["due_date"] == (today + timedelta(days=1)).isoformat()


class TestChainedTopics:
    def test_advances_chained_topic_due_date_to_today(self) -> None:
        case_exercise = make_exercise(
            word="mit", topic="preposition_case", answer="Freund"
        )
        meaning_exercise = make_exercise(
            word="mit", topic="preposition_meaning", answer="mit"
        )
        today = date.today()
        state = {
            "word_schedule": {
                "mit:preposition_meaning": {
                    "interval_days": 8,
                    "due_date": (today + timedelta(days=8)).isoformat(),
                },
            }
        }
        chained_topics = {"preposition_case": ["preposition_meaning"]}
        tutor = Tutor(Course([case_exercise, meaning_exercise], chained_topics), state)

        tutor.check_answer(case_exercise, "Freund")

        entry = state["word_schedule"]["mit:preposition_meaning"]
        assert entry["due_date"] == today.isoformat()
        assert entry["interval_days"] == 8

    def test_advances_regardless_of_answer_correctness(self) -> None:
        case_exercise = make_exercise(
            word="mit", topic="preposition_case", answer="Freund"
        )
        meaning_exercise = make_exercise(
            word="mit", topic="preposition_meaning", answer="mit"
        )
        today = date.today()
        state = {
            "word_schedule": {
                "mit:preposition_meaning": {
                    "interval_days": 8,
                    "due_date": (today + timedelta(days=8)).isoformat(),
                },
            }
        }
        chained_topics = {"preposition_case": ["preposition_meaning"]}
        tutor = Tutor(Course([case_exercise, meaning_exercise], chained_topics), state)

        tutor.check_answer(case_exercise, "wrong answer")

        entry = state["word_schedule"]["mit:preposition_meaning"]
        assert entry["due_date"] == today.isoformat()

    def test_does_not_push_back_an_already_due_chained_topic(self) -> None:
        case_exercise = make_exercise(
            word="mit", topic="preposition_case", answer="Freund"
        )
        meaning_exercise = make_exercise(
            word="mit", topic="preposition_meaning", answer="mit"
        )
        today = date.today()
        overdue_date = today - timedelta(days=3)
        state = {
            "word_schedule": {
                "mit:preposition_meaning": {
                    "interval_days": 8,
                    "due_date": overdue_date.isoformat(),
                },
            }
        }
        chained_topics = {"preposition_case": ["preposition_meaning"]}
        tutor = Tutor(Course([case_exercise, meaning_exercise], chained_topics), state)

        tutor.check_answer(case_exercise, "Freund")

        entry = state["word_schedule"]["mit:preposition_meaning"]
        assert entry["due_date"] == overdue_date.isoformat()

    def test_creates_a_due_today_entry_for_a_never_scheduled_chained_topic(
        self,
    ) -> None:
        case_exercise = make_exercise(
            word="mit", topic="preposition_case", answer="Freund"
        )
        meaning_exercise = make_exercise(
            word="mit", topic="preposition_meaning", answer="mit"
        )
        state: dict = {}
        chained_topics = {"preposition_case": ["preposition_meaning"]}
        tutor = Tutor(Course([case_exercise, meaning_exercise], chained_topics), state)

        tutor.check_answer(case_exercise, "Freund")

        entry = state["word_schedule"]["mit:preposition_meaning"]
        assert entry["due_date"] == date.today().isoformat()

    def test_ignores_chained_topic_with_no_exercises(self) -> None:
        case_exercise = make_exercise(
            word="mit", topic="preposition_case", answer="Freund"
        )
        state: dict = {}
        chained_topics = {"preposition_case": ["preposition_meaning"]}
        tutor = Tutor(Course([case_exercise], chained_topics), state)

        tutor.check_answer(case_exercise, "Freund")

        assert "mit:preposition_meaning" not in state.get("word_schedule", {})

    def test_ignores_unrelated_topic(self) -> None:
        government_exercise = make_exercise(
            word="warten", topic="government", answer="auf"
        )
        meaning_exercise = make_exercise(
            word="mit", topic="preposition_meaning", answer="mit"
        )
        today = date.today()
        state = {
            "word_schedule": {
                "mit:preposition_meaning": {
                    "interval_days": 8,
                    "due_date": (today + timedelta(days=8)).isoformat(),
                },
            }
        }
        chained_topics = {"preposition_case": ["preposition_meaning"]}
        tutor = Tutor(
            Course([government_exercise, meaning_exercise], chained_topics), state
        )

        tutor.check_answer(government_exercise, "auf")

        entry = state["word_schedule"]["mit:preposition_meaning"]
        assert entry["due_date"] == (today + timedelta(days=8)).isoformat()

    def test_mutual_chains_without_gating_does_not_deadlock(self) -> None:
        partizip_exercise = make_exercise(
            word="sprechen", topic="partizip_ii", answer="gesprochen"
        )
        preteritum_exercise = make_exercise(
            word="sprechen", topic="preteritum", answer="sprach"
        )
        chained_topics = {
            "partizip_ii": ["preteritum"],
            "preteritum": ["partizip_ii"],
        }
        tutor = Tutor(
            Course([partizip_exercise, preteritum_exercise], chained_topics), {}
        )

        assert tutor.due_topics_count() == 2


class TestChainedTopicGating:
    def test_never_answered_parent_locks_the_chained_topic(self) -> None:
        case_exercise = make_exercise(
            word="mit", topic="preposition_case", answer="Freund"
        )
        meaning_exercise = make_exercise(
            word="mit", topic="preposition_meaning", answer="mit"
        )
        chained_topics = {"preposition_case": ["preposition_meaning"]}
        gated_topics = frozenset({"preposition_meaning"})
        tutor = Tutor(
            Course([case_exercise, meaning_exercise], chained_topics, gated_topics), {}
        )

        assert tutor.next_exercise().topic == "preposition_case"

    def test_answering_the_parent_unlocks_the_chained_topic(self) -> None:
        case_exercise = make_exercise(
            word="mit", topic="preposition_case", answer="Freund"
        )
        meaning_exercise = make_exercise(
            word="mit", topic="preposition_meaning", answer="mit"
        )
        chained_topics = {"preposition_case": ["preposition_meaning"]}
        gated_topics = frozenset({"preposition_meaning"})
        course = Course([case_exercise, meaning_exercise], chained_topics, gated_topics)
        state: dict = {}
        Tutor(course, state).check_answer(case_exercise, "Freund")

        assert Tutor(course, state).next_exercise().topic == "preposition_meaning"

    def test_locked_topic_is_excluded_even_when_it_would_otherwise_tie_for_due(
        self,
    ) -> None:
        # Both keys start unscheduled (date.min fallback), so without gating they'd
        # tie for "due today" and next_exercise() could randomly pick either. Gating
        # must exclude the never-unlocked child regardless of that tie.
        case_exercise = make_exercise(
            word="mit", topic="preposition_case", answer="Freund"
        )
        meaning_exercise = make_exercise(
            word="mit", topic="preposition_meaning", answer="mit"
        )
        chained_topics = {"preposition_case": ["preposition_meaning"]}
        gated_topics = frozenset({"preposition_meaning"})
        tutor = Tutor(
            Course([case_exercise, meaning_exercise], chained_topics, gated_topics), {}
        )

        for _ in range(50):
            assert tutor.next_exercise().topic == "preposition_case"

    def test_due_topics_count_excludes_locked_topics(self) -> None:
        case_exercise = make_exercise(
            word="mit", topic="preposition_case", answer="Freund"
        )
        meaning_exercise = make_exercise(
            word="mit", topic="preposition_meaning", answer="mit"
        )
        chained_topics = {"preposition_case": ["preposition_meaning"]}
        gated_topics = frozenset({"preposition_meaning"})
        tutor = Tutor(
            Course([case_exercise, meaning_exercise], chained_topics, gated_topics), {}
        )

        assert tutor.due_topics_count() == 1

    def test_unrelated_topic_is_never_locked(self) -> None:
        government_exercise = make_exercise(word="warten", topic="government")
        chained_topics = {"preposition_case": ["preposition_meaning"]}
        gated_topics = frozenset({"preposition_meaning"})
        tutor = Tutor(Course([government_exercise], chained_topics, gated_topics), {})

        assert tutor.next_exercise().word == "warten"


class TestRequestRecallInterval:
    def test_halves_the_interval_after_a_correct_answer(self) -> None:
        exercise = make_exercise(recalls=True)
        today = date.today()
        journal = {
            "word_schedule": {
                "warten:government": {
                    "interval_days": 8,
                    "due_date": today.isoformat(),
                },
            }
        }
        tutor = Tutor(Course([exercise]), journal)
        tutor.check_answer(exercise, exercise.answer)

        tutor.request_recall(exercise)

        entry = journal["word_schedule"]["warten:government"]
        assert entry["interval_days"] == 8
        assert entry["due_date"] == (today + timedelta(days=8)).isoformat()

    def test_only_halves_once_per_episode(self) -> None:
        exercise = make_exercise(recalls=True)
        today = date.today()
        journal = {
            "word_schedule": {
                "warten:government": {
                    "interval_days": 8,
                    "due_date": today.isoformat(),
                },
            }
        }
        tutor = Tutor(Course([exercise]), journal)
        tutor.check_answer(exercise, exercise.answer)

        tutor.request_recall(exercise)
        tutor.request_recall(exercise)

        entry = journal["word_schedule"]["warten:government"]
        assert entry["interval_days"] == 8

    def test_does_not_halve_when_last_mark_is_required(self) -> None:
        exercise = make_exercise(recalls=True)
        today = date.today()
        journal = {
            "last_exercise": {"is_recall_optional": False},
            "word_schedule": {
                "warten:government": {
                    "interval_days": 8,
                    "due_date": today.isoformat(),
                },
            },
        }
        tutor = Tutor(Course([exercise]), journal)

        tutor.request_recall(exercise)

        entry = journal["word_schedule"]["warten:government"]
        assert entry["interval_days"] == 8
