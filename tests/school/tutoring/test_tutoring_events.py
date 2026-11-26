from datetime import UTC, datetime, timedelta
from typing import Any

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Tracer

from tests.plugins.curriculum import make_exercise
from wiederholen.school.curriculum import Course, Pair
from wiederholen.school.tutoring import Tutor


def _events(span: ReadableSpan) -> list[tuple[str, dict[str, Any]]]:
    return [(event.name, dict(event.attributes or {})) for event in span.events]


def test_answering_a_brand_new_pair_reports_is_new_and_no_previous_interval(
    tracer: Tracer,
    exporter: InMemorySpanExporter,
) -> None:
    exercise = make_exercise(word="warten", answer="auf")

    with tracer.start_as_current_span("test-span"):
        Tutor(Course([exercise]), {}).check_answer(exercise, "auf")

    span = exporter.get_finished_spans()[0]
    assert _events(span)[0] == (
        "ExerciseAnswered",
        {
            "word": "warten",
            "topic": "government",
            "is_correct": True,
            "is_new": True,
            "recall_mode": "none",
            # prev_repetition_interval is omitted, not sent as None — see
            # events.py's _attributes() for why.
            "next_repetition_interval": 0,
        },
    )


def test_answering_a_due_review_reports_is_new_false_and_interval_doubling(
    tracer: Tracer,
    exporter: InMemorySpanExporter,
) -> None:
    exercise = make_exercise(word="warten", answer="auf")
    today = datetime.now(UTC).date()
    state = {
        "word_schedule": {
            "warten": {
                "government": {
                    "repetition_interval": 4,
                    "due_date": (today - timedelta(days=1)).isoformat(),
                    "introduced_at": (today - timedelta(days=1)).isoformat(),
                },
            },
        }
    }

    with tracer.start_as_current_span("test-span"):
        Tutor(Course([exercise]), state).check_answer(exercise, "auf")

    span = exporter.get_finished_spans()[0]
    assert _events(span)[0] == (
        "ExerciseAnswered",
        {
            "word": "warten",
            "topic": "government",
            "is_correct": True,
            "is_new": False,
            "recall_mode": "none",
            "prev_repetition_interval": 4,
            "next_repetition_interval": 8,
        },
    )


def test_wrong_answer_reports_correct_false_interval_reset_and_recall_mode(
    tracer: Tracer,
    exporter: InMemorySpanExporter,
) -> None:
    exercise = make_exercise(word="warten", answer="auf", recalls=True)
    today = datetime.now(UTC).date()
    state = {
        "word_schedule": {
            "warten": {
                "government": {
                    "repetition_interval": 8,
                    "due_date": (today - timedelta(days=1)).isoformat(),
                    "introduced_at": (today - timedelta(days=1)).isoformat(),
                },
            },
        }
    }

    with tracer.start_as_current_span("test-span"):
        Tutor(Course([exercise]), state).check_answer(exercise, "wrong")

    span = exporter.get_finished_spans()[0]
    assert _events(span)[0] == (
        "ExerciseAnswered",
        {
            "word": "warten",
            "topic": "government",
            "is_correct": False,
            "is_new": False,
            "recall_mode": "required",
            "prev_repetition_interval": 8,
            "next_repetition_interval": 0,
        },
    )


def test_creating_a_dependent_entry_reports_topic_unlocked_via_chain(
    tracer: Tracer,
    exporter: InMemorySpanExporter,
) -> None:
    case_exercise = make_exercise(word="mit", topic="preposition_case", answer="Freund")
    meaning_exercise = make_exercise(
        word="mit", topic="preposition_meaning", answer="mit"
    )
    chained_topics = {"preposition_case": ["preposition_meaning"]}
    tutor = Tutor(
        Course([case_exercise, meaning_exercise], word_chained_topics=chained_topics),
        {},
    )

    with tracer.start_as_current_span("test-span"):
        tutor.check_answer(case_exercise, "Freund")

    span = exporter.get_finished_spans()[0]
    assert (
        "TopicUnlocked",
        {
            "source_topic": "preposition_case",
            "dependent_topic": "preposition_meaning",
            "via": "chain",
        },
    ) in _events(span)


def test_creating_a_gated_dependent_entry_reports_topic_unlocked_via_gate(
    tracer: Tracer,
    exporter: InMemorySpanExporter,
) -> None:
    case_exercise = make_exercise(word="mit", topic="preposition_case", answer="Freund")
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

    with tracer.start_as_current_span("test-span"):
        tutor.check_answer(case_exercise, "Freund")

    span = exporter.get_finished_spans()[0]
    assert (
        "TopicUnlocked",
        {
            "source_topic": "preposition_case",
            "dependent_topic": "preposition_meaning",
            "via": "gate",
        },
    ) in _events(span)


def test_an_already_progressing_dependent_reports_no_unlock_event(
    tracer: Tracer,
    exporter: InMemorySpanExporter,
) -> None:
    case_exercise = make_exercise(word="mit", topic="preposition_case", answer="Freund")
    meaning_exercise = make_exercise(
        word="mit", topic="preposition_meaning", answer="mit"
    )
    today = datetime.now(UTC).date()
    state = {
        "word_schedule": {
            "mit": {
                "preposition_meaning": {
                    "repetition_interval": 8,
                    "due_date": (today + timedelta(days=8)).isoformat(),
                },
            },
        }
    }
    chained_topics = {"preposition_case": ["preposition_meaning"]}
    tutor = Tutor(
        Course([case_exercise, meaning_exercise], word_chained_topics=chained_topics),
        state,
    )

    with tracer.start_as_current_span("test-span"):
        tutor.check_answer(case_exercise, "Freund")

    span = exporter.get_finished_spans()[0]
    assert not any(name == "TopicUnlocked" for name, _ in _events(span))


def test_a_dependent_with_no_exercises_reports_no_unlock_event(
    tracer: Tracer,
    exporter: InMemorySpanExporter,
) -> None:
    case_exercise = make_exercise(word="mit", topic="preposition_case", answer="Freund")
    chained_topics = {"preposition_case": ["preposition_meaning"]}
    tutor = Tutor(
        Course([case_exercise], word_chained_topics=chained_topics),
        {},
    )

    with tracer.start_as_current_span("test-span"):
        tutor.check_answer(case_exercise, "Freund")

    span = exporter.get_finished_spans()[0]
    assert not any(name == "TopicUnlocked" for name, _ in _events(span))


def test_answer_chained_dependent_reports_topic_unlocked(
    tracer: Tracer,
    exporter: InMemorySpanExporter,
) -> None:
    government_exercise = make_exercise(word="warten", topic="government", answer="auf")
    meaning_exercise = make_exercise(word="auf", topic="preposition_meaning")
    answer_chained_topics = {"government": ["preposition_meaning"]}
    tutor = Tutor(
        Course(
            [government_exercise, meaning_exercise],
            answer_chained_topics=answer_chained_topics,
        ),
        {},
    )

    with tracer.start_as_current_span("test-span"):
        tutor.check_answer(government_exercise, "auf")

    span = exporter.get_finished_spans()[0]
    assert (
        "TopicUnlocked",
        {
            "source_topic": "government",
            "dependent_topic": "preposition_meaning",
            "via": "chain",
        },
    ) in _events(span)


def test_next_exercise_reports_nothing_available(
    tracer: Tracer,
    exporter: InMemorySpanExporter,
) -> None:
    # Both pairs already have an entry, neither due today.
    exercises = [make_exercise(word="warten"), make_exercise(word="hoffen")]
    today = datetime.now(UTC).date()
    state = {
        "word_schedule": {
            "warten": {
                "government": {
                    "repetition_interval": 30,
                    "due_date": (today + timedelta(days=29)).isoformat(),
                },
            },
            "hoffen": {
                "government": {
                    "repetition_interval": 5,
                    "due_date": (today + timedelta(days=8)).isoformat(),
                },
            },
        }
    }
    tutor = Tutor(Course(exercises), state)

    with tracer.start_as_current_span("test-span"):
        exercise = tutor.next_exercise()

    assert exercise is None
    span = exporter.get_finished_spans()[0]
    assert _events(span) == [("NoExerciseAvailable", {"reason": "nothing_available"})]


def test_next_exercise_reports_daily_cap_reached(
    tracer: Tracer,
    exporter: InMemorySpanExporter,
) -> None:
    # A fresh "warten" pair exists, but every other word already introduced
    # today has used up the daily cap — the pair is available in principle,
    # just not right now, which is exactly what "daily_cap_reached" reports
    # (as opposed to "nothing_available" — see the test above).
    today = datetime.now(UTC).date()
    capped_exercises = [
        make_exercise(word=f"introduced{i}") for i in range(Tutor.NEW_WORDS_PER_DAY)
    ]
    exercises = [*capped_exercises, make_exercise(word="warten")]
    word_schedule = {
        f"introduced{i}": {
            "government": {
                "repetition_interval": 1,
                "due_date": (today + timedelta(days=30)).isoformat(),
                "introduced_at": today.isoformat(),
            },
        }
        for i in range(Tutor.NEW_WORDS_PER_DAY)
    }
    tutor = Tutor(Course(exercises), {"word_schedule": word_schedule})

    with tracer.start_as_current_span("test-span"):
        exercise = tutor.next_exercise()

    assert exercise is None
    span = exporter.get_finished_spans()[0]
    assert _events(span) == [("NoExerciseAvailable", {"reason": "daily_cap_reached"})]


def test_next_exercise_reports_a_new_pair_selected(
    tracer: Tracer,
    exporter: InMemorySpanExporter,
) -> None:
    tutor = Tutor(Course([make_exercise(word="warten")]), {})

    with tracer.start_as_current_span("test-span"):
        exercise = tutor.next_exercise()

    assert exercise is not None
    span = exporter.get_finished_spans()[0]
    assert _events(span) == [
        ("LessonStarted", {"size": 1}),
        (
            "ExerciseSelected",
            {
                "word": "warten",
                "topic": "government",
                "question": "Ich ___ warten.",
                "is_new": True,
            },
        ),
    ]


def test_next_exercise_reports_a_due_review_selected_as_not_new(
    tracer: Tracer,
    exporter: InMemorySpanExporter,
) -> None:
    today = datetime.now(UTC).date()
    state = {
        "word_schedule": {
            "warten": {
                "government": {
                    "repetition_interval": 4,
                    "due_date": (today - timedelta(days=1)).isoformat(),
                    "introduced_at": (today - timedelta(days=5)).isoformat(),
                },
            },
        }
    }
    tutor = Tutor(Course([make_exercise(word="warten")]), state)

    with tracer.start_as_current_span("test-span"):
        tutor.next_exercise()

    span = exporter.get_finished_spans()[0]
    assert _events(span) == [
        ("LessonStarted", {"size": 1}),
        (
            "ExerciseSelected",
            {
                "word": "warten",
                "topic": "government",
                "question": "Ich ___ warten.",
                "is_new": False,
            },
        ),
    ]


def test_next_exercise_reports_a_chain_queued_pair_selected_as_new(
    tracer: Tracer,
    exporter: InMemorySpanExporter,
) -> None:
    # A chain created the entry, but the learner has never answered the pair
    today = datetime.now(UTC).date()
    state = {
        "word_schedule": {
            "warten": {
                "government": {
                    "repetition_interval": 0,
                    "due_date": today.isoformat(),
                },
            },
        }
    }
    tutor = Tutor(Course([make_exercise(word="warten")]), state)

    with tracer.start_as_current_span("test-span"):
        tutor.next_exercise()

    span = exporter.get_finished_spans()[0]
    assert _events(span) == [
        ("LessonStarted", {"size": 1}),
        (
            "ExerciseSelected",
            {
                "word": "warten",
                "topic": "government",
                "question": "Ich ___ warten.",
                "is_new": True,
            },
        ),
    ]


def test_a_recall_after_a_wrong_answer_reports_a_required_first_attempt(
    tracer: Tracer,
    exporter: InMemorySpanExporter,
) -> None:
    exercise = make_exercise(word="warten", answer="auf", recalls=True)
    tutor = Tutor(Course([exercise]), {})
    tutor.check_answer(exercise, "auf")
    tutor.check_answer(exercise, "an")

    with tracer.start_as_current_span("test-span"):
        recall = tutor.request_recall(exercise)
        tutor.check_recall(exercise, recall, "Ich warte auf den Bus.")

    span = exporter.get_finished_spans()[0]
    assert _events(span) == [
        (
            "RecallRequested",
            {
                "word": "warten",
                "topic": "government",
                "question": "Ich ___ (der Bus).",
                "recall_mode": "required",
                "attempt": 1,
            },
        ),
        (
            "RecallAnswered",
            {
                "word": "warten",
                "topic": "government",
                "question": "Ich ___ (der Bus).",
                "is_correct": True,
                "recall_mode": "required",
                "attempt": 1,
            },
        ),
    ]


def test_a_recall_after_try_again_reports_the_next_attempt(
    tracer: Tracer,
    exporter: InMemorySpanExporter,
) -> None:
    exercise = make_exercise(word="warten", answer="auf", recalls=True)
    tutor = Tutor(Course([exercise]), {})
    tutor.check_answer(exercise, "auf")
    recall = tutor.request_recall(exercise)
    tutor.check_recall(exercise, recall, "Ich warte.")

    with tracer.start_as_current_span("test-span"):
        recall = tutor.request_recall(exercise)
        tutor.check_recall(exercise, recall, "Ich warte.")

    span = exporter.get_finished_spans()[0]
    assert [
        (name, attributes["recall_mode"], attributes["attempt"])
        for name, attributes in _events(span)
    ] == [
        ("RecallRequested", "optional", 2),
        ("RecallAnswered", "optional", 2),
    ]


def test_a_recall_answer_after_a_newer_answer_reports_no_mode_or_attempt(
    tracer: Tracer,
    exporter: InMemorySpanExporter,
) -> None:
    # The other frontend answered an exercise after the bot showed the recall
    exercise = make_exercise(word="warten", answer="auf", recalls=True)
    tutor = Tutor(Course([exercise]), {})
    tutor.check_answer(exercise, "an")
    recall = tutor.request_recall(exercise)
    tutor.check_answer(exercise, "auf")

    with tracer.start_as_current_span("test-span"):
        tutor.check_recall(exercise, recall, "Ich warte.")

    span = exporter.get_finished_spans()[0]
    assert _events(span) == [
        (
            "RecallAnswered",
            {
                "word": "warten",
                "topic": "government",
                "question": "Ich ___ (der Bus).",
                "is_correct": False,
            },
        ),
    ]


def test_a_recall_answer_after_a_recall_for_another_exercise_reports_no_mode(
    tracer: Tracer,
    exporter: InMemorySpanExporter,
) -> None:
    # The bot showed a recall for warten. Then the web app took an answer and
    # gave a recall for another exercise
    warten = make_exercise(word="warten", answer="auf", recalls=True)
    denken = make_exercise(word="denken", answer="auf", recalls=True)
    tutor = Tutor(Course([warten, denken]), {})
    tutor.check_answer(warten, "an")
    recall = tutor.request_recall(warten)
    tutor.check_answer(denken, "an")
    tutor.request_recall(denken)

    with tracer.start_as_current_span("test-span"):
        tutor.check_recall(warten, recall, "Ich warte auf den Bus.")

    span = exporter.get_finished_spans()[0]
    assert _events(span) == [
        (
            "RecallAnswered",
            {
                "word": "warten",
                "topic": "government",
                "question": "Ich ___ (der Bus).",
                "is_correct": True,
            },
        ),
    ]


def test_a_recall_for_an_exercise_without_its_answer_reports_no_mode(
    tracer: Tracer,
    exporter: InMemorySpanExporter,
) -> None:
    # The web app recorded an answer to denken after the bot showed warten
    warten = make_exercise(word="warten", answer="auf", recalls=True)
    denken = make_exercise(word="denken", answer="auf", recalls=True)
    tutor = Tutor(Course([warten, denken]), {})
    tutor.check_answer(warten, "an")
    tutor.check_answer(denken, "auf")

    with tracer.start_as_current_span("test-span"):
        tutor.request_recall(warten)

    span = exporter.get_finished_spans()[0]
    assert _events(span) == [
        (
            "RecallRequested",
            {
                "word": "warten",
                "topic": "government",
                "question": "Ich ___ (der Bus).",
            },
        ),
    ]


def test_lesson_recall_mistakes_report_only_the_words_and_topics_of_the_course(
    tracer: Tracer,
    exporter: InMemorySpanExporter,
) -> None:
    warten = make_exercise(word="warten", answer="auf")
    hoffen = make_exercise(word="hoffen", answer="auf")
    tutor = Tutor(Course([warten, hoffen]), {})
    tutor.check_answer(warten, "auf")

    with tracer.start_as_current_span("test-span"):
        tutor.report_lesson_recall_mistakes(
            [
                Pair(word="warten", topic="government"),
                Pair(word="hoffen", topic="government"),
                Pair(word="warten", topic="genus"),
                Pair(word="Kino", topic="government"),
                Pair(word="Kino", topic="genus"),
            ]
        )

    span = exporter.get_finished_spans()[0]
    assert _events(span) == [
        (
            "LessonRecallMistake",
            {
                "in_course": True,
                "introduced": True,
                "word": "warten",
                "topic": "government",
            },
        ),
        (
            "LessonRecallMistake",
            {
                "in_course": True,
                "introduced": False,
                "word": "hoffen",
                "topic": "government",
            },
        ),
        (
            "LessonRecallMistake",
            {"in_course": False, "introduced": False, "word": "warten"},
        ),
        (
            "LessonRecallMistake",
            {"in_course": False, "introduced": False, "topic": "government"},
        ),
        ("LessonRecallMistake", {"in_course": False, "introduced": False}),
    ]
