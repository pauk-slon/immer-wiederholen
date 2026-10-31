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


def test_should_remind_honors_a_shorter_remind_after() -> None:
    exercise = make_exercise()
    student_record = {
        "last_exercise": {
            "answered_at": (datetime.now(UTC) - timedelta(hours=5)).isoformat(),
        },
    }

    tutor = Tutor(Course([exercise]), student_record)

    assert tutor.should_remind(timedelta(hours=4)) is True
    assert tutor.should_remind(timedelta(hours=8)) is False


def _reminded_record(
    answered_hours_ago: int, reminded_hours_ago: int, *, streak: bool = True
) -> dict:
    now = datetime.now(UTC)
    answered_at = (now - timedelta(hours=answered_hours_ago)).isoformat()
    student_record: dict = {
        "last_exercise": {"answered_at": answered_at},
        "last_reminded_at": (now - timedelta(hours=reminded_hours_ago)).isoformat(),
    }
    if streak:
        student_record["streak"] = {"days": 5, "counted_at": answered_at}
    return student_record


def test_should_remind_again_after_24h_when_the_streak_is_alive() -> None:
    student_record = _reminded_record(answered_hours_ago=25, reminded_hours_ago=21)

    tutor = Tutor(Course([make_exercise()]), student_record)

    assert tutor.should_remind(timedelta(hours=4)) is True


def test_should_not_remind_again_before_24h() -> None:
    student_record = _reminded_record(answered_hours_ago=23, reminded_hours_ago=19)

    tutor = Tutor(Course([make_exercise()]), student_record)

    assert tutor.should_remind(timedelta(hours=4)) is False


def test_should_not_remind_a_third_time() -> None:
    student_record = _reminded_record(answered_hours_ago=30, reminded_hours_ago=5)

    tutor = Tutor(Course([make_exercise()]), student_record)

    assert tutor.should_remind(timedelta(hours=4)) is False


def test_should_not_remind_again_without_a_streak() -> None:
    student_record = _reminded_record(
        answered_hours_ago=25, reminded_hours_ago=21, streak=False
    )

    tutor = Tutor(Course([make_exercise()]), student_record)

    assert tutor.should_remind(timedelta(hours=4)) is False


def test_should_not_remind_again_after_the_streak_broke() -> None:
    student_record = _reminded_record(answered_hours_ago=37, reminded_hours_ago=33)

    tutor = Tutor(Course([make_exercise()]), student_record)

    assert tutor.should_remind(timedelta(hours=4)) is False
