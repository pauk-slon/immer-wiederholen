import pytest
from aiogram import Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.methods import EditMessageReplyMarkup, SendMessage
from aiogram.types import InlineKeyboardMarkup
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Tracer

from tests.plugins.aiogram import FeedCallbackQuery, FeedMessage
from tests.plugins.curriculum import make_exercise
from wiederholen.bot.commands.wiederholen import NEXT_EXERCISE
from wiederholen.bot.l10n import EN, RU
from wiederholen.bot.tracing import TracingMiddleware
from wiederholen.school import Course
from wiederholen.school.curriculum import TopicGroup


def _course() -> Course:
    return Course(
        [],
        topic_groups={
            "verb_forms": TopicGroup(
                title={"ru": "Формы глаголов", "en": "Verb forms"},
                topics=frozenset({"partizip_ii"}),
            ),
            "cases": TopicGroup(
                title={"ru": "Падежи", "en": "Cases"},
                topics=frozenset({"verb_case"}),
            ),
        },
    )


async def test_defaults_to_ru(
    feed_message: FeedMessage,
) -> None:
    requests = await feed_message("/start", course=_course())

    assert len(requests) == 1
    assert requests[0].text == RU.start


@pytest.mark.parametrize("language,expected", [("ru", RU.start), ("en", EN.start)])
async def test_responds_in_current_language(
    state: FSMContext,
    feed_message: FeedMessage,
    language: str,
    expected: str,
) -> None:
    await state.update_data(language=language)
    requests = await feed_message("/start", course=_course())

    assert len(requests) == 1
    assert requests[0].text == expected


@pytest.mark.parametrize("payload,expected", [("en", EN.start), ("ru", RU.start)])
async def test_deep_link_payload_sets_language(
    state: FSMContext,
    feed_message: FeedMessage,
    payload: str,
    expected: str,
) -> None:
    requests = await feed_message(f"/start {payload}", course=_course())

    assert len(requests) == 1
    assert requests[0].text == expected
    assert (await state.get_data())["language"] == payload


@pytest.mark.parametrize(
    "stored,payload,expected", [("ru", "en", RU.start), ("en", "ru", EN.start)]
)
async def test_deep_link_payload_keeps_stored_language(
    state: FSMContext,
    feed_message: FeedMessage,
    stored: str,
    payload: str,
    expected: str,
) -> None:
    await state.update_data(language=stored)
    requests = await feed_message(f"/start {payload}", course=_course())

    assert len(requests) == 1
    assert requests[0].text == expected
    assert (await state.get_data())["language"] == stored


async def test_deep_link_payload_keeps_default_language_of_existing_chat(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    await state.update_data(last_buttoned_message_id=None)
    requests = await feed_message("/start en", course=_course())

    assert len(requests) == 1
    assert requests[0].text == RU.start
    assert "language" not in await state.get_data()


async def test_unknown_deep_link_payload_falls_back_to_stored_language(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    await state.update_data(language="en")
    requests = await feed_message("/start whatever", course=_course())

    assert len(requests) == 1
    assert requests[0].text == EN.start
    assert (await state.get_data())["language"] == "en"


async def test_greeting_has_next_exercise_button(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    requests = await feed_message("/start", course=_course())

    markup = requests[0].reply_markup
    assert isinstance(markup, InlineKeyboardMarkup)
    assert markup.inline_keyboard[0][0].callback_data == NEXT_EXERCISE
    # feed_raw_update numbers the messages that the bot sends from 1000
    assert (await state.get_data())["last_buttoned_message_id"] == 1000


async def test_clears_a_stale_button(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    await state.update_data(last_buttoned_message_id=77)

    requests = await feed_message("/start", course=_course())

    edits = [r for r in requests if isinstance(r, EditMessageReplyMarkup)]
    assert len(edits) == 1
    assert edits[0].message_id == 77


async def test_deep_link_payload_after_start_keeps_language(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    # The greeting's button is stored in the FSM data, so after /start the
    # chat isn't new anymore (ADR 0019)
    await feed_message("/start", course=_course())

    requests = await feed_message("/start en", course=_course())

    assert requests[-1].text == RU.start
    assert "language" not in await state.get_data()


@pytest.mark.parametrize(
    "payload,expected",
    [
        (
            "ru-cases",
            f"{RU.start}\n\n✅ Темы: Падежи\n{RU.topics_change_hint}",
        ),
        (
            "en-cases-verb_forms",
            f"{EN.start}\n\n✅ Topics: Verb forms, Cases\n{EN.topics_change_hint}",
        ),
    ],
)
async def test_deep_link_payload_selects_topic_groups(
    state: FSMContext,
    feed_message: FeedMessage,
    payload: str,
    expected: str,
) -> None:
    requests = await feed_message(f"/start {payload}", course=_course())

    assert requests[0].text == expected
    data = await state.get_data()
    assert data["language"] == payload.split("-")[0]
    assert sorted(data["topic_groups"]) == sorted(payload.split("-")[1:])


async def test_deep_link_payload_skips_unknown_topic_groups(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    requests = await feed_message("/start en-nouns-cases", course=_course())

    assert requests[0].text == (
        f"{EN.start}\n\n✅ Topics: Cases\n{EN.topics_change_hint}"
    )
    assert (await state.get_data())["topic_groups"] == ["cases"]


async def test_deep_link_payload_with_only_unknown_groups_gives_usual_start(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    requests = await feed_message("/start en-nouns", course=_course())

    assert requests[0].text == EN.start
    data = await state.get_data()
    assert data["language"] == "en"
    assert "topic_groups" not in data


async def test_deep_link_payload_without_language_gives_usual_start(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    requests = await feed_message("/start cases", course=_course())

    assert requests[0].text == RU.start
    data = await state.get_data()
    assert "language" not in data
    assert "topic_groups" not in data


async def test_deep_link_payload_keeps_topic_groups_of_existing_chat(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    await state.update_data(topic_groups=["verb_forms"])

    requests = await feed_message("/start ru-cases", course=_course())

    assert requests[0].text == RU.start
    assert (await state.get_data())["topic_groups"] == ["verb_forms"]


async def test_selected_topic_groups_narrow_the_first_exercise(
    feed_message: FeedMessage,
    feed_callback_query: FeedCallbackQuery,
) -> None:
    course = Course(
        [
            make_exercise(word="sprechen", topic="partizip_ii"),
            make_exercise(word="helfen", topic="verb_case"),
        ],
        topic_groups=_course().topic_groups,
    )
    await feed_message("/start ru-cases", course=course)

    requests = await feed_callback_query(NEXT_EXERCISE, course=course)

    texts = [request.text for request in requests if isinstance(request, SendMessage)]
    assert any("Ich ___ helfen." in text for text in texts)
    assert not any("sprechen" in text for text in texts)


@pytest.fixture
def traced_dispatcher(
    dispatcher: Dispatcher, tracer: Tracer, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The dispatcher's TracingMiddleware opens the telegram.message span that
    # the handler adds attributes to, so it must record with the test tracer
    for middleware in dispatcher.update.outer_middleware:
        if isinstance(middleware, TracingMiddleware):
            monkeypatch.setattr(middleware, "_tracer", tracer)


@pytest.mark.usefixtures("traced_dispatcher")
async def test_records_new_chat_and_topic_groups_in_the_span(
    exporter: InMemorySpanExporter,
    feed_message: FeedMessage,
) -> None:
    await feed_message("/start ru-cases-nouns", course=_course())

    attributes = dict(exporter.get_finished_spans()[0].attributes or {})
    assert attributes["telegram.start.new_chat"] is True
    assert attributes["telegram.start.topic_groups"] == ("cases",)


@pytest.mark.usefixtures("traced_dispatcher")
async def test_records_an_existing_chat_in_the_span(
    state: FSMContext,
    exporter: InMemorySpanExporter,
    feed_message: FeedMessage,
) -> None:
    await state.update_data(language="ru")

    await feed_message("/start ru-cases", course=_course())

    attributes = dict(exporter.get_finished_spans()[0].attributes or {})
    assert attributes["telegram.start.new_chat"] is False
    assert "telegram.start.topic_groups" not in attributes
