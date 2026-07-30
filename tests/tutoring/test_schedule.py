import random
from collections import Counter
from datetime import UTC, date, datetime, timedelta

import pytest

from tests.plugins.tutoring import make_exercise
from wiederholen.tutoring import Course, Exercise, Journal, Tutor


def _next(tutor: Tutor) -> Exercise:
    exercise = tutor.next_exercise()
    assert exercise is not None
    return exercise


def test_next_exercise_only_picks_due_topics() -> None:
    exercises = [make_exercise(word="warten"), make_exercise(word="hoffen")]
    today = datetime.now(UTC).date()
    state = {
        "word_schedule": {
            "warten": {
                "government": {
                    "interval_days": 30,
                    "due_date": (today + timedelta(days=20)).isoformat(),
                },
            },
        }
    }
    tutor = Tutor(Course(exercises), state)
    assert _next(tutor).word == "hoffen"


def test_next_exercise_falls_back_to_earliest_due_when_nothing_due() -> None:
    exercises = [make_exercise(word="warten"), make_exercise(word="hoffen")]
    today = datetime.now(UTC).date()
    state = {
        "word_schedule": {
            "warten": {
                "government": {
                    "interval_days": 30,
                    "due_date": (today + timedelta(days=29)).isoformat(),
                },
            },
            "hoffen": {
                "government": {
                    "interval_days": 5,
                    "due_date": (today + timedelta(days=8)).isoformat(),
                },
            },
        }
    }
    tutor = Tutor(Course(exercises), state)
    assert _next(tutor).word == "hoffen"


def test_next_exercise_breaks_earliest_due_ties_randomly() -> None:
    exercises = [make_exercise(word="warten"), make_exercise(word="hoffen")]
    today = datetime.now(UTC).date()
    due_date = (today + timedelta(days=8)).isoformat()
    state = {
        "word_schedule": {
            "warten": {"government": {"interval_days": 5, "due_date": due_date}},
            "hoffen": {"government": {"interval_days": 5, "due_date": due_date}},
        }
    }
    tutor = Tutor(Course(exercises), state)

    random.seed(1234)
    picks = Counter(_next(tutor).word for _ in range(2000))

    assert 0.8 < picks["warten"] / picks["hoffen"] < 1.25


def test_due_topics_count_is_zero_for_empty_course() -> None:
    assert Tutor(Course([]), {}).progress().remaining_today == 0


def test_due_topics_count_counts_new_topics_as_due() -> None:
    exercises = [make_exercise(word="warten"), make_exercise(word="hoffen")]

    assert Tutor(Course(exercises), {}).progress().remaining_today == 2


def test_due_topics_count_excludes_not_yet_due_topics() -> None:
    exercise = make_exercise(word="warten")
    journal = {
        "word_schedule": {
            "warten": {
                "government": {
                    "interval_days": 30,
                    "due_date": (
                        datetime.now(UTC).date() + timedelta(days=20)
                    ).isoformat(),
                },
            },
        }
    }

    assert Tutor(Course([exercise]), journal).progress().remaining_today == 0


def test_due_topics_count_counts_shared_schedule_key_once() -> None:
    # Two YAML entries for the same word+topic share one schedule key.
    duplicate_1 = make_exercise(word="helfen")
    duplicate_2 = make_exercise(word="helfen")

    assert Tutor(Course([duplicate_1, duplicate_2]), {}).progress().remaining_today == 1


def test_new_topic_is_always_due() -> None:
    exercise = make_exercise(word="warten")
    tutor = Tutor(Course([exercise]), {})
    assert _next(tutor).word == "warten"


def test_next_exercise_does_not_persist_entries_for_unscheduled_topics() -> None:
    exercises = [make_exercise(word="warten"), make_exercise(word="hoffen")]
    state = {
        "word_schedule": {
            "warten": {
                "government": {
                    "interval_days": 5,
                    "due_date": (
                        datetime.now(UTC).date() + timedelta(days=20)
                    ).isoformat(),
                },
            },
        }
    }
    tutor = Tutor(Course(exercises), state)

    tutor.next_exercise()

    assert "government" not in state["word_schedule"].get("hoffen", {})


def test_correct_answer_doubles_interval() -> None:
    exercise = make_exercise(word="warten", answer="auf")
    today = datetime.now(UTC).date()
    state = {
        "word_schedule": {
            "warten": {
                "government": {
                    "interval_days": 4,
                    "due_date": (today - timedelta(days=11)).isoformat(),
                },
            },
        }
    }
    Tutor(Course([exercise]), state).check_answer(exercise, "auf")
    entry = state["word_schedule"]["warten"]["government"]
    assert entry["interval_days"] == 8
    assert entry["due_date"] == (today + timedelta(days=8)).isoformat()


def test_correct_answer_on_new_topic_sets_interval_to_one() -> None:
    exercise = make_exercise(word="warten", answer="auf")
    state: dict = {}
    Tutor(Course([exercise]), state).check_answer(exercise, "auf")
    entry = state["word_schedule"]["warten"]["government"]
    assert entry["interval_days"] == 1
    assert (
        entry["due_date"] == (datetime.now(UTC).date() + timedelta(days=1)).isoformat()
    )


def test_correct_answer_caps_interval_at_max() -> None:
    exercise = make_exercise(word="warten", answer="auf")
    today = datetime.now(UTC).date()
    state = {
        "word_schedule": {
            "warten": {
                "government": {
                    "interval_days": 50,
                    "due_date": (today - timedelta(days=11)).isoformat(),
                },
            },
        }
    }
    Tutor(Course([exercise]), state).check_answer(exercise, "auf")
    entry = state["word_schedule"]["warten"]["government"]
    assert entry["interval_days"] == 60
    assert entry["due_date"] == (today + timedelta(days=60)).isoformat()


def test_wrong_answer_resets_interval_and_is_due_today() -> None:
    exercise = make_exercise(word="warten", answer="auf")
    today = datetime.now(UTC).date()
    state = {
        "word_schedule": {
            "warten": {
                "government": {
                    "interval_days": 30,
                    "due_date": (today - timedelta(days=11)).isoformat(),
                },
            },
        }
    }
    Tutor(Course([exercise]), state).check_answer(exercise, "für")
    entry = state["word_schedule"]["warten"]["government"]
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
            "warten": {"government": malformed_entry},
            "hoffen": {
                "government": {
                    "interval_days": 30,
                    "due_date": (
                        datetime.now(UTC).date() + timedelta(days=20)
                    ).isoformat(),
                },
            },
        }
    }
    tutor = Tutor(Course(exercises), state)
    assert _next(tutor).word == "warten"


def test_malformed_word_schedule_is_treated_as_unscheduled() -> None:
    # The word-level container itself (not just a leaf entry) can be malformed.
    exercises = [make_exercise(word="warten"), make_exercise(word="hoffen")]
    state = {
        "word_schedule": {
            "warten": "not a dict",
            "hoffen": {
                "government": {
                    "interval_days": 30,
                    "due_date": (
                        datetime.now(UTC).date() + timedelta(days=20)
                    ).isoformat(),
                },
            },
        }
    }
    tutor = Tutor(Course(exercises), state)
    assert _next(tutor).word == "warten"


def test_malformed_word_schedule_is_overwritten_on_check_answer() -> None:
    exercise = make_exercise(word="warten", answer="auf")
    today = datetime.now(UTC).date()
    state: dict = {"word_schedule": {}}
    state["word_schedule"]["warten"] = "not a dict"
    Tutor(Course([exercise]), state).check_answer(exercise, "auf")
    entry = state["word_schedule"]["warten"]["government"]  # ty: ignore[invalid-argument-type]
    assert entry["interval_days"] == 1
    assert entry["due_date"] == (today + timedelta(days=1)).isoformat()


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
    picks = Counter(_next(tutor).word for _ in range(2000))

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

    result = _next(tutor)

    assert result.question == ueber.question


def test_next_exercise_repeats_question_when_no_other_variant_is_available() -> None:
    # Both partizip_ii entries for one word render the same question text and
    # differ only in recall — excluding by question leaves no alternative, so
    # the repeat is unavoidable rather than something to filter out.
    duplicate_1 = make_exercise(word="helfen")
    duplicate_2 = make_exercise(word="helfen")
    state = {"last_exercise": {"question": duplicate_1.question}}
    tutor = Tutor(Course([duplicate_1, duplicate_2]), state)

    result = _next(tutor)

    assert result.question == duplicate_1.question


def test_same_word_different_topics_are_scheduled_independently() -> None:
    government = make_exercise(word="sprechen", topic="government", answer="auf")
    partizip = make_exercise(word="sprechen", topic="partizip_ii", answer="gesprochen")
    state: dict = {}
    tutor = Tutor(Course([government, partizip]), state)

    tutor.check_answer(government, "auf")

    assert "government" in state["word_schedule"]["sprechen"]
    assert "partizip_ii" not in state["word_schedule"]["sprechen"]


def test_schedule_entry_with_unknown_extra_key_is_still_respected() -> None:
    exercises = [make_exercise(word="warten"), make_exercise(word="hoffen")]
    today = datetime.now(UTC).date()
    state = {
        "word_schedule": {
            "warten": {
                "government": {
                    "interval_days": 30,
                    "due_date": (today + timedelta(days=20)).isoformat(),
                    "extra": "field",
                },
            },
            "hoffen": {
                "government": {
                    "interval_days": 5,
                    "due_date": (today - timedelta(days=11)).isoformat(),
                },
            },
        }
    }
    tutor = Tutor(Course(exercises), state)
    assert _next(tutor).word == "hoffen"


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
    today = datetime.now(UTC).date()
    state = {"word_schedule": {"warten": {"government": malformed_entry}}}
    Tutor(Course([exercise]), state).check_answer(exercise, "auf")
    entry = state["word_schedule"]["warten"]["government"]
    assert entry["interval_days"] == 1
    assert entry["due_date"] == (today + timedelta(days=1)).isoformat()


class TestChainedTopics:
    def test_does_not_advance_an_already_progressing_chained_topic(self) -> None:
        # A dependent with its own earned schedule (already answered at least
        # once) must not be yanked back to today just because the source was
        # answered again — that would erase progress the dependent made on its
        # own, and for a *mutual* chain (see below) would loop forever.
        case_exercise = make_exercise(
            word="mit", topic="preposition_case", answer="Freund"
        )
        meaning_exercise = make_exercise(
            word="mit", topic="preposition_meaning", answer="mit"
        )
        today = datetime.now(UTC).date()
        state = {
            "word_schedule": {
                "mit": {
                    "preposition_meaning": {
                        "interval_days": 8,
                        "due_date": (today + timedelta(days=8)).isoformat(),
                    },
                },
            }
        }
        chained_topics = {"preposition_case": ["preposition_meaning"]}
        tutor = Tutor(
            Course(
                [case_exercise, meaning_exercise],
                word_chained_topics=chained_topics,
            ),
            state,
        )

        tutor.check_answer(case_exercise, "Freund")

        entry = state["word_schedule"]["mit"]["preposition_meaning"]
        assert entry["due_date"] == (today + timedelta(days=8)).isoformat()
        assert entry["interval_days"] == 8

    def test_creates_a_never_scheduled_dependent_regardless_of_answer_correctness(
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
        tutor = Tutor(
            Course(
                [case_exercise, meaning_exercise],
                word_chained_topics=chained_topics,
            ),
            state,
        )

        tutor.check_answer(case_exercise, "wrong answer")

        entry = state["word_schedule"]["mit"]["preposition_meaning"]
        assert entry["due_date"] == datetime.now(UTC).date().isoformat()

    def test_does_not_push_back_an_already_due_chained_topic(self) -> None:
        case_exercise = make_exercise(
            word="mit", topic="preposition_case", answer="Freund"
        )
        meaning_exercise = make_exercise(
            word="mit", topic="preposition_meaning", answer="mit"
        )
        today = datetime.now(UTC).date()
        overdue_date = today - timedelta(days=3)
        state = {
            "word_schedule": {
                "mit": {
                    "preposition_meaning": {
                        "interval_days": 8,
                        "due_date": overdue_date.isoformat(),
                    },
                },
            }
        }
        chained_topics = {"preposition_case": ["preposition_meaning"]}
        tutor = Tutor(
            Course(
                [case_exercise, meaning_exercise],
                word_chained_topics=chained_topics,
            ),
            state,
        )

        tutor.check_answer(case_exercise, "Freund")

        entry = state["word_schedule"]["mit"]["preposition_meaning"]
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
        tutor = Tutor(
            Course(
                [case_exercise, meaning_exercise],
                word_chained_topics=chained_topics,
            ),
            state,
        )

        tutor.check_answer(case_exercise, "Freund")

        entry = state["word_schedule"]["mit"]["preposition_meaning"]
        assert entry["due_date"] == datetime.now(UTC).date().isoformat()

    def test_ignores_chained_topic_with_no_exercises(self) -> None:
        case_exercise = make_exercise(
            word="mit", topic="preposition_case", answer="Freund"
        )
        state: dict = {}
        chained_topics = {"preposition_case": ["preposition_meaning"]}
        tutor = Tutor(
            Course([case_exercise], word_chained_topics=chained_topics),
            state,
        )

        tutor.check_answer(case_exercise, "Freund")

        assert "preposition_meaning" not in state.get("word_schedule", {}).get(
            "mit", {}
        )

    def test_ignores_unrelated_topic(self) -> None:
        government_exercise = make_exercise(
            word="warten", topic="government", answer="auf"
        )
        meaning_exercise = make_exercise(
            word="mit", topic="preposition_meaning", answer="mit"
        )
        today = datetime.now(UTC).date()
        state = {
            "word_schedule": {
                "mit": {
                    "preposition_meaning": {
                        "interval_days": 8,
                        "due_date": (today + timedelta(days=8)).isoformat(),
                    },
                },
            }
        }
        chained_topics = {"preposition_case": ["preposition_meaning"]}
        tutor = Tutor(
            Course(
                [government_exercise, meaning_exercise],
                word_chained_topics=chained_topics,
            ),
            state,
        )

        tutor.check_answer(government_exercise, "auf")

        entry = state["word_schedule"]["mit"]["preposition_meaning"]
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
            Course(
                [partizip_exercise, preteritum_exercise],
                word_chained_topics=chained_topics,
            ),
            {},
        )

        assert tutor.progress().remaining_today == 2


class TestAnswerChainedTopics:
    def test_does_not_advance_an_already_progressing_answer_chained_topic(
        self,
    ) -> None:
        government_exercise = make_exercise(
            word="warten", topic="government", answer="auf"
        )
        meaning_exercise = make_exercise(word="auf", topic="preposition_meaning")
        today = datetime.now(UTC).date()
        state = {
            "word_schedule": {
                "auf": {
                    "preposition_meaning": {
                        "interval_days": 8,
                        "due_date": (today + timedelta(days=8)).isoformat(),
                    },
                },
            }
        }
        answer_chained_topics = {"government": ["preposition_meaning"]}
        tutor = Tutor(
            Course(
                [government_exercise, meaning_exercise],
                answer_chained_topics=answer_chained_topics,
            ),
            state,
        )

        tutor.check_answer(government_exercise, "auf")

        entry = state["word_schedule"]["auf"]["preposition_meaning"]
        assert entry["due_date"] == (today + timedelta(days=8)).isoformat()
        assert entry["interval_days"] == 8

    def test_creates_a_due_today_entry_for_a_never_scheduled_answer_chained_topic(
        self,
    ) -> None:
        government_exercise = make_exercise(
            word="warten", topic="government", answer="auf"
        )
        meaning_exercise = make_exercise(word="auf", topic="preposition_meaning")
        case_exercise = make_exercise(word="auf", topic="preposition_case")
        answer_chained_topics = {
            "government": ["preposition_meaning", "preposition_case"],
        }
        state: dict = {}
        tutor = Tutor(
            Course(
                [government_exercise, meaning_exercise, case_exercise],
                answer_chained_topics=answer_chained_topics,
            ),
            state,
        )

        tutor.check_answer(government_exercise, "auf")

        today = datetime.now(UTC).date().isoformat()
        assert state["word_schedule"]["auf"]["preposition_meaning"]["due_date"] == today
        assert state["word_schedule"]["auf"]["preposition_case"]["due_date"] == today

    def test_does_not_expedite_by_word_when_only_chained_by_answer(self) -> None:
        government_exercise = make_exercise(
            word="warten", topic="government", answer="auf"
        )
        meaning_exercise = make_exercise(word="warten", topic="preposition_meaning")
        answer_chained_topics = {"government": ["preposition_meaning"]}
        state: dict = {}
        tutor = Tutor(
            Course(
                [government_exercise, meaning_exercise],
                answer_chained_topics=answer_chained_topics,
            ),
            state,
        )

        tutor.check_answer(government_exercise, "auf")

        assert "preposition_meaning" not in state.get("word_schedule", {}).get(
            "warten", {}
        )


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
            Course(
                [case_exercise, meaning_exercise],
                word_chained_topics=chained_topics,
                gated_topics=gated_topics,
            ),
            {},
        )

        assert _next(tutor).topic == "preposition_case"

    def test_answering_the_parent_unlocks_the_chained_topic(self) -> None:
        case_exercise = make_exercise(
            word="mit", topic="preposition_case", answer="Freund"
        )
        meaning_exercise = make_exercise(
            word="mit", topic="preposition_meaning", answer="mit"
        )
        chained_topics = {"preposition_case": ["preposition_meaning"]}
        gated_topics = frozenset({"preposition_meaning"})
        course = Course(
            [case_exercise, meaning_exercise],
            word_chained_topics=chained_topics,
            gated_topics=gated_topics,
        )
        state: dict = {}
        Tutor(course, state).check_answer(case_exercise, "Freund")

        assert _next(Tutor(course, state)).topic == "preposition_meaning"

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
            Course(
                [case_exercise, meaning_exercise],
                word_chained_topics=chained_topics,
                gated_topics=gated_topics,
            ),
            {},
        )

        for _ in range(50):
            assert _next(tutor).topic == "preposition_case"

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
            Course(
                [case_exercise, meaning_exercise],
                word_chained_topics=chained_topics,
                gated_topics=gated_topics,
            ),
            {},
        )

        assert tutor.progress().remaining_today == 1

    def test_unrelated_topic_is_never_locked(self) -> None:
        government_exercise = make_exercise(word="warten", topic="government")
        chained_topics = {"preposition_case": ["preposition_meaning"]}
        gated_topics = frozenset({"preposition_meaning"})
        tutor = Tutor(
            Course(
                [government_exercise],
                word_chained_topics=chained_topics,
                gated_topics=gated_topics,
            ),
            {},
        )

        assert _next(tutor).word == "warten"


def _introduced_today_schedule(count: int, today: date) -> dict:
    return {
        f"introduced{i}": {
            "government": {
                "interval_days": 1,
                "due_date": (today + timedelta(days=30)).isoformat(),
                "introduced_at": today.isoformat(),
            },
        }
        for i in range(count)
    }


class TestNewWordDailyCap:
    def test_returns_none_when_cap_reached_and_nothing_else_due(self) -> None:
        today = datetime.now(UTC).date()
        capped_exercises = [
            make_exercise(word=f"introduced{i}") for i in range(Tutor.NEW_PER_DAY)
        ]
        exercises = [*capped_exercises, make_exercise(word="warten")]
        state = {"word_schedule": _introduced_today_schedule(Tutor.NEW_PER_DAY, today)}
        tutor = Tutor(Course(exercises), state)

        assert tutor.next_exercise() is None

    def test_still_returns_a_due_review_when_cap_reached(self) -> None:
        today = datetime.now(UTC).date()
        new_exercise = make_exercise(word="warten")
        review_exercise = make_exercise(word="hoffen")
        capped_exercises = [
            make_exercise(word=f"introduced{i}") for i in range(Tutor.NEW_PER_DAY)
        ]
        state = {
            "word_schedule": {
                **_introduced_today_schedule(Tutor.NEW_PER_DAY, today),
                "hoffen": {
                    "government": {
                        "interval_days": 1,
                        "due_date": today.isoformat(),
                        "introduced_at": (today - timedelta(days=5)).isoformat(),
                    },
                },
            }
        }
        tutor = Tutor(Course([new_exercise, review_exercise, *capped_exercises]), state)

        assert _next(tutor).word == "hoffen"

    def test_still_offers_new_topics_below_the_cap(self) -> None:
        today = datetime.now(UTC).date()
        capped_exercises = [
            make_exercise(word=f"introduced{i}") for i in range(Tutor.NEW_PER_DAY - 1)
        ]
        exercises = [*capped_exercises, make_exercise(word="warten")]
        state = {
            "word_schedule": _introduced_today_schedule(Tutor.NEW_PER_DAY - 1, today),
        }
        tutor = Tutor(Course(exercises), state)

        assert _next(tutor).word == "warten"

    def test_a_stale_introduced_at_from_a_previous_day_does_not_count_toward_the_cap(
        self,
    ) -> None:
        today = datetime.now(UTC).date()
        yesterday = today - timedelta(days=1)
        capped_exercises = [
            make_exercise(word=f"introduced{i}") for i in range(Tutor.NEW_PER_DAY)
        ]
        exercises = [*capped_exercises, make_exercise(word="warten")]
        state = {
            "word_schedule": _introduced_today_schedule(Tutor.NEW_PER_DAY, yesterday)
        }
        tutor = Tutor(Course(exercises), state)

        assert _next(tutor).word == "warten"

    def test_check_answer_sets_introduced_at_for_a_brand_new_pair(self) -> None:
        exercise = make_exercise(word="warten", answer="auf")
        today = datetime.now(UTC).date()
        state: dict = {}

        Tutor(Course([exercise]), state).check_answer(exercise, "auf")

        entry = state["word_schedule"]["warten"]["government"]
        assert entry["introduced_at"] == today.isoformat()

    def test_check_answer_sets_introduced_at_even_on_a_wrong_answer(self) -> None:
        exercise = make_exercise(word="warten", answer="auf")
        today = datetime.now(UTC).date()
        state: dict = {}

        Tutor(Course([exercise]), state).check_answer(exercise, "wrong")

        entry = state["word_schedule"]["warten"]["government"]
        assert entry["introduced_at"] == today.isoformat()

    def test_check_answer_does_not_overwrite_an_existing_introduced_at(self) -> None:
        exercise = make_exercise(word="warten", answer="auf")
        today = datetime.now(UTC).date()
        original = (today - timedelta(days=10)).isoformat()
        state = {
            "word_schedule": {
                "warten": {
                    "government": {
                        "interval_days": 4,
                        "due_date": today.isoformat(),
                        "introduced_at": original,
                    },
                },
            },
        }

        Tutor(Course([exercise]), state).check_answer(exercise, "auf")

        assert (
            state["word_schedule"]["warten"]["government"]["introduced_at"] == original
        )

    def test_legacy_entry_without_introduced_at_is_not_treated_as_new(self) -> None:
        # A schedule entry created before introduced_at existed has no way to know
        # when it was first introduced, but it clearly isn't new — it already has
        # real interval_days from being reviewed. It must not be misclassified as
        # new (which would both wrongly consume the daily cap and let it get
        # excluded from the due pool once that cap is reached).
        exercise = make_exercise(word="warten", answer="auf")
        today = datetime.now(UTC).date()
        state = {
            "word_schedule": {
                "warten": {
                    "government": {
                        "interval_days": 30,
                        "due_date": today.isoformat(),
                    },
                },
            },
        }

        Tutor(Course([exercise]), state).check_answer(exercise, "auf")

        assert "introduced_at" not in state["word_schedule"]["warten"]["government"]

    def test_reset_schedule_clears_introduced_at_along_with_the_schedule(self) -> None:
        journal = Journal(
            {
                "word_schedule": {
                    "warten": {
                        "government": {
                            "interval_days": 1,
                            "due_date": "2026-01-01",
                            "introduced_at": "2026-01-01",
                        },
                    },
                },
            }
        )

        journal.reset_schedule()

        assert journal.get_schedule_entry("warten", "government") is None

    def test_expedited_dependent_still_counts_as_new_until_actually_answered(
        self,
    ) -> None:
        # _expedite_dependent() creates a schedule entry to unlock/advance a chained
        # topic, but that's not the same as the learner having seen it — it must
        # still be capped like any other never-shown pair.
        case_exercise = make_exercise(
            word="mit", topic="preposition_case", answer="Freund"
        )
        meaning_exercise = make_exercise(
            word="mit", topic="preposition_meaning", answer="mit"
        )
        chained_topics = {"preposition_case": ["preposition_meaning"]}
        today = datetime.now(UTC).date()
        capped_exercises = [
            make_exercise(word=f"introduced{i}") for i in range(Tutor.NEW_PER_DAY - 1)
        ]
        state = {
            "word_schedule": _introduced_today_schedule(Tutor.NEW_PER_DAY - 1, today),
        }
        tutor = Tutor(
            Course(
                [case_exercise, meaning_exercise, *capped_exercises],
                word_chained_topics=chained_topics,
            ),
            state,
        )

        tutor.check_answer(case_exercise, "Freund")

        assert (
            "introduced_at" not in state["word_schedule"]["mit"]["preposition_meaning"]
        )
        assert tutor.next_exercise() is None

    def test_expedited_dependent_gets_introduced_at_only_once_actually_answered(
        self,
    ) -> None:
        case_exercise = make_exercise(
            word="mit", topic="preposition_case", answer="Freund"
        )
        meaning_exercise = make_exercise(
            word="mit", topic="preposition_meaning", answer="mit"
        )
        chained_topics = {"preposition_case": ["preposition_meaning"]}
        today = datetime.now(UTC).date()
        state: dict = {}
        tutor = Tutor(
            Course(
                [case_exercise, meaning_exercise], word_chained_topics=chained_topics
            ),
            state,
        )

        tutor.check_answer(case_exercise, "Freund")
        tutor.check_answer(meaning_exercise, "mit")

        entry = state["word_schedule"]["mit"]["preposition_meaning"]
        assert entry["introduced_at"] == today.isoformat()


class TestRequestRecallInterval:
    def test_halves_the_interval_after_a_correct_answer(self) -> None:
        exercise = make_exercise(recalls=True)
        today = datetime.now(UTC).date()
        journal = {
            "word_schedule": {
                "warten": {
                    "government": {
                        "interval_days": 8,
                        "due_date": today.isoformat(),
                    },
                },
            }
        }
        tutor = Tutor(Course([exercise]), journal)
        tutor.check_answer(exercise, exercise.answer)

        tutor.request_recall(exercise)

        entry = journal["word_schedule"]["warten"]["government"]
        assert entry["interval_days"] == 8
        assert entry["due_date"] == (today + timedelta(days=8)).isoformat()

    def test_only_halves_once_per_episode(self) -> None:
        exercise = make_exercise(recalls=True)
        today = datetime.now(UTC).date()
        journal = {
            "word_schedule": {
                "warten": {
                    "government": {
                        "interval_days": 8,
                        "due_date": today.isoformat(),
                    },
                },
            }
        }
        tutor = Tutor(Course([exercise]), journal)
        tutor.check_answer(exercise, exercise.answer)

        tutor.request_recall(exercise)
        tutor.request_recall(exercise)

        entry = journal["word_schedule"]["warten"]["government"]
        assert entry["interval_days"] == 8

    def test_does_not_halve_when_last_mark_is_required(self) -> None:
        exercise = make_exercise(recalls=True)
        today = datetime.now(UTC).date()
        journal = {
            "last_exercise": {"is_recall_optional": False},
            "word_schedule": {
                "warten": {
                    "government": {
                        "interval_days": 8,
                        "due_date": today.isoformat(),
                    },
                },
            },
        }
        tutor = Tutor(Course([exercise]), journal)

        tutor.request_recall(exercise)

        entry = journal["word_schedule"]["warten"]["government"]
        assert entry["interval_days"] == 8
