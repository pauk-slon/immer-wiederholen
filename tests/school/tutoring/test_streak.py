from datetime import UTC, datetime, timedelta
from typing import Any

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Tracer

from tests.plugins.curriculum import make_exercise
from wiederholen.school.curriculum import Course
from wiederholen.school.tutoring import StudentRecord, Tutor


def _record(
    *,
    answered_ago: timedelta,
    days: int | None = None,
    counted_ago: timedelta | None = None,
) -> dict:
    now = datetime.now(UTC)
    student_record: dict = {
        "last_exercise": {
            "question": "Ich ___ hoffen.",
            "answered_at": (now - answered_ago).isoformat(),
            "is_recall_optional": False,
        },
    }
    if days is not None:
        student_record["streak"] = {
            "days": days,
            "counted_at": (now - (counted_ago or answered_ago)).isoformat(),
        }
    return student_record


def _answer(student_record: dict) -> Tutor:
    exercise = make_exercise()
    tutor = Tutor(Course([exercise]), student_record)
    tutor.check_answer(exercise, exercise.answer[0])
    return tutor


def _days_after_answer(student_record: dict) -> int:
    streak = _answer(student_record).streak()
    assert streak is not None
    return streak.days


def _streak_events(span: ReadableSpan) -> list[tuple[str, dict[str, Any]]]:
    return [
        (event.name, dict(event.attributes or {}))
        for event in span.events
        if event.name.startswith("Streak")
    ]


def test_there_is_no_streak_before_the_first_answer() -> None:
    assert Tutor(Course([make_exercise()]), {}).streak() is None


def test_the_first_answer_starts_a_one_day_streak() -> None:
    student_record: dict = {}

    assert _days_after_answer(student_record) == 1
    assert (
        student_record["streak"]["counted_at"]
        == student_record["last_exercise"]["answered_at"]
    )


def test_a_wrong_answer_also_counts_as_practice() -> None:
    exercise = make_exercise()
    tutor = Tutor(Course([exercise]), {})

    tutor.check_answer(exercise, "nonsense")

    streak = tutor.streak()
    assert streak is not None
    assert streak.days == 1


def test_a_second_session_on_the_same_day_adds_no_day() -> None:
    # 8:00 and 20:00
    student_record = _record(answered_ago=timedelta(hours=12), days=3)

    assert _days_after_answer(student_record) == 3


def test_an_answer_18_hours_after_the_counted_one_adds_a_day() -> None:
    student_record = _record(answered_ago=timedelta(hours=18), days=3)

    assert _days_after_answer(student_record) == 4


def test_a_day_counts_from_the_counted_answer_not_from_the_last_one() -> None:
    # 8:00 counted, 20:00 not counted, 8:00 the next day
    student_record = _record(
        answered_ago=timedelta(hours=12), days=3, counted_ago=timedelta(hours=24)
    )

    assert _days_after_answer(student_record) == 4


def test_the_counted_answer_moves_only_when_a_day_is_added() -> None:
    student_record = _record(
        answered_ago=timedelta(hours=2), days=3, counted_ago=timedelta(hours=10)
    )
    counted_at = student_record["streak"]["counted_at"]

    _answer(student_record)

    assert student_record["streak"]["counted_at"] == counted_at


def test_an_evening_then_a_morning_session_adds_no_day() -> None:
    # 20:00, then 9:00 the next day. Without the learner's time zone this
    # looks the same as 9:00 and 22:00 on one day (see ADR 0021)
    student_record = _record(answered_ago=timedelta(hours=13), days=3)

    assert _days_after_answer(student_record) == 3


def test_a_gap_just_under_36_hours_keeps_the_streak() -> None:
    student_record = _record(answered_ago=timedelta(hours=35, minutes=59), days=3)

    assert _days_after_answer(student_record) == 4


def test_a_gap_just_over_36_hours_starts_a_new_streak() -> None:
    student_record = _record(answered_ago=timedelta(hours=36, minutes=1), days=10)

    assert _days_after_answer(student_record) == 1


def test_the_streak_breaks_36_hours_after_the_last_answer() -> None:
    student_record = _record(answered_ago=timedelta(hours=10), days=3)

    streak = Tutor(Course([make_exercise()]), student_record).streak()

    assert streak is not None
    assert streak.days == 3
    answered_at = datetime.fromisoformat(student_record["last_exercise"]["answered_at"])
    assert streak.breaks_at == answered_at + Tutor.STREAK_BREAKS_AFTER


def test_there_is_no_streak_after_36_hours_without_answers() -> None:
    student_record = _record(answered_ago=timedelta(hours=36, minutes=1), days=3)

    assert Tutor(Course([make_exercise()]), student_record).streak() is None


def test_a_record_from_before_streaks_has_no_streak_until_the_next_answer() -> None:
    student_record = _record(answered_ago=timedelta(hours=2))

    assert Tutor(Course([make_exercise()]), student_record).streak() is None
    assert _days_after_answer(student_record) == 1


def test_reset_progress_keeps_the_streak() -> None:
    student_record = _record(answered_ago=timedelta(hours=10), days=3)
    streak = student_record["streak"]

    StudentRecord.reset_progress(student_record)

    assert student_record["streak"] == streak


class TestEvents:
    def _streak_events_after_answer(
        self, tracer: Tracer, exporter: InMemorySpanExporter, student_record: dict
    ) -> list[tuple[str, dict[str, Any]]]:
        with tracer.start_as_current_span("test-span"):
            _answer(student_record)
        return _streak_events(exporter.get_finished_spans()[0])

    def test_the_first_answer_reports_a_one_day_streak(
        self, tracer: Tracer, exporter: InMemorySpanExporter
    ) -> None:
        assert self._streak_events_after_answer(tracer, exporter, {}) == [
            ("StreakExtended", {"days": 1})
        ]

    def test_an_answer_on_the_same_day_reports_nothing(
        self, tracer: Tracer, exporter: InMemorySpanExporter
    ) -> None:
        student_record = _record(answered_ago=timedelta(hours=2), days=3)

        assert self._streak_events_after_answer(tracer, exporter, student_record) == []

    def test_an_answer_on_the_next_day_reports_the_new_length(
        self, tracer: Tracer, exporter: InMemorySpanExporter
    ) -> None:
        student_record = _record(answered_ago=timedelta(hours=20), days=3)

        assert self._streak_events_after_answer(tracer, exporter, student_record) == [
            ("StreakExtended", {"days": 4})
        ]

    def test_an_answer_after_a_break_reports_the_lost_streak(
        self, tracer: Tracer, exporter: InMemorySpanExporter
    ) -> None:
        student_record = _record(answered_ago=timedelta(hours=37), days=6)

        assert self._streak_events_after_answer(tracer, exporter, student_record) == [
            ("StreakBroken", {"days": 6}),
            ("StreakExtended", {"days": 1}),
        ]

    def test_a_record_from_before_streaks_reports_no_break(
        self, tracer: Tracer, exporter: InMemorySpanExporter
    ) -> None:
        student_record = _record(answered_ago=timedelta(hours=40))

        assert self._streak_events_after_answer(tracer, exporter, student_record) == [
            ("StreakExtended", {"days": 1})
        ]
