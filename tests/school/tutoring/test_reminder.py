from datetime import UTC, datetime, timedelta

from tests.plugins.curriculum import make_exercise
from wiederholen.school.curriculum import Course
from wiederholen.school.tutoring import Tutor


def test_record_reminder_sent_sets_last_reminded_at() -> None:
    exercise = make_exercise()
    student_record: dict = {}
    before = datetime.now(UTC)

    Tutor(Course([exercise]), student_record).record_reminder_sent()

    recorded = datetime.fromisoformat(student_record["last_reminded_at"])
    assert before <= recorded <= datetime.now(UTC)


def test_should_remind_is_false_when_nothing_is_due() -> None:
    exercise = make_exercise(word="warten")
    student_record = {
        "word_schedule": {
            "warten": {
                "government": {
                    "repetition_interval": 30,
                    "due_date": (
                        datetime.now(UTC).date() + timedelta(days=20)
                    ).isoformat(),
                },
            },
        },
        "last_exercise": {
            "answered_at": (datetime.now(UTC) - timedelta(hours=25)).isoformat(),
        },
    }

    assert Tutor(Course([exercise]), student_record).should_remind() is False


def test_should_remind_is_false_without_ever_answering() -> None:
    exercise = make_exercise()
    student_record: dict = {}

    assert Tutor(Course([exercise]), student_record).should_remind() is False


def test_should_remind_is_false_when_answered_recently() -> None:
    exercise = make_exercise()
    student_record = {
        "last_exercise": {
            "answered_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
        },
    }

    assert Tutor(Course([exercise]), student_record).should_remind() is False


def test_should_remind_is_true_after_24h_since_last_answer_with_due_material() -> None:
    exercise = make_exercise()
    student_record = {
        "last_exercise": {
            "answered_at": (datetime.now(UTC) - timedelta(hours=25)).isoformat(),
        },
    }

    assert Tutor(Course([exercise]), student_record).should_remind() is True


def test_should_remind_is_true_for_an_overdue_review_with_no_new_pairs_available() -> (
    None
):
    # A word already introduced, with a genuinely overdue review, and
    # nothing else in the course (so _get_available_not_scheduled_pairs()
    # is empty) — the reminder must still fire off the due review alone.
    exercise = make_exercise(word="warten")
    today = datetime.now(UTC).date()
    student_record = {
        "word_schedule": {
            "warten": {
                "government": {
                    "repetition_interval": 4,
                    "due_date": (today - timedelta(days=1)).isoformat(),
                    "introduced_at": (today - timedelta(days=10)).isoformat(),
                },
            },
        },
        "last_exercise": {
            "answered_at": (datetime.now(UTC) - timedelta(hours=25)).isoformat(),
        },
    }

    assert Tutor(Course([exercise]), student_record).should_remind() is True


def test_should_remind_is_false_if_already_reminded_since_last_answer() -> None:
    exercise = make_exercise()
    last_answered_at = datetime.now(UTC) - timedelta(hours=25)
    student_record = {
        "last_exercise": {"answered_at": last_answered_at.isoformat()},
        "last_reminded_at": (last_answered_at + timedelta(minutes=1)).isoformat(),
    }

    assert Tutor(Course([exercise]), student_record).should_remind() is False


def test_should_remind_is_true_if_answered_again_since_last_reminder() -> None:
    exercise = make_exercise()
    last_reminded_at = datetime.now(UTC) - timedelta(days=2)
    last_answered_at = datetime.now(UTC) - timedelta(hours=25)
    student_record = {
        "last_exercise": {"answered_at": last_answered_at.isoformat()},
        "last_reminded_at": last_reminded_at.isoformat(),
    }

    assert Tutor(Course([exercise]), student_record).should_remind() is True
