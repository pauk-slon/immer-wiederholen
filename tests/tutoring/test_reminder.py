from datetime import UTC, datetime, timedelta

from tests.plugins.tutoring import make_exercise
from wiederholen.tutoring import Course, Tutor


def test_record_reminder_sent_sets_last_reminded_at() -> None:
    exercise = make_exercise()
    journal: dict = {}
    before = datetime.now(UTC)

    Tutor(Course([exercise]), journal).record_reminder_sent()

    recorded = datetime.fromisoformat(journal["last_reminded_at"])
    assert before <= recorded <= datetime.now(UTC)


def test_should_remind_is_false_when_nothing_is_due() -> None:
    exercise = make_exercise(word="warten")
    journal = {
        "word_schedule": {
            "warten": {
                "government": {
                    "interval_days": 30,
                    "due_date": (datetime.now(UTC).date() + timedelta(days=20)).isoformat(),
                },
            },
        },
        "last_exercise": {
            "answered_at": (datetime.now(UTC) - timedelta(hours=25)).isoformat(),
        },
    }

    assert Tutor(Course([exercise]), journal).should_remind() is False


def test_should_remind_is_false_without_ever_answering() -> None:
    exercise = make_exercise()
    journal: dict = {}

    assert Tutor(Course([exercise]), journal).should_remind() is False


def test_should_remind_is_false_when_answered_recently() -> None:
    exercise = make_exercise()
    journal = {
        "last_exercise": {
            "answered_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
        },
    }

    assert Tutor(Course([exercise]), journal).should_remind() is False


def test_should_remind_is_true_after_24h_since_last_answer_with_due_material() -> None:
    exercise = make_exercise()
    journal = {
        "last_exercise": {
            "answered_at": (datetime.now(UTC) - timedelta(hours=25)).isoformat(),
        },
    }

    assert Tutor(Course([exercise]), journal).should_remind() is True


def test_should_remind_is_false_if_already_reminded_since_last_answer() -> None:
    exercise = make_exercise()
    last_answered_at = datetime.now(UTC) - timedelta(hours=25)
    journal = {
        "last_exercise": {"answered_at": last_answered_at.isoformat()},
        "last_reminded_at": (last_answered_at + timedelta(minutes=1)).isoformat(),
    }

    assert Tutor(Course([exercise]), journal).should_remind() is False


def test_should_remind_is_true_if_answered_again_since_last_reminder() -> None:
    exercise = make_exercise()
    last_reminded_at = datetime.now(UTC) - timedelta(days=2)
    last_answered_at = datetime.now(UTC) - timedelta(hours=25)
    journal = {
        "last_exercise": {"answered_at": last_answered_at.isoformat()},
        "last_reminded_at": last_reminded_at.isoformat(),
    }

    assert Tutor(Course([exercise]), journal).should_remind() is True
