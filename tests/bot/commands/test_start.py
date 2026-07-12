import pytest

from aiogram.fsm.context import FSMContext

from wiederholen.bot.l10n import EN, RU

from tests.plugins.aiogram import FeedMessage


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
