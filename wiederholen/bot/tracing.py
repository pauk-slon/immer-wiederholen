from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.dispatcher.event.bases import UNHANDLED
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
    Message,
    TelegramObject,
    Update,
)
from opentelemetry import trace
from opentelemetry.trace import Tracer
from redis.exceptions import RedisError

from wiederholen.tracing import default_tracer

from .l10n import get_language


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
    if isinstance(event, ChatMemberUpdated):
        return "telegram.my_chat_member", {
            "telegram.chat_id": event.chat.id,
            "telegram.chat_member.status": event.new_chat_member.status,
        }
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
        ) as span:
            result = await handler(event, data)
            # False when no handler matched, so the learner got no reply
            span.set_attribute("telegram.handled", result is not UNHANDLED)
            state = data.get("state")
            if isinstance(state, FSMContext):
                await _record_language(span, state)
            return result


async def _record_language(span: trace.Span, state: FSMContext) -> None:
    # Read after the handler, so /language records the new language
    try:
        state_data = await state.get_data()
    except RedisError:
        # The update was already handled, so the trace must not fail it
        return
    span.set_attribute("telegram.language", get_language(state_data))
