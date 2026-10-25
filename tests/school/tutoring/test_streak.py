from datetime import UTC, datetime, timedelta
from typing import Any

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Tracer

from tests.plugins.curriculum import make_exercise
from wiederholen.school.curriculum import Course
from wiederholen.school.tutoring import StudentRecord, Tutor


def _record(*, started_ago: timedelta | None, answered_ago: timedelta) -> dict:
    now = datetime.now(UTC)
    student_record: dict = {
        "last_exercise": {
            "question": "Ich ___ hoffen.",
            "answered_at": (now - answered_ago).isoformat(),
            "is_recall_optional": False,
        },
    }
    if started_ago is not None:
        student_record["streak_started_at"] = (now - started_ago).isoformat()
    return student_record


def _streak_events(span: ReadableSpan) -> list[tuple[str, dict[str, Any]]]:
    return [
        (event.name, dict(event.attributes or {}))
        for event in span.events
        if event.name.startswith("Streak")
    ]


def test_there_is_no_streak_before_the_first_answer() -> None:
    assert Tutor(Course([make_exercise()]), {}).streak() is None


def test_the_first_answer_starts_a_one_day_streak() -> None:
    exercise = make_exercise()
    student_record: dict = {}
    tutor = Tutor(Course([exercise]), student_record)

    tutor.check_answer(exercise, exercise.answer)

    streak = tutor.streak()
    assert streak is not None
    assert streak.days == 1
    assert (
        student_record["streak_started_at"]
        == student_record["last_exercise"]["answered_at"]
    )


def test_a_wrong_answer_also_counts_as_practice() -> None:
    exercise = make_exercise()
    tutor = Tutor(Course([exercise]), {})

    tutor.check_answer(exercise, "nonsense")

    streak = tutor.streak()
    assert streak is not None
    assert streak.days == 1


def test_answers_within_the_first_24_hours_keep_one_day() -> None:
    exercise = make_exercise()
    student_record = _record(
        started_ago=timedelta(hours=20), answered_ago=timedelta(hours=2)
    )
    tutor = Tutor(Course([exercise]), student_record)

    tutor.check_answer(exercise, exercise.answer)

    streak = tutor.streak()
    assert streak is not None
    assert streak.days == 1


def test_an_answer_on_the_next_day_extends_the_streak() -> None:
    exercise = make_exercise()
    student_record = _record(
        started_ago=timedelta(hours=30), answered_ago=timedelta(hours=10)
    )
    tutor = Tutor(Course([exercise]), student_record)

    tutor.check_answer(exercise, exercise.answer)

    streak = tutor.streak()
    assert streak is not None
    assert streak.days == 2


def test_a_gap_of_almost_36_hours_keeps_the_streak() -> None:
    exercise = make_exercise()
    student_record = _record(
        started_ago=timedelta(days=4), answered_ago=timedelta(hours=35)
    )
    tutor = Tutor(Course([exercise]), student_record)

    tutor.check_answer(exercise, exercise.answer)

    streak = tutor.streak()
    assert streak is not None
    assert streak.days == 5


def test_a_gap_over_36_hours_starts_a_new_streak() -> None:
    exercise = make_exercise()
    student_record = _record(
        started_ago=timedelta(days=10), answered_ago=timedelta(hours=37)
    )
    tutor = Tutor(Course([exercise]), student_record)

    tutor.check_answer(exercise, exercise.answer)

    streak = tutor.streak()
    assert streak is not None
    assert streak.days == 1
    assert (
        student_record["streak_started_at"]
        == student_record["last_exercise"]["answered_at"]
    )


def test_the_streak_counts_to_the_last_answer_not_to_now() -> None:
    student_record = _record(
        started_ago=timedelta(hours=40), answered_ago=timedelta(hours=30)
    )

    streak = Tutor(Course([make_exercise()]), student_record).streak()

    assert streak is not None
    assert streak.days == 1


def test_the_streak_breaks_36_hours_after_the_last_answer() -> None:
    student_record = _record(
        started_ago=timedelta(days=3), answered_ago=timedelta(hours=10)
    )

    streak = Tutor(Course([make_exercise()]), student_record).streak()

    assert streak is not None
    answered_at = datetime.fromisoformat(student_record["last_exercise"]["answered_at"])
    assert streak.breaks_at == answered_at + Tutor.STREAK_BREAKS_AFTER


def test_there_is_no_streak_after_36_hours_without_answers() -> None:
    student_record = _record(
        started_ago=timedelta(days=3), answered_ago=timedelta(hours=37)
    )

    assert Tutor(Course([make_exercise()]), student_record).streak() is None


def test_a_record_from_before_streaks_has_no_streak_until_the_next_answer() -> None:
    exercise = make_exercise()
    student_record = _record(started_ago=None, answered_ago=timedelta(hours=2))
    tutor = Tutor(Course([exercise]), student_record)

    assert tutor.streak() is None

    tutor.check_answer(exercise, exercise.answer)

    streak = tutor.streak()
    assert streak is not None
    assert streak.days == 1


def test_reset_progress_keeps_the_streak() -> None:
    student_record = _record(
        started_ago=timedelta(days=3), answered_ago=timedelta(hours=10)
    )
    started_at = student_record["streak_started_at"]

    StudentRecord.reset_progress(student_record)

    assert student_record["streak_started_at"] == started_at


class TestEvents:
    def test_the_first_answer_reports_a_one_day_streak(
        self, tracer: Tracer, exporter: InMemorySpanExporter
    ) -> None:
        exercise = make_exercise()

        with tracer.start_as_current_span("test-span"):
            Tutor(Course([exercise]), {}).check_answer(exercise, exercise.answer)

        span = exporter.get_finished_spans()[0]
        assert _streak_events(span) == [("StreakExtended", {"days": 1})]

    def test_an_answer_on_the_same_day_reports_nothing(
        self, tracer: Tracer, exporter: InMemorySpanExporter
    ) -> None:
        exercise = make_exercise()
        student_record = _record(
            started_ago=timedelta(hours=20), answered_ago=timedelta(hours=2)
        )

        with tracer.start_as_current_span("test-span"):
            Tutor(Course([exercise]), student_record).check_answer(
                exercise, exercise.answer
            )

        span = exporter.get_finished_spans()[0]
        assert _streak_events(span) == []

    def test_an_answer_on_the_next_day_reports_the_new_length(
        self, tracer: Tracer, exporter: InMemorySpanExporter
    ) -> None:
        exercise = make_exercise()
        student_record = _record(
            started_ago=timedelta(hours=30), answered_ago=timedelta(hours=10)
        )

        with tracer.start_as_current_span("test-span"):
            Tutor(Course([exercise]), student_record).check_answer(
                exercise, exercise.answer
            )

        span = exporter.get_finished_spans()[0]
        assert _streak_events(span) == [("StreakExtended", {"days": 2})]

    def test_an_answer_after_a_break_reports_the_lost_streak(
        self, tracer: Tracer, exporter: InMemorySpanExporter
    ) -> None:
        exercise = make_exercise()
        student_record = _record(
            started_ago=timedelta(days=5) + timedelta(hours=37),
            answered_ago=timedelta(hours=37),
        )

        with tracer.start_as_current_span("test-span"):
            Tutor(Course([exercise]), student_record).check_answer(
                exercise, exercise.answer
            )

        span = exporter.get_finished_spans()[0]
        assert _streak_events(span) == [
            ("StreakBroken", {"days": 6}),
            ("StreakExtended", {"days": 1}),
        ]

    def test_a_record_from_before_streaks_reports_no_break(
        self, tracer: Tracer, exporter: InMemorySpanExporter
    ) -> None:
        exercise = make_exercise()
        student_record = _record(started_ago=None, answered_ago=timedelta(hours=40))

        with tracer.start_as_current_span("test-span"):
            Tutor(Course([exercise]), student_record).check_answer(
                exercise, exercise.answer
            )

        span = exporter.get_finished_spans()[0]
        assert _streak_events(span) == [("StreakExtended", {"days": 1})]
