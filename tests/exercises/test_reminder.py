from datetime import UTC, date, datetime, timedelta

from wiederholen.exercises import Course, Tutor

from tests.plugins.exercises import make_exercise


def test_due_topics_count_is_zero_for_empty_school() -> None:
    assert Tutor(Course([]), {}).due_topics_count() == 0


def test_due_topics_count_counts_new_topics_as_due() -> None:
    exercises = [make_exercise(topic="warten"), make_exercise(topic="hoffen")]

    assert Tutor(Course(exercises), {}).due_topics_count() == 2


def test_due_topics_count_excludes_not_yet_due_topics() -> None:
    exercise = make_exercise(topic="warten")
    journal = {
        "topic_schedule": {
            "warten:government": {
                "interval_days": 30,
                "due_date": (date.today() + timedelta(days=20)).isoformat(),
            },
        }
    }

    assert Tutor(Course([exercise]), journal).due_topics_count() == 0


def test_due_topics_count_counts_shared_schedule_key_once() -> None:
    # Two YAML entries for the same topic+category share one schedule key.
    duplicate_1 = make_exercise(topic="helfen")
    duplicate_2 = make_exercise(topic="helfen")

    assert Tutor(Course([duplicate_1, duplicate_2]), {}).due_topics_count() == 1


def test_record_reminder_sent_sets_last_reminded_at() -> None:
    exercise = make_exercise()
    journal: dict = {}
    before = datetime.now(UTC)

    Tutor(Course([exercise]), journal).record_reminder_sent()

    recorded = datetime.fromisoformat(journal["last_reminded_at"])
    assert before <= recorded <= datetime.now(UTC)


def test_should_remind_is_false_when_nothing_is_due() -> None:
    exercise = make_exercise(topic="warten")
    journal = {
        "topic_schedule": {
            "warten:government": {
                "interval_days": 30,
                "due_date": (date.today() + timedelta(days=20)).isoformat(),
            },
        },
        "last_answered_at": (datetime.now(UTC) - timedelta(hours=25)).isoformat(),
    }

    assert Tutor(Course([exercise]), journal).should_remind() is False


def test_should_remind_is_false_without_ever_answering() -> None:
    exercise = make_exercise()
    journal: dict = {}

    assert Tutor(Course([exercise]), journal).should_remind() is False


def test_should_remind_is_false_when_answered_recently() -> None:
    exercise = make_exercise()
    journal = {
        "last_answered_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
    }

    assert Tutor(Course([exercise]), journal).should_remind() is False


def test_should_remind_is_true_after_24h_since_last_answer_with_due_material() -> None:
    exercise = make_exercise()
    journal = {
        "last_answered_at": (datetime.now(UTC) - timedelta(hours=25)).isoformat(),
    }

    assert Tutor(Course([exercise]), journal).should_remind() is True


def test_should_remind_is_false_if_already_reminded_since_last_answer() -> None:
    exercise = make_exercise()
    last_answered_at = datetime.now(UTC) - timedelta(hours=25)
    journal = {
        "last_answered_at": last_answered_at.isoformat(),
        "last_reminded_at": (last_answered_at + timedelta(minutes=1)).isoformat(),
    }

    assert Tutor(Course([exercise]), journal).should_remind() is False


def test_should_remind_is_true_if_answered_again_since_last_reminder() -> None:
    exercise = make_exercise()
    last_reminded_at = datetime.now(UTC) - timedelta(days=2)
    last_answered_at = datetime.now(UTC) - timedelta(hours=25)
    journal = {
        "last_answered_at": last_answered_at.isoformat(),
        "last_reminded_at": last_reminded_at.isoformat(),
    }

    assert Tutor(Course([exercise]), journal).should_remind() is True
