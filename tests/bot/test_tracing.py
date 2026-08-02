from datetime import UTC, datetime
from typing import Any

import pytest
from aiogram.types import CallbackQuery, Chat, Message, Update, User
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from wiederholen.bot import tracing
from wiederholen.bot.tracing import TracingMiddleware


def _attributes(span: ReadableSpan) -> dict[str, Any]:
    assert span.attributes is not None
    return dict(span.attributes)


@pytest.fixture
def exporter() -> InMemorySpanExporter:
    return InMemorySpanExporter()


@pytest.fixture
def middleware(exporter: InMemorySpanExporter) -> TracingMiddleware:
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return TracingMiddleware(tracer=provider.get_tracer("test"))


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
    event = _make_message("/wiederholen")

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
    event = _make_message("gesprochen")

    async def handler(event, data):
        return None

    await middleware(handler, event, {})

    span = exporter.get_finished_spans()[0]
    assert "telegram.command" not in _attributes(span)


async def test_callback_query_span_carries_chat_id_and_callback_data(
    middleware: TracingMiddleware,
    exporter: InMemorySpanExporter,
) -> None:
    event = _make_callback_query("__next__", message=_make_message("question"))

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
    event = _make_callback_query("__next__", message=None)

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
    event = Update(update_id=1)

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
    event = _make_message("/wiederholen")

    async def handler(event, data):
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        await middleware(handler, event, {})

    span = exporter.get_finished_spans()[0]
    assert span.status.status_code.name == "ERROR"


def test_resource_attributes_fall_back_when_env_var_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)

    assert tracing._resource_attributes() == {
        "service.name": tracing.FALLBACK_SERVICE_NAME
    }


def test_resource_attributes_defer_to_env_var_when_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OTEL_SERVICE_NAME", "bot")

    assert tracing._resource_attributes() == {}
