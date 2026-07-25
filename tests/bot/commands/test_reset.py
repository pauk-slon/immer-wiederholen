from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup

from wiederholen.bot.commands.reset import RESET_CANCEL, RESET_CONFIRM
from wiederholen.bot.l10n import EN, RU
from wiederholen.exercises import Course

from tests.plugins.aiogram import FeedCallbackQuery, FeedMessage


async def test_reset_command_asks_for_confirmation(feed_message: FeedMessage) -> None:
    requests = await feed_message("/reset", course=Course([]))

    assert len(requests) == 1
    assert requests[0].text == RU.reset_confirm_prompt
    assert isinstance(requests[0].reply_markup, InlineKeyboardMarkup)
    buttons = [
        btn.callback_data
        for row in requests[0].reply_markup.inline_keyboard
        for btn in row
    ]
    assert buttons == [RESET_CONFIRM, RESET_CANCEL]


async def test_reset_command_responds_in_current_language(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    await state.update_data(language="en")
    requests = await feed_message("/reset", course=Course([]))

    assert len(requests) == 1
    assert requests[0].text == EN.reset_confirm_prompt


async def test_confirming_reset_clears_schedule_only(
    state: FSMContext,
    feed_callback_query: FeedCallbackQuery,
) -> None:
    await state.update_data(
        journal={
            "word_schedule": {"warten:government": {}},
            "last_mark": {"correct": True, "recall": "none"},
        }
    )

    requests = await feed_callback_query(RESET_CONFIRM, course=Course([]))

    assert len(requests) == 2
    assert requests[0].text == RU.reset_done
    data = await state.get_data()
    assert data["journal"]["word_schedule"] == {}
    assert data["journal"]["last_mark"] == {"correct": True, "recall": "none"}


async def test_confirming_reset_preserves_language(
    state: FSMContext,
    feed_callback_query: FeedCallbackQuery,
) -> None:
    await state.update_data(language="en", journal={"word_schedule": {"x": {}}})

    requests = await feed_callback_query(RESET_CONFIRM, course=Course([]))

    assert len(requests) == 2
    assert requests[0].text == EN.reset_done
    data = await state.get_data()
    assert data["language"] == "en"
    assert data["journal"]["word_schedule"] == {}


async def test_cancelling_reset_keeps_journal(
    state: FSMContext,
    feed_callback_query: FeedCallbackQuery,
) -> None:
    journal = {"word_schedule": {"warten:government": {}}}
    await state.update_data(journal=journal)

    requests = await feed_callback_query(RESET_CANCEL, course=Course([]))

    assert len(requests) == 2
    assert requests[0].text == RU.reset_cancelled
    data = await state.get_data()
    assert data["journal"] == journal
