from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update
from opentelemetry import trace
from opentelemetry.trace import Tracer

from wiederholen.tracing import default_tracer


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
