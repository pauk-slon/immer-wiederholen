import dataclasses
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Tracer

from tests.plugins.curriculum import make_exercise
from wiederholen.school.curriculum import Course, Exercise
from wiederholen.school.tutoring import FinishedLesson, LessonProgress, Tutor
from wiederholen.school.tutoring.lesson import Lesson


def _next(tutor: Tutor) -> Exercise:
    exercise = tutor.next_exercise()
    assert exercise is not None
    return exercise


def _lesson_events(span: ReadableSpan) -> list[tuple[str, dict[str, Any]]]:
    return [
        (event.name, dict(event.attributes or {}))
        for event in span.events
        if event.name.startswith("Lesson")
    ]


def _started_lesson(*exercises: Exercise) -> dict:
    lesson: dict = {}
    Lesson(lesson, today=datetime.now(UTC).date()).start(
        [exercise.content_key for exercise in exercises]
    )
    return lesson


def test_a_lesson_gives_its_exercises_over_several_requests(
    tracer: Tracer,
    exporter: InMemorySpanExporter,
) -> None:
    course = Course(
        [make_exercise(word=word) for word in ("warten", "hoffen", "denken")]
    )
    student_record: dict = {}
    lesson: dict = {}

    with tracer.start_as_current_span("test-span"):
        shown = [
            _next(Tutor(course, student_record, lesson=lesson, lesson_size=3))
            for _ in range(3)
        ]

    assert {exercise.word for exercise in shown} == {"warten", "hoffen", "denken"}
    span = exporter.get_finished_spans()[0]
    assert _lesson_events(span) == [("LessonStarted", {"size": 3})]


def test_by_default_every_request_starts_a_lesson_of_one_exercise(
    tracer: Tracer,
    exporter: InMemorySpanExporter,
) -> None:
    course = Course([make_exercise(word="warten"), make_exercise(word="hoffen")])
    student_record: dict = {}
    lesson: dict = {}

    with tracer.start_as_current_span("test-span"):
        for _ in range(2):
            _next(Tutor(course, student_record, lesson=lesson))

    span = exporter.get_finished_spans()[0]
    assert _lesson_events(span) == [
        ("LessonStarted", {"size": 1}),
        ("LessonStarted", {"size": 1}),
    ]


def test_a_lesson_takes_each_pair_once() -> None:
    course = Course(
        [
            make_exercise(word="warten", topic="government"),
            make_exercise(word="warten", topic="partizip_ii"),
        ]
    )
    lesson: dict = {}

    first = _next(Tutor(course, {}, lesson=lesson, lesson_size=5))
    second = _next(Tutor(course, {}, lesson=lesson, lesson_size=5))

    assert lesson["size"] == 2
    assert {first.topic, second.topic} == {"government", "partizip_ii"}


def test_a_lesson_puts_another_word_between_two_exercises_of_one_word() -> None:
    # Two pairs of warten and one of hoffen. A lesson that starts with
    # warten must put hoffen second. Only a lesson that starts with hoffen
    # has warten twice in a row, because nothing else is left
    course = Course(
        [
            make_exercise(word="warten", topic="government"),
            make_exercise(word="warten", topic="partizip_ii"),
            make_exercise(word="hoffen"),
        ]
    )

    for _ in range(50):
        lesson: dict = {}
        words = [
            _next(Tutor(course, {}, lesson=lesson, lesson_size=3)).word
            for _ in range(3)
        ]
        assert words[:2] != ["warten", "warten"]


def test_new_words_of_a_lesson_use_the_daily_limit() -> None:
    course = Course(
        [make_exercise(word=f"word{i}") for i in range(Tutor.NEW_WORDS_PER_DAY + 3)]
    )
    lesson: dict = {}

    _next(Tutor(course, {}, lesson=lesson, lesson_size=len(course.exercises)))

    assert lesson["size"] == Tutor.NEW_WORDS_PER_DAY


def test_a_lesson_from_an_earlier_day_is_replaced() -> None:
    warten = make_exercise(word="warten")
    hoffen = make_exercise(word="hoffen")
    today = datetime.now(UTC).date()
    student_record = {
        "word_schedule": {
            "hoffen": {
                "government": {
                    "repetition_interval": 4,
                    "due_date": (today + timedelta(days=3)).isoformat(),
                    "introduced_at": (today - timedelta(days=5)).isoformat(),
                },
            },
        }
    }
    lesson = _started_lesson(hoffen)
    lesson["date"] = (today - timedelta(days=1)).isoformat()

    exercise = _next(Tutor(Course([warten, hoffen]), student_record, lesson=lesson))

    assert exercise == warten
    assert lesson["date"] == today.isoformat()


def test_a_lesson_skips_an_exercise_that_the_course_no_longer_has() -> None:
    warten = make_exercise(word="warten", answer="auf")
    edited_warten = dataclasses.replace(warten, explanation={"ru": "new", "en": "new"})
    hoffen = make_exercise(word="hoffen")
    lesson = _started_lesson(warten, hoffen)

    exercise = _next(Tutor(Course([edited_warten, hoffen]), {}, lesson=lesson))

    assert exercise == hoffen


def test_a_lesson_skips_exercises_outside_the_selected_topics() -> None:
    government = make_exercise(word="warten", topic="government")
    partizip = make_exercise(word="warten", topic="partizip_ii")
    lesson = _started_lesson(government, partizip)
    course = Course([government, partizip]).restricted_to(["partizip_ii"])

    exercise = _next(Tutor(course, {}, lesson=lesson))

    assert exercise == partizip


def test_the_answer_to_the_last_exercise_finishes_the_lesson_once(
    tracer: Tracer,
    exporter: InMemorySpanExporter,
) -> None:
    course = Course([make_exercise(word="warten"), make_exercise(word="hoffen")])
    student_record: dict = {}
    lesson: dict = {}

    def tutor() -> Tutor:
        return Tutor(course, student_record, lesson=lesson, lesson_size=2)

    with tracer.start_as_current_span("first-exercise"):
        first = _next(tutor())
        tutor().check_answer(first, first.answer[0])
    with tracer.start_as_current_span("last-exercise"):
        last = _next(tutor())
        tutor().check_answer(last, last.answer[0])
    with tracer.start_as_current_span("same-answer-again"):
        tutor().check_answer(last, last.answer[0])

    first_span, last_span, again_span = exporter.get_finished_spans()
    assert _lesson_events(first_span) == [("LessonStarted", {"size": 2})]
    assert _lesson_events(last_span) == [("LessonFinished", {"size": 2, "correct": 2})]
    assert _lesson_events(again_span) == []


def test_the_answer_to_the_last_exercise_of_an_earlier_days_lesson_finishes_it(
    tracer: Tracer,
    exporter: InMemorySpanExporter,
) -> None:
    exercise = make_exercise()
    lesson: dict = {}
    _next(Tutor(Course([exercise]), {}, lesson=lesson))
    lesson["date"] = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()

    with tracer.start_as_current_span("test-span"):
        Tutor(Course([exercise]), {}, lesson=lesson).check_answer(
            exercise, exercise.answer[0]
        )

    span = exporter.get_finished_spans()[0]
    assert _lesson_events(span) == [("LessonFinished", {"size": 1, "correct": 1})]


def test_an_answer_without_a_lesson_finishes_nothing(
    tracer: Tracer,
    exporter: InMemorySpanExporter,
) -> None:
    exercise = make_exercise()

    with tracer.start_as_current_span("test-span"):
        Tutor(Course([exercise]), {}).check_answer(exercise, exercise.answer[0])

    assert _lesson_events(exporter.get_finished_spans()[0]) == []


def test_a_malformed_lesson_counts_as_empty() -> None:
    today = datetime.now(UTC).date()
    lesson = Lesson(
        {"date": today.isoformat(), "size": "five", "exercise_keys": "not a list"},
        today=today,
    )

    assert lesson.size == 0
    assert lesson.take_exercise_key() is None


def test_content_key_tells_apart_exercises_with_the_same_question() -> None:
    with_bruder = make_exercise(word="für", answer="meinen Bruder")
    with_mutter = make_exercise(word="für", answer="meine Mutter")

    assert with_bruder.question == with_mutter.question
    assert with_bruder.content_key != with_mutter.content_key
    assert (
        with_bruder.content_key
        == make_exercise(word="für", answer="meinen Bruder").content_key
    )


def test_a_lesson_size_below_one_is_rejected() -> None:
    with pytest.raises(ValueError, match="lesson_size"):
        Tutor(Course([make_exercise()]), {}, lesson_size=0)


def test_a_finished_lesson_reports_its_correct_answers_and_the_streak_day() -> None:
    course = Course(
        [
            make_exercise(word="warten", answer="auf"),
            make_exercise(word="hoffen", answer="auf"),
        ]
    )
    student_record: dict = {}
    lesson: dict = {}
    marks = []
    for answer in ("auf", "nonsense"):
        tutor = Tutor(course, student_record, lesson=lesson, lesson_size=2)
        marks.append(tutor.check_answer(_next(tutor), answer))

    assert marks[0].finished_lesson is None
    assert marks[1].finished_lesson == FinishedLesson(
        size=2, correct=1, extends_streak=True
    )


def test_a_lesson_on_the_same_day_as_the_last_one_adds_no_streak_day() -> None:
    course = Course([make_exercise(word="warten"), make_exercise(word="hoffen")])
    student_record: dict = {}
    lesson: dict = {}
    marks = []
    for _ in range(2):
        tutor = Tutor(course, student_record, lesson=lesson)
        exercise = _next(tutor)
        marks.append(tutor.check_answer(exercise, exercise.answer[0]))

    assert marks[1].finished_lesson == FinishedLesson(
        size=1, correct=1, extends_streak=False
    )


def test_lesson_progress_is_the_position_of_the_shown_exercise() -> None:
    course = Course([make_exercise(word=word) for word in ("warten", "hoffen")])
    lesson: dict = {}
    tutor = Tutor(course, {}, lesson=lesson, lesson_size=2)

    assert tutor.lesson_progress() is None
    _next(tutor)
    assert tutor.lesson_progress() == LessonProgress(position=1, size=2)
    _next(tutor)
    assert tutor.lesson_progress() == LessonProgress(position=2, size=2)
