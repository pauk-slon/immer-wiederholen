import dataclasses
import os
from collections.abc import Awaitable, Callable, Sequence
from enum import Enum
from typing import Any, Final

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk.environment_variables import (
    OTEL_EXPORTER_OTLP_ENDPOINT,
    OTEL_EXPORTER_OTLP_TRACES_ENDPOINT,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Tracer

from wiederholen.tutoring import TutoringEvent

default_tracer: Final = trace.get_tracer(__name__)


def _otlp_endpoint_configured() -> bool:
    return bool(
        os.environ.get(OTEL_EXPORTER_OTLP_ENDPOINT)
        or os.environ.get(OTEL_EXPORTER_OTLP_TRACES_ENDPOINT)
    )


def configure_tracing() -> None:
    # OTLPSpanExporter() defaults to http://localhost:4318, a convention for a
    # local collector sidecar this project's deployment doesn't have — without
    # an explicit endpoint there's nowhere valid to export to, so skip wiring
    # up a real provider at all rather than let it retry into the void.
    if not _otlp_endpoint_configured():
        return
    provider = TracerProvider(resource=Resource.create())
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)


def instrument_redis() -> None:
    RedisInstrumentor().instrument()


def _event_attributes(event: TutoringEvent) -> dict[str, Any]:
    # Enum values (e.g. RecallMode) aren't valid span event attribute types,
    # so unwrap them to their plain value; everything else in a TutoringEvent
    # is already a span-attribute-safe type (str/bool/int).
    return {
        key: value.value if isinstance(value, Enum) else value
        for key, value in dataclasses.asdict(event).items()
    }


def record_tutoring_events(events: Sequence[TutoringEvent]) -> None:
    # A generic bridge, deliberately with no knowledge of what any given
    # TutoringEvent means — wiederholen.tutoring decides what counts as an
    # event and when it fires; this just serializes whatever it hands back
    # onto the current span.
    span = trace.get_current_span()
    for event in events:
        span.add_event(type(event).__name__, attributes=_event_attributes(event))


def _describe(update: Update) -> tuple[str, dict[str, Any]]:
    event = update.event
    if isinstance(event, Message):
        attributes: dict[str, Any] = {"telegram.chat_id": event.chat.id}
        if event.text and event.text.startswith("/"):
            attributes["telegram.command"] = event.text.split()[0]
        return "telegram.message", attributes
    if isinstance(event, CallbackQuery):
        attributes = {}
        if isinstance(event.message, Message):
            attributes["telegram.chat_id"] = event.message.chat.id
        if event.data is not None:
            attributes["telegram.callback_data"] = event.data
        return "telegram.callback_query", attributes
    return "telegram.update", {}


class TracingMiddleware(BaseMiddleware):
    def __init__(self, tracer: Tracer = default_tracer) -> None:
        self._tracer = tracer

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        assert isinstance(event, Update)
        span_name, attributes = _describe(event)
        with self._tracer.start_as_current_span(
            span_name,
            kind=trace.SpanKind.SERVER,
            attributes=attributes,
        ):
            return await handler(event, data)
