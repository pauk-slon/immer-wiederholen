from datetime import UTC, datetime, timedelta

from tests.plugins.tutoring import make_exercise
from wiederholen.tutoring import Course, Tutor


def test_progress_word_with_no_scheduled_topics_is_neither_learning_nor_mastered() -> (
    None
):
    exercise = make_exercise(word="warten")

    progress = Tutor(Course([exercise]), {}).progress()

    assert progress.learning == 0
    assert progress.mastered == 0


def test_progress_word_below_max_interval_is_learning() -> None:
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

    progress = Tutor(Course([exercise]), journal).progress()

    assert progress.learning == 1
    assert progress.mastered == 0


def test_progress_word_at_max_interval_is_mastered() -> None:
    exercise = make_exercise(word="warten")
    journal = {
        "word_schedule": {
            "warten": {
                "government": {
                    "interval_days": 60,
                    "due_date": (
                        datetime.now(UTC).date() + timedelta(days=60)
                    ).isoformat(),
                },
            },
        }
    }

    progress = Tutor(Course([exercise]), journal).progress()

    assert progress.mastered == 1
    assert progress.learning == 0


def test_progress_word_is_learning_until_every_one_of_its_topics_is_mastered() -> None:
    # sprechen has two independently scheduled topics; only one is maxed out, so
    # the word as a whole isn't "mastered" yet.
    government = make_exercise(word="sprechen", topic="government", answer="auf")
    partizip = make_exercise(word="sprechen", topic="partizip_ii", answer="gesprochen")
    today = datetime.now(UTC).date()
    journal = {
        "word_schedule": {
            "sprechen": {
                "government": {
                    "interval_days": 60,
                    "due_date": (today + timedelta(days=60)).isoformat(),
                },
                "partizip_ii": {
                    "interval_days": 4,
                    "due_date": (today + timedelta(days=4)).isoformat(),
                },
            },
        }
    }

    progress = Tutor(Course([government, partizip]), journal).progress()

    assert progress.learning == 1
    assert progress.mastered == 0


def test_progress_word_with_no_scheduled_topics_at_all_is_not_learning() -> None:
    # A word entirely untouched shouldn't inflate "learning" — it's still new,
    # just not surfaced as its own bucket anymore.
    government = make_exercise(word="sprechen", topic="government", answer="auf")
    partizip = make_exercise(word="sprechen", topic="partizip_ii", answer="gesprochen")

    progress = Tutor(Course([government, partizip]), {}).progress()

    assert progress.learning == 0
    assert progress.mastered == 0


def test_progress_counts_distinct_words_not_schedule_keys() -> None:
    # Two YAML entries for the same word+topic share one schedule key.
    duplicate_1 = make_exercise(word="helfen")
    duplicate_2 = make_exercise(word="helfen")
    journal = {
        "word_schedule": {
            "helfen": {
                "government": {
                    "interval_days": 30,
                    "due_date": (
                        datetime.now(UTC).date() + timedelta(days=20)
                    ).isoformat(),
                },
            },
        }
    }

    progress = Tutor(Course([duplicate_1, duplicate_2]), journal).progress()

    assert progress.learning == 1


def test_progress_does_not_persist_entries_for_unscheduled_topics() -> None:
    exercise = make_exercise(word="warten")
    journal: dict = {}

    Tutor(Course([exercise]), journal).progress()

    assert journal == {}


def test_progress_remaining_today_counts_overdue_reviews() -> None:
    exercise = make_exercise(word="warten")
    today = datetime.now(UTC).date()
    journal = {
        "word_schedule": {
            "warten": {
                "government": {
                    "interval_days": 30,
                    "due_date": (today - timedelta(days=1)).isoformat(),
                },
            },
        }
    }

    assert Tutor(Course([exercise]), journal).progress().remaining_today == 1


def test_progress_remaining_today_counts_a_due_but_not_yet_introduced_pair() -> None:
    # A pair expedited via a chain/gate (real entry, due today) but never
    # actually answered — next_exercise() would present it right now, so it
    # counts toward remaining_today even though it isn't "introduced" yet.
    exercise = make_exercise(word="mit", topic="preposition_meaning")
    today = datetime.now(UTC).date()
    journal = {
        "word_schedule": {
            "mit": {
                "preposition_meaning": {
                    "interval_days": 0,
                    "due_date": today.isoformat(),
                },
            },
        }
    }

    assert Tutor(Course([exercise]), journal).progress().remaining_today == 1


def test_progress_remaining_today_does_not_count_untouched_pairs() -> None:
    # Untouched pairs (no schedule entry at all) are never "due" — unlike an
    # earlier design (issue #119), remaining_today no longer estimates new
    # material at all, so a large untouched course can't inflate it either.
    exercises = [make_exercise(word=f"untouched{i}") for i in range(50)]

    assert Tutor(Course(exercises), {}).progress().remaining_today == 0


def test_progress_new_today_counts_words_introduced_today() -> None:
    exercise = make_exercise(word="warten", answer="auf")
    journal: dict = {}
    tutor = Tutor(Course([exercise]), journal)

    tutor.check_answer(exercise, "auf")

    assert tutor.progress().new_today == 1


def test_progress_new_today_counts_distinct_words_not_pairs() -> None:
    # sprechen has two independently scheduled topics; answering both today
    # is still just one new word for the day, not two.
    government = make_exercise(word="sprechen", topic="government", answer="auf")
    partizip = make_exercise(word="sprechen", topic="partizip_ii", answer="gesprochen")
    journal: dict = {}
    tutor = Tutor(Course([government, partizip]), journal)

    tutor.check_answer(government, "auf")
    tutor.check_answer(partizip, "gesprochen")

    assert tutor.progress().new_today == 1


def test_progress_new_today_is_zero_before_anything_is_answered() -> None:
    exercise = make_exercise(word="warten")

    assert Tutor(Course([exercise]), {}).progress().new_today == 0


def test_progress_new_today_excludes_a_queued_but_never_answered_word() -> None:
    # A pair expedited via a chain/gate has a real schedule entry (so it's
    # no longer "untouched") but was never actually answered — no
    # introduced_at anywhere for this word. Queued isn't introduced.
    exercise = make_exercise(word="mit", topic="preposition_meaning")
    today = datetime.now(UTC).date()
    journal = {
        "word_schedule": {
            "mit": {
                "preposition_meaning": {
                    "interval_days": 0,
                    "due_date": today.isoformat(),
                },
            },
        }
    }

    assert Tutor(Course([exercise]), journal).progress().new_today == 0


def test_progress_new_today_excludes_a_word_already_introduced_earlier() -> None:
    # sprechen's government was introduced 3 days ago; today its
    # partizip_ii gets its first answer too. The word itself started 3
    # days ago, so today's tally shouldn't count it again.
    government = make_exercise(word="sprechen", topic="government", answer="auf")
    partizip = make_exercise(word="sprechen", topic="partizip_ii", answer="gesprochen")
    today = datetime.now(UTC).date()
    journal = {
        "word_schedule": {
            "sprechen": {
                "government": {
                    "interval_days": 4,
                    "due_date": today.isoformat(),
                    "introduced_at": (today - timedelta(days=3)).isoformat(),
                },
            },
        }
    }
    tutor = Tutor(Course([government, partizip]), journal)

    tutor.check_answer(partizip, "gesprochen")

    assert tutor.progress().new_today == 0
