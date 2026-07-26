from aiogram.fsm.context import FSMContext

from tests.plugins.aiogram import FeedMessage
from wiederholen.bot.l10n import EN, RU


async def test_switches_ru_to_en(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    await state.update_data(language="ru")
    requests = await feed_message("/language")

    assert len(requests) == 1
    assert (await state.get_data())["language"] == "en"
    assert requests[0].text == EN.start


async def test_switches_en_to_ru(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    await state.update_data(language="en")
    requests = await feed_message("/language")

    assert len(requests) == 1
    assert (await state.get_data())["language"] == "ru"
    assert requests[0].text == RU.start


async def test_defaults_to_ru_then_switches_to_en(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    requests = await feed_message("/language")

    assert len(requests) == 1
    assert (await state.get_data())["language"] == "en"
    assert requests[0].text == EN.start
