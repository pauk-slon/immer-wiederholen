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


def test_progress_remaining_today_counts_available_new_pairs() -> None:
    exercises = [make_exercise(word="warten"), make_exercise(word="hoffen")]

    assert Tutor(Course(exercises), {}).progress().remaining_today == 2


def test_progress_remaining_today_is_capped_by_the_daily_new_word_limit() -> None:
    today = datetime.now(UTC).date()
    capped_exercises = [
        make_exercise(word=f"introduced{i}") for i in range(Tutor.NEW_WORDS_PER_DAY)
    ]
    exercises = [*capped_exercises, make_exercise(word="warten")]
    word_schedule = {
        f"introduced{i}": {
            "government": {
                "interval_days": 1,
                "due_date": (today + timedelta(days=30)).isoformat(),
                "introduced_at": today.isoformat(),
            },
        }
        for i in range(Tutor.NEW_WORDS_PER_DAY)
    }
    journal = {"word_schedule": word_schedule}

    assert Tutor(Course(exercises), journal).progress().remaining_today == 0


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
