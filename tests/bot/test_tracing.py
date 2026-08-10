from datetime import UTC, datetime
from typing import Any

import pytest
from aiogram.types import CallbackQuery, Chat, Message, PollAnswer, Update, User
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Tracer

from wiederholen.bot import tracing
from wiederholen.bot.tracing import TracingMiddleware
from wiederholen.tutoring import ExerciseAnswered, RecallMode, TopicUnlocked


def _attributes(span: ReadableSpan) -> dict[str, Any]:
    assert span.attributes is not None
    return dict(span.attributes)


@pytest.fixture
def exporter() -> InMemorySpanExporter:
    return InMemorySpanExporter()


@pytest.fixture
def tracer(
    exporter: InMemorySpanExporter,
    monkeypatch: pytest.MonkeyPatch,
) -> Tracer:
    # The test session forces OTEL_SDK_DISABLED=true (tests/plugins/tracing.py)
    # so nothing ever exports real telemetry — these tests need a live,
    # recording provider of their own to verify span content, so opt back in
    # for just this provider's construction.
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider.get_tracer("test")


@pytest.fixture
def middleware(tracer: Tracer) -> TracingMiddleware:
    return TracingMiddleware(tracer=tracer)


def _make_message(text: str) -> Message:
    return Message(
        message_id=1,
        date=datetime.now(UTC),
        chat=Chat(id=42, type="private"),
        text=text,
    )


def _make_callback_query(data: str | None, *, message: Message | None) -> CallbackQuery:
    return CallbackQuery(
        id="1",
        from_user=User(id=1, is_bot=False, first_name="Test"),
        chat_instance="x",
        data=data,
        message=message,
    )


async def test_message_span_carries_chat_id_and_command(
    middleware: TracingMiddleware,
    exporter: InMemorySpanExporter,
) -> None:
    event = Update(update_id=1, message=_make_message("/wiederholen"))

    async def handler(event, data):
        return "result"

    result = await middleware(handler, event, {})

    assert result == "result"
    span = exporter.get_finished_spans()[0]
    assert span.name == "telegram.message"
    attributes = _attributes(span)
    assert attributes["telegram.chat_id"] == 42
    assert attributes["telegram.command"] == "/wiederholen"


async def test_message_span_omits_command_for_free_text(
    middleware: TracingMiddleware,
    exporter: InMemorySpanExporter,
) -> None:
    event = Update(update_id=1, message=_make_message("gesprochen"))

    async def handler(event, data):
        return None

    await middleware(handler, event, {})

    span = exporter.get_finished_spans()[0]
    assert "telegram.command" not in _attributes(span)


async def test_callback_query_span_carries_chat_id_and_callback_data(
    middleware: TracingMiddleware,
    exporter: InMemorySpanExporter,
) -> None:
    callback_query = _make_callback_query("__next__", message=_make_message("question"))
    event = Update(update_id=1, callback_query=callback_query)

    async def handler(event, data):
        return None

    await middleware(handler, event, {})

    span = exporter.get_finished_spans()[0]
    assert span.name == "telegram.callback_query"
    attributes = _attributes(span)
    assert attributes["telegram.chat_id"] == 42
    assert attributes["telegram.callback_data"] == "__next__"


async def test_callback_query_span_omits_chat_id_when_message_is_inaccessible(
    middleware: TracingMiddleware,
    exporter: InMemorySpanExporter,
) -> None:
    callback_query = _make_callback_query("__next__", message=None)
    event = Update(update_id=1, callback_query=callback_query)

    async def handler(event, data):
        return None

    await middleware(handler, event, {})

    span = exporter.get_finished_spans()[0]
    attributes = _attributes(span)
    assert "telegram.chat_id" not in attributes
    assert attributes["telegram.callback_data"] == "__next__"


async def test_other_update_types_get_a_generic_span(
    middleware: TracingMiddleware,
    exporter: InMemorySpanExporter,
) -> None:
    poll_answer = PollAnswer(
        poll_id="1",
        option_ids=[0],
        option_persistent_ids=["a"],
        voter_chat=None,
        user=User(id=1, is_bot=False, first_name="Test"),
    )
    event = Update(update_id=1, poll_answer=poll_answer)

    async def handler(event, data):
        return None

    await middleware(handler, event, {})

    span = exporter.get_finished_spans()[0]
    assert span.name == "telegram.update"
    assert _attributes(span) == {}


async def test_handler_exception_propagates_and_is_recorded(
    middleware: TracingMiddleware,
    exporter: InMemorySpanExporter,
) -> None:
    event = Update(update_id=1, message=_make_message("/wiederholen"))

    async def handler(event, data):
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        await middleware(handler, event, {})

    span = exporter.get_finished_spans()[0]
    assert span.status.status_code.name == "ERROR"


def test_otlp_endpoint_not_configured_when_no_endpoint_env_vars_are_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)

    assert tracing._otlp_endpoint_configured() is False


def test_otlp_endpoint_configured_via_the_generic_endpoint_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)

    assert tracing._otlp_endpoint_configured() is True


def test_otlp_endpoint_configured_via_the_traces_specific_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://collector:4318")

    assert tracing._otlp_endpoint_configured() is True


def test_configure_tracing_is_a_noop_without_an_otlp_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    provider_before = trace.get_tracer_provider()

    tracing.configure_tracing()

    assert trace.get_tracer_provider() is provider_before


def test_configure_tracing_installs_a_provider_when_an_otlp_endpoint_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # trace.set_tracer_provider() only ever succeeds once per process (see
    # wiederholen/bot/tracing.py's own module docstring-equivalent notes on
    # this), so calling the real one here would make this test's outcome
    # depend on whether some earlier test in the same session already
    # claimed it — same reason the `tracer` fixture above builds its own
    # provider directly instead of going through the global registration.
    # Spying on the setter instead sidesteps that entirely.
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    installed_providers: list[object] = []
    monkeypatch.setattr(trace, "set_tracer_provider", installed_providers.append)

    tracing.configure_tracing()

    assert len(installed_providers) == 1
    assert isinstance(installed_providers[0], TracerProvider)


def test_record_tutoring_events_adds_one_span_event_per_event(
    tracer: Tracer,
    exporter: InMemorySpanExporter,
) -> None:
    events = [
        ExerciseAnswered(
            word="warten",
            topic="government",
            is_correct=True,
            is_new=False,
            recall_mode=RecallMode.optional,
            prev_repetition_interval=4,
            next_repetition_interval=8,
        ),
        TopicUnlocked(
            source_topic="government",
            dependent_topic="preposition_meaning",
            via="chain",
        ),
    ]

    with tracer.start_as_current_span("test-span"):
        tracing.record_tutoring_events(events)

    span = exporter.get_finished_spans()[0]
    assert [event.name for event in span.events] == [
        "ExerciseAnswered",
        "TopicUnlocked",
    ]


def test_record_tutoring_events_carries_dataclass_fields_as_attributes(
    tracer: Tracer,
    exporter: InMemorySpanExporter,
) -> None:
    event = TopicUnlocked(
        source_topic="partizip_ii",
        dependent_topic="praeteritum",
        via="gate",
    )

    with tracer.start_as_current_span("test-span"):
        tracing.record_tutoring_events([event])

    span = exporter.get_finished_spans()[0]
    attributes = dict(span.events[0].attributes or {})
    assert attributes == {
        "source_topic": "partizip_ii",
        "dependent_topic": "praeteritum",
        "via": "gate",
    }


def test_record_tutoring_events_unwraps_enum_attributes_to_their_value(
    tracer: Tracer,
    exporter: InMemorySpanExporter,
) -> None:
    event = ExerciseAnswered(
        word="warten",
        topic="government",
        is_correct=True,
        is_new=True,
        recall_mode=RecallMode.required,
        prev_repetition_interval=0,
        next_repetition_interval=1,
    )

    with tracer.start_as_current_span("test-span"):
        tracing.record_tutoring_events([event])

    span = exporter.get_finished_spans()[0]
    attributes = dict(span.events[0].attributes or {})
    assert attributes["recall_mode"] == "required"


def test_record_tutoring_events_omits_none_attributes(
    tracer: Tracer,
    exporter: InMemorySpanExporter,
) -> None:
    # prev_repetition_interval is None for a pair's very first answer —
    # None isn't a valid span attribute type, and unlike an Enum there's no
    # single plain value to unwrap it to, so it's dropped instead.
    event = ExerciseAnswered(
        word="warten",
        topic="government",
        is_correct=True,
        is_new=True,
        recall_mode=RecallMode.none,
        prev_repetition_interval=None,
        next_repetition_interval=0,
    )

    with tracer.start_as_current_span("test-span"):
        tracing.record_tutoring_events([event])

    span = exporter.get_finished_spans()[0]
    attributes = dict(span.events[0].attributes or {})
    assert "prev_repetition_interval" not in attributes
    assert attributes["next_repetition_interval"] == 0
