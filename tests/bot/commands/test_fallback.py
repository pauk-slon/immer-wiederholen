import pytest
from aiogram import Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.methods import EditMessageReplyMarkup, SendMessage
from aiogram.types import InlineKeyboardMarkup
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Tracer

from tests.plugins.aiogram import FeedMessage, FeedRawUpdate
from tests.plugins.curriculum import make_exercise
from wiederholen.bot.commands.wiederholen import NEXT_EXERCISE
from wiederholen.bot.l10n import EN, RU
from wiederholen.bot.tracing import TracingMiddleware
from wiederholen.school import Course

COURSE = Course([make_exercise(word="warten")])


def _next_button(request: SendMessage) -> str | None:
    assert isinstance(request.reply_markup, InlineKeyboardMarkup)
    return request.reply_markup.inline_keyboard[0][0].callback_data


@pytest.mark.parametrize("text", ["Hallo", "Как это работает?", "/help"])
async def test_an_unexpected_message_gets_a_hint_and_the_next_button(
    feed_message: FeedMessage, text: str
) -> None:
    requests = await feed_message(text, course=COURSE)

    assert len(requests) == 1
    assert requests[0].text == RU.unexpected_message
    assert _next_button(requests[0]) == NEXT_EXERCISE


async def test_the_hint_is_in_the_chat_language(
    state: FSMContext, feed_message: FeedMessage
) -> None:
    await state.update_data(language="en")

    requests = await feed_message("Hello", course=COURSE)

    assert requests[0].text == EN.unexpected_message


async def test_a_sticker_gets_the_hint(
    feed_raw_update: FeedRawUpdate, message_factory, chat_id: int
) -> None:
    raw_update = message_factory("")
    message = raw_update["message"]
    del message["text"]
    message["sticker"] = {
        "file_id": "x",
        "file_unique_id": "x",
        "type": "regular",
        "width": 512,
        "height": 512,
        "is_animated": False,
        "is_video": False,
    }

    requests = await feed_raw_update(raw_update, course=COURSE)

    assert requests[0].text == RU.unexpected_message


async def test_the_hint_replaces_the_buttons_of_an_earlier_message(
    feed_message: FeedMessage,
) -> None:
    await feed_message("Hallo", course=COURSE)

    requests = await feed_message("Hallo", course=COURSE)

    assert isinstance(requests[0], EditMessageReplyMarkup)
    assert requests[0].reply_markup is None
    assert requests[1].text == RU.unexpected_message


async def test_an_answer_to_an_exercise_isnt_taken(
    feed_message: FeedMessage,
) -> None:
    await feed_message("/wiederholen", course=COURSE)

    requests = await feed_message("falsch", course=COURSE)

    assert all(
        getattr(request, "text", None) != RU.unexpected_message for request in requests
    )


@pytest.fixture
def traced_dispatcher(
    dispatcher: Dispatcher, tracer: Tracer, monkeypatch: pytest.MonkeyPatch
) -> None:
    for middleware in dispatcher.update.outer_middleware:
        if isinstance(middleware, TracingMiddleware):
            monkeypatch.setattr(middleware, "_tracer", tracer)


@pytest.mark.usefixtures("traced_dispatcher")
async def test_the_fallback_is_recorded_on_the_span(
    exporter: InMemorySpanExporter, feed_message: FeedMessage
) -> None:
    await feed_message("Hallo", course=COURSE)

    span = next(
        s for s in exporter.get_finished_spans() if s.name == "telegram.message"
    )
    attributes = dict(span.attributes or {})
    assert attributes["telegram.fallback"] is True
    assert attributes["telegram.handled"] is True
