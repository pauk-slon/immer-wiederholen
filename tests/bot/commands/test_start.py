import pytest

from aiogram.fsm.context import FSMContext

from wiederholen.bot.l10n import EN, RU

from tests.plugins.aiogram import FeedRawUpdate


async def test_defaults_to_ru(
    feed_raw_update: FeedRawUpdate,
) -> None:
    requests = await feed_raw_update("/start")

    assert len(requests) == 1
    assert requests[0].text == RU.start


@pytest.mark.parametrize("language,expected", [("ru", RU.start), ("en", EN.start)])
async def test_responds_in_current_language(
    state: FSMContext,
    feed_raw_update: FeedRawUpdate,
    language: str,
    expected: str,
) -> None:
    await state.update_data(language=language)
    requests = await feed_raw_update("/start")

    assert len(requests) == 1
    assert requests[0].text == expected
