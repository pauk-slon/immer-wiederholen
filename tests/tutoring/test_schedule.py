import random
from collections import Counter
from datetime import UTC, date, datetime, timedelta

import pytest

from tests.plugins.tutoring import make_exercise
from wiederholen.tutoring import Course, Exercise, Journal, NoExerciseAvailable, Tutor


def _next(tutor: Tutor) -> Exercise:
    exercise, _events = tutor.next_exercise()
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


def test_next_exercise_returns_none_when_nothing_is_due_or_available() -> None:
    # Both pairs already have an entry, neither due today — nothing to
    # serve (an earlier "borrow from upcoming review" fallback was tried
    # and reverted; see git history).
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

    exercise, events = tutor.next_exercise()

    assert exercise is None
    assert events == [NoExerciseAvailable(reason="nothing_available")]


def test_next_exercise_returns_none_when_the_whole_course_is_gated() -> None:
    # A gated topic with no entry and no source to unlock it never becomes
    # available.
    exercise = make_exercise(word="mit", topic="preposition_meaning")
    gated_topics = frozenset({"preposition_meaning"})
    tutor = Tutor(Course([exercise], gated_topics=gated_topics), {})

    exercise_, events = tutor.next_exercise()

    assert exercise_ is None
    assert events == [NoExerciseAvailable(reason="nothing_available")]


def test_progress_remaining_today_is_zero_for_empty_course() -> None:
    assert Tutor(Course([]), {}).progress().remaining_today == 0


def test_progress_remaining_today_excludes_not_yet_due_topics() -> None:
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


def test_progress_remaining_today_counts_shared_schedule_key_once() -> None:
    # Two YAML entries for the same word+topic share one schedule key, so a
    # due review counts once regardless of how many entries back it.
    duplicate_1 = make_exercise(word="helfen")
    duplicate_2 = make_exercise(word="helfen")
    journal = {
        "word_schedule": {
            "helfen": {
                "government": {
                    "interval_days": 30,
                    "due_date": (
                        datetime.now(UTC).date() - timedelta(days=1)
                    ).isoformat(),
                },
            },
        }
    }

    progress = Tutor(Course([duplicate_1, duplicate_2]), journal).progress()

    assert progress.remaining_today == 1


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
                    "introduced_at": (today - timedelta(days=11)).isoformat(),
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


def test_correct_answer_on_new_topic_is_still_due_today() -> None:
    # A pair's very first answer is a same-day "learning step" regardless of
    # correctness — real spacing (interval_days-based due dates) only starts
    # from the second answer onward (see test_correct_answer_doubles_interval).
    exercise = make_exercise(word="warten", answer="auf")
    state: dict = {}
    Tutor(Course([exercise]), state).check_answer(exercise, "auf")
    entry = state["word_schedule"]["warten"]["government"]
    assert entry["due_date"] == datetime.now(UTC).date().isoformat()


def test_correct_answer_caps_interval_at_max() -> None:
    exercise = make_exercise(word="warten", answer="auf")
    today = datetime.now(UTC).date()
    state = {
        "word_schedule": {
            "warten": {
                "government": {
                    "interval_days": 50,
                    "due_date": (today - timedelta(days=11)).isoformat(),
                    "introduced_at": (today - timedelta(days=11)).isoformat(),
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


def test_malformed_topic_key_is_ignored() -> None:
    # A topic-level key that isn't a string (e.g. corrupted data) is
    # skipped, not treated as a real topic.
    exercise = make_exercise(word="warten", answer="auf")
    today = datetime.now(UTC).date()
    state = {
        "word_schedule": {
            "warten": {
                123: {
                    "interval_days": 1,
                    "due_date": today.isoformat(),
                    "introduced_at": today.isoformat(),
                },
                "government": {
                    "interval_days": 1,
                    "due_date": today.isoformat(),
                    "introduced_at": today.isoformat(),
                },
            },
        }
    }
    tutor = Tutor(Course([exercise]), state)

    assert tutor.progress().new_today == 1


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
    assert entry["due_date"] == today.isoformat()


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


def test_a_due_word_is_not_swamped_by_a_large_fresh_word_pool() -> None:
    # The fresh-word candidate pool per pick is bounded by the remaining
    # daily budget (NEW_WORDS_PER_DAY), not by how large the course is — so
    # a due word's chances of being picked stay roughly 1-in-(budget+1), not
    # diluted down to 1-in-(course size) by hundreds of untouched words.
    review = make_exercise(word="warten")
    fresh_words = [make_exercise(word=f"fresh{i}") for i in range(100)]
    today = datetime.now(UTC).date()
    state = {
        "word_schedule": {
            "warten": {
                "government": {
                    "interval_days": 1,
                    "due_date": today.isoformat(),
                    "introduced_at": (today - timedelta(days=1)).isoformat(),
                },
            },
        }
    }
    tutor = Tutor(Course([review, *fresh_words]), state)

    random.seed(1234)
    picks = Counter(_next(tutor).word == "warten" for _ in range(3000))

    observed_review_share = picks[True] / 3000
    expected_review_share = 1 / (Tutor.NEW_WORDS_PER_DAY + 1)
    assert abs(observed_review_share - expected_review_share) < 0.03


def test_queued_words_take_priority_and_can_exhaust_the_entire_budget() -> None:
    # Words with an expedited-but-never-answered entry (e.g. via a
    # chain/gate) fill the daily budget before any genuinely untouched word
    # gets a chance — here they exactly fill it, leaving nothing for fresh.
    queued_words = [
        make_exercise(word=f"queued{i}", topic="government")
        for i in range(Tutor.NEW_WORDS_PER_DAY)
    ]
    fresh_words = [make_exercise(word=f"fresh{i}") for i in range(20)]
    today = datetime.now(UTC).date()
    state = {
        "word_schedule": {
            f"queued{i}": {
                "government": {"interval_days": 0, "due_date": today.isoformat()},
            }
            for i in range(Tutor.NEW_WORDS_PER_DAY)
        }
    }
    tutor = Tutor(Course([*queued_words, *fresh_words]), state)

    words = {_next(tutor).word for _ in range(200)}

    assert words == {f"queued{i}" for i in range(Tutor.NEW_WORDS_PER_DAY)}


def test_topic_selection_prefers_due_over_new_within_the_same_word() -> None:
    government = make_exercise(word="sprechen", topic="government", answer="auf")
    partizip = make_exercise(word="sprechen", topic="partizip_ii", answer="gesprochen")
    today = datetime.now(UTC).date()
    state = {
        "word_schedule": {
            "sprechen": {
                "government": {
                    "interval_days": 4,
                    "due_date": (today - timedelta(days=1)).isoformat(),
                    "introduced_at": (today - timedelta(days=10)).isoformat(),
                },
            },
        }
    }
    tutor = Tutor(Course([government, partizip]), state)

    topics = {_next(tutor).topic for _ in range(50)}

    assert topics == {"government"}


def test_a_word_with_an_untouched_topic_is_free_even_if_its_other_topic_is_not_due() -> (
    None
):
    government = make_exercise(word="warten", topic="government", answer="auf")
    verb_case = make_exercise(word="warten", topic="verb_case", answer="dem Freund")
    fresh_words = [make_exercise(word=f"fresh{i}") for i in range(20)]
    today = datetime.now(UTC).date()
    state = {
        "word_schedule": {
            "warten": {
                "government": {
                    "interval_days": 10,
                    "due_date": (today + timedelta(days=9)).isoformat(),
                    "introduced_at": (today - timedelta(days=1)).isoformat(),
                },
            },
        }
    }
    tutor = Tutor(Course([government, verb_case, *fresh_words]), state)

    results = [_next(tutor) for _ in range(400)]

    # Reachable at all despite its other topic not being due (not gated
    # behind the fresh-word budget), and only the actually-eligible topic
    # (government isn't due) is ever shown for it.
    warten_topics = {ex.topic for ex in results if ex.word == "warten"}
    assert warten_topics == {"verb_case"}


def test_next_exercise_avoids_repeating_the_last_topic_when_word_repeat_is_forced() -> (
    None
):
    government = make_exercise(word="sprechen", topic="government", answer="auf")
    partizip = make_exercise(word="sprechen", topic="partizip_ii", answer="gesprochen")
    today = datetime.now(UTC).date()
    state = {
        "word_schedule": {
            "sprechen": {
                "government": {
                    "interval_days": 4,
                    "due_date": (today - timedelta(days=1)).isoformat(),
                    "introduced_at": (today - timedelta(days=10)).isoformat(),
                },
                "partizip_ii": {
                    "interval_days": 2,
                    "due_date": (today - timedelta(days=1)).isoformat(),
                    "introduced_at": (today - timedelta(days=5)).isoformat(),
                },
            },
        },
        "last_exercise": {
            "question": government.question,
            "word": "sprechen",
            "topic": "government",
            "answered_at": datetime.now(UTC).isoformat(),
            "is_recall_optional": False,
        },
    }
    tutor = Tutor(Course([government, partizip]), state)

    assert _next(tutor).topic == "partizip_ii"


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


def test_next_exercise_avoids_repeating_the_last_answered_pair() -> None:
    # warten becomes due again today right after being answered (same-day
    # first review), which could otherwise dominate REVIEW_WEIGHT-weighted
    # selection and get picked again as literally the next exercise.
    warten = make_exercise(word="warten", answer="auf")
    hoffen = make_exercise(word="hoffen", answer="auf")
    tutor = Tutor(Course([warten, hoffen]), {})

    tutor.check_answer(warten, "auf")

    assert _next(tutor).word == "hoffen"


def test_next_exercise_repeats_the_last_pair_when_nothing_else_is_due() -> None:
    exercise = make_exercise(word="warten", answer="auf")
    tutor = Tutor(Course([exercise]), {})

    tutor.check_answer(exercise, "auf")

    assert _next(tutor).word == "warten"


def test_next_exercise_prefers_a_different_word_over_a_different_topic_of_the_same_word() -> (
    None
):
    # sprechen has two independently-scheduled topics; warten is an unrelated
    # word. After answering sprechen/government, both sprechen/partizip_ii
    # (same word, different topic) and warten/government (different word)
    # are eligible — a different word should win over a different topic of
    # the same word, not just any non-matching pair.
    government = make_exercise(word="sprechen", topic="government", answer="auf")
    partizip = make_exercise(word="sprechen", topic="partizip_ii", answer="gesprochen")
    warten = make_exercise(word="warten", answer="auf")
    tutor = Tutor(Course([government, partizip, warten]), {})

    tutor.check_answer(government, "auf")

    assert _next(tutor).word == "warten"


def test_next_exercise_pair_exclusion_tolerates_a_last_exercise_without_word_or_topic() -> (
    None
):
    # Simulates a last_exercise recorded before word/topic were added to it —
    # pair-level exclusion should just no-op, not raise.
    warten = make_exercise(word="warten", answer="auf")
    hoffen = make_exercise(word="hoffen", answer="auf")
    state = {
        "last_exercise": {
            "question": "some old question",
            "answered_at": datetime.now(UTC).isoformat(),
            "is_recall_optional": False,
        }
    }
    tutor = Tutor(Course([warten, hoffen]), state)

    words = {_next(tutor).word for _ in range(50)}

    assert words == {"warten", "hoffen"}


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
    assert entry["due_date"] == today.isoformat()


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

        # remaining_today collapses both pairs to one word-budget slot (see
        # #119), so it can't distinguish "both available" from "only one" —
        # check next_exercise() selection directly instead, which is what
        # this test actually guards against (neither topic ending up
        # permanently locked/unreachable).
        topics = {_next(tutor).topic for _ in range(50)}

        assert topics == {"partizip_ii", "preteritum"}


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

        # The dependent now has a real entry, due today, instead of the
        # gated date.max fallback — this is what "unlocked" means. Whether
        # next_exercise() shows it *this same day* is a separate concern:
        # preposition_case is also due today (same-day first review), and
        # topic selection prefers a word's due topic over its new one, so
        # preposition_meaning won't win today — it'll surface once
        # preposition_case is no longer due.
        entry = state["word_schedule"]["mit"]["preposition_meaning"]
        assert entry["due_date"] == datetime.now(UTC).date().isoformat()

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

    def test_progress_remaining_today_excludes_locked_topics(self) -> None:
        # A locked (gated, never expedited) topic has no schedule entry at
        # all, so it can never contribute to remaining_today — only a real
        # due review of the unlocked source topic does.
        case_exercise = make_exercise(
            word="mit", topic="preposition_case", answer="Freund"
        )
        meaning_exercise = make_exercise(
            word="mit", topic="preposition_meaning", answer="mit"
        )
        chained_topics = {"preposition_case": ["preposition_meaning"]}
        gated_topics = frozenset({"preposition_meaning"})
        journal = {
            "word_schedule": {
                "mit": {
                    "preposition_case": {
                        "interval_days": 30,
                        "due_date": (
                            datetime.now(UTC).date() - timedelta(days=1)
                        ).isoformat(),
                    },
                },
            }
        }
        tutor = Tutor(
            Course(
                [case_exercise, meaning_exercise],
                word_chained_topics=chained_topics,
                gated_topics=gated_topics,
            ),
            journal,
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
            make_exercise(word=f"introduced{i}") for i in range(Tutor.NEW_WORDS_PER_DAY)
        ]
        exercises = [*capped_exercises, make_exercise(word="warten")]
        state = {
            "word_schedule": _introduced_today_schedule(Tutor.NEW_WORDS_PER_DAY, today),
        }
        tutor = Tutor(Course(exercises), state)

        exercise, events = tutor.next_exercise()

        assert exercise is None
        assert events == [NoExerciseAvailable(reason="daily_cap_reached")]

    def test_still_returns_a_due_review_when_cap_reached(self) -> None:
        today = datetime.now(UTC).date()
        new_exercise = make_exercise(word="warten")
        review_exercise = make_exercise(word="hoffen")
        capped_exercises = [
            make_exercise(word=f"introduced{i}") for i in range(Tutor.NEW_WORDS_PER_DAY)
        ]
        state = {
            "word_schedule": {
                **_introduced_today_schedule(Tutor.NEW_WORDS_PER_DAY, today),
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
            make_exercise(word=f"introduced{i}")
            for i in range(Tutor.NEW_WORDS_PER_DAY - 1)
        ]
        exercises = [*capped_exercises, make_exercise(word="warten")]
        state = {
            "word_schedule": _introduced_today_schedule(
                Tutor.NEW_WORDS_PER_DAY - 1, today
            ),
        }
        tutor = Tutor(Course(exercises), state)

        assert _next(tutor).word == "warten"

    def test_a_multi_topic_word_only_uses_one_slot_of_the_cap(self) -> None:
        # The cap counts distinct words, not (word, topic) pairs — sprechen's
        # second topic shouldn't need a slot of its own.
        government = make_exercise(word="sprechen", topic="government", answer="auf")
        partizip = make_exercise(
            word="sprechen", topic="partizip_ii", answer="gesprochen"
        )
        today = datetime.now(UTC).date()
        capped_exercises = [
            make_exercise(word=f"introduced{i}")
            for i in range(Tutor.NEW_WORDS_PER_DAY - 1)
        ]
        state = {
            "word_schedule": _introduced_today_schedule(
                Tutor.NEW_WORDS_PER_DAY - 1, today
            ),
        }
        tutor = Tutor(Course([government, partizip, *capped_exercises]), state)

        tutor.check_answer(government, "auf")

        assert _next(tutor).word == "sprechen"

    def test_a_stale_introduced_at_from_a_previous_day_does_not_count_toward_the_cap(
        self,
    ) -> None:
        today = datetime.now(UTC).date()
        yesterday = today - timedelta(days=1)
        capped_exercises = [
            make_exercise(word=f"introduced{i}") for i in range(Tutor.NEW_WORDS_PER_DAY)
        ]
        exercises = [*capped_exercises, make_exercise(word="warten")]
        state = {
            "word_schedule": _introduced_today_schedule(
                Tutor.NEW_WORDS_PER_DAY, yesterday
            )
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

    def test_entry_without_introduced_at_is_treated_as_new_regardless_of_interval_days(
        self,
    ) -> None:
        # record_mark() checks introduced_at directly, not interval_days as
        # an indirect proxy — a schedule entry with real interval_days but
        # no introduced_at is treated as new, and gets introduced_at
        # stamped on its next answer like any other new pair.
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

        assert (
            state["word_schedule"]["warten"]["government"]["introduced_at"]
            == today.isoformat()
        )

    def test_reset_progress_clears_introduced_at_along_with_the_schedule(self) -> None:
        data = {
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

        Journal.reset_progress(data)

        assert Journal(data).get_schedule_entry("warten", "government") is None

    def test_reset_progress_clears_todays_answer_stats(self) -> None:
        today = datetime.now(UTC).date().isoformat()
        data = {
            "today_answers": {"date": today, "answered": 5, "correct": 4},
        }

        Journal.reset_progress(data)

        assert Journal(data).get_answer_stats_today() == (0, 0)

    def test_expedited_dependent_is_not_stamped_as_introduced_until_answered(
        self,
    ) -> None:
        # _expedite_dependent() creates a schedule entry to unlock/advance a chained
        # topic, but that's not the same as the learner having seen it.
        case_exercise = make_exercise(
            word="mit", topic="preposition_case", answer="Freund"
        )
        meaning_exercise = make_exercise(
            word="mit", topic="preposition_meaning", answer="mit"
        )
        chained_topics = {"preposition_case": ["preposition_meaning"]}
        state: dict = {}
        tutor = Tutor(
            Course(
                [case_exercise, meaning_exercise], word_chained_topics=chained_topics
            ),
            state,
        )

        tutor.check_answer(case_exercise, "Freund")

        assert (
            "introduced_at" not in state["word_schedule"]["mit"]["preposition_meaning"]
        )

    def test_expedited_dependent_for_the_same_word_is_offered_despite_the_cap(
        self,
    ) -> None:
        # The cap is per word, not per (word, topic) pair: "mit" already used its
        # one slot for the day via case_exercise, so its chained dependent isn't
        # a *new* word and must still be offered even once the cap is otherwise
        # exhausted by unrelated words.
        case_exercise = make_exercise(
            word="mit", topic="preposition_case", answer="Freund"
        )
        meaning_exercise = make_exercise(
            word="mit", topic="preposition_meaning", answer="mit"
        )
        chained_topics = {"preposition_case": ["preposition_meaning"]}
        today = datetime.now(UTC).date()
        capped_exercises = [
            make_exercise(word=f"introduced{i}")
            for i in range(Tutor.NEW_WORDS_PER_DAY - 1)
        ]
        state = {
            "word_schedule": _introduced_today_schedule(
                Tutor.NEW_WORDS_PER_DAY - 1, today
            ),
        }
        tutor = Tutor(
            Course(
                [case_exercise, meaning_exercise, *capped_exercises],
                word_chained_topics=chained_topics,
            ),
            state,
        )

        tutor.check_answer(case_exercise, "Freund")

        assert _next(tutor).word == "mit"

    def test_expedited_dependent_for_a_different_word_still_respects_the_cap(
        self,
    ) -> None:
        # chains_by_answer keys the dependent by the source's *answer*, which can
        # be an entirely different word than the source — that dependent is
        # genuinely new and must not bypass an already-exhausted daily cap just
        # because some other word happened to trigger it.
        source_exercise = make_exercise(word="etwas", topic="government", answer="mit")
        meaning_exercise = make_exercise(
            word="mit", topic="preposition_meaning", answer="mit"
        )
        chained_topics = {"government": ["preposition_meaning"]}
        today = datetime.now(UTC).date()
        capped_exercises = [
            make_exercise(word=f"introduced{i}") for i in range(Tutor.NEW_WORDS_PER_DAY)
        ]
        state = {
            "word_schedule": _introduced_today_schedule(Tutor.NEW_WORDS_PER_DAY, today),
        }
        tutor = Tutor(
            Course(
                [source_exercise, meaning_exercise, *capped_exercises],
                answer_chained_topics=chained_topics,
            ),
            state,
        )

        tutor.check_answer(source_exercise, "mit")

        # The source itself is due again today too (same-day first review),
        # but the dependent it expedited must not leak through despite
        # that — only the source ever comes back, never the dependent.
        words = {_next(tutor).word for _ in range(50)}
        assert words == {"etwas"}

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


class TestExtraNewWords:
    def test_grant_lifts_the_cap_for_a_genuinely_new_word(self) -> None:
        today = datetime.now(UTC).date()
        capped_exercises = [
            make_exercise(word=f"introduced{i}") for i in range(Tutor.NEW_WORDS_PER_DAY)
        ]
        exercises = [*capped_exercises, make_exercise(word="warten")]
        state = {
            "word_schedule": _introduced_today_schedule(Tutor.NEW_WORDS_PER_DAY, today),
        }
        tutor = Tutor(Course(exercises), state)
        exercise, _events = tutor.next_exercise()
        assert exercise is None

        tutor.grant_extra_new_words()

        assert _next(tutor).word == "warten"

    def test_grant_stacks_across_multiple_calls(self) -> None:
        today = datetime.now(UTC).date()
        capped_exercises = [
            make_exercise(word=f"introduced{i}")
            for i in range(Tutor.NEW_WORDS_PER_DAY + Tutor.EXTRA_NEW_WORDS_GRANT)
        ]
        exercises = [*capped_exercises, make_exercise(word="warten")]
        state = {
            "word_schedule": _introduced_today_schedule(
                Tutor.NEW_WORDS_PER_DAY + Tutor.EXTRA_NEW_WORDS_GRANT, today
            ),
        }
        tutor = Tutor(Course(exercises), state)
        tutor.grant_extra_new_words()
        exercise, _events = tutor.next_exercise()
        assert exercise is None

        tutor.grant_extra_new_words()

        assert _next(tutor).word == "warten"

    def test_grant_from_a_previous_day_does_not_carry_over(self) -> None:
        today = datetime.now(UTC).date()
        yesterday = today - timedelta(days=1)
        capped_exercises = [
            make_exercise(word=f"introduced{i}") for i in range(Tutor.NEW_WORDS_PER_DAY)
        ]
        exercises = [*capped_exercises, make_exercise(word="warten")]
        state = {
            "word_schedule": _introduced_today_schedule(Tutor.NEW_WORDS_PER_DAY, today),
            "extra_new_words": {"date": yesterday.isoformat(), "count": 3},
        }
        tutor = Tutor(Course(exercises), state)

        exercise, _events = tutor.next_exercise()
        assert exercise is None

    def test_grant_is_a_noop_when_the_cap_is_not_currently_reached(self) -> None:
        exercise = make_exercise(word="warten")
        state: dict = {}
        tutor = Tutor(Course([exercise]), state)

        tutor.grant_extra_new_words()

        assert "extra_new_words" not in state

    def test_grant_ignores_a_stale_click_after_the_cap_has_reset_for_a_new_day(
        self,
    ) -> None:
        # A "study more" button left over from a previous day's message is
        # still clickable in Telegram — clicking it after the cap has already
        # reset for today must not silently raise today's cap.
        exercise = make_exercise(word="warten")
        yesterday = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
        state = {"extra_new_words": {"date": yesterday, "count": 3}}
        tutor = Tutor(Course([exercise]), state)

        tutor.grant_extra_new_words()

        assert state["extra_new_words"] == {"date": yesterday, "count": 3}


class TestTodayAnswers:
    def test_check_answer_counts_a_correct_answer(self) -> None:
        exercise = make_exercise(word="warten", answer="auf")
        state: dict = {}
        tutor = Tutor(Course([exercise]), state)

        tutor.check_answer(exercise, "auf")

        assert tutor.progress().answered_today == 1
        assert tutor.progress().correct_today == 1

    def test_check_answer_counts_a_wrong_answer_as_answered_but_not_correct(
        self,
    ) -> None:
        exercise = make_exercise(word="warten", answer="auf")
        state: dict = {}
        tutor = Tutor(Course([exercise]), state)

        tutor.check_answer(exercise, "für")

        assert tutor.progress().answered_today == 1
        assert tutor.progress().correct_today == 0

    def test_check_answer_accumulates_across_multiple_answers(self) -> None:
        exercise = make_exercise(word="warten", answer="auf")
        state: dict = {}
        tutor = Tutor(Course([exercise]), state)

        tutor.check_answer(exercise, "auf")
        tutor.check_answer(exercise, "für")
        tutor.check_answer(exercise, "auf")

        assert tutor.progress().answered_today == 3
        assert tutor.progress().correct_today == 2

    def test_today_answers_from_a_previous_day_do_not_carry_over(self) -> None:
        exercise = make_exercise(word="warten")
        yesterday = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
        state = {"today_answers": {"date": yesterday, "answered": 5, "correct": 4}}

        progress = Tutor(Course([exercise]), state).progress()

        assert progress.answered_today == 0
        assert progress.correct_today == 0

    def test_today_answers_are_zero_before_anything_is_answered(self) -> None:
        exercise = make_exercise(word="warten")

        progress = Tutor(Course([exercise]), {}).progress()

        assert progress.answered_today == 0
        assert progress.correct_today == 0


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
