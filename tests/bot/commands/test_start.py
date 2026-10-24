import pytest
from aiogram.fsm.context import FSMContext

from tests.plugins.aiogram import FeedMessage
from wiederholen.bot.l10n import EN, RU


async def test_defaults_to_ru(
    feed_message: FeedMessage,
) -> None:
    requests = await feed_message("/start")

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
    requests = await feed_message("/start")

    assert len(requests) == 1
    assert requests[0].text == expected


@pytest.mark.parametrize("payload,expected", [("en", EN.start), ("ru", RU.start)])
async def test_deep_link_payload_sets_language(
    state: FSMContext,
    feed_message: FeedMessage,
    payload: str,
    expected: str,
) -> None:
    requests = await feed_message(f"/start {payload}")

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
    requests = await feed_message(f"/start {payload}")

    assert len(requests) == 1
    assert requests[0].text == expected
    assert (await state.get_data())["language"] == stored


async def test_deep_link_payload_keeps_default_language_of_existing_chat(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    await state.update_data(last_buttoned_message_id=None)
    requests = await feed_message("/start en")

    assert len(requests) == 1
    assert requests[0].text == RU.start
    assert "language" not in await state.get_data()


async def test_unknown_deep_link_payload_falls_back_to_stored_language(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    await state.update_data(language="en")
    requests = await feed_message("/start whatever")

    assert len(requests) == 1
    assert requests[0].text == EN.start
    assert (await state.get_data())["language"] == "en"
