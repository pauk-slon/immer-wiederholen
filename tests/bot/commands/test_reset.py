from aiogram.fsm.context import FSMContext
from aiogram.methods import EditMessageReplyMarkup
from aiogram.types import InlineKeyboardMarkup

from tests.plugins.aiogram import FeedCallbackQuery, FeedMessage
from tests.plugins.journal_store import ReadJournal, SeedJournal
from wiederholen.bot.commands.reset import RESET_CANCEL, RESET_CONFIRM
from wiederholen.bot.commands.wiederholen import NEXT_EXERCISE
from wiederholen.bot.l10n import EN, RU
from wiederholen.tutoring import Course


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
    seed_journal: SeedJournal,
    read_journal: ReadJournal,
    chat_id: int,
) -> None:
    await seed_journal(
        str(chat_id),
        {
            "word_schedule": {"warten": {"government": {}}},
            "last_exercise": {"is_recall_optional": False},
        },
    )

    requests = await feed_callback_query(RESET_CONFIRM, course=Course([]))

    assert len(requests) == 2
    assert requests[0].text == RU.reset_done
    journal = await read_journal(str(chat_id))
    assert journal["word_schedule"] == {}
    assert journal["last_exercise"]["is_recall_optional"] is False


async def test_confirming_reset_preserves_language(
    state: FSMContext,
    feed_callback_query: FeedCallbackQuery,
    seed_journal: SeedJournal,
    read_journal: ReadJournal,
    chat_id: int,
) -> None:
    await state.update_data(language="en")
    await seed_journal(str(chat_id), {"word_schedule": {"x": {"y": {}}}})

    requests = await feed_callback_query(RESET_CONFIRM, course=Course([]))

    assert len(requests) == 2
    assert requests[0].text == EN.reset_done
    data = await state.get_data()
    assert data["language"] == "en"
    journal = await read_journal(str(chat_id))
    assert journal["word_schedule"] == {}


async def test_cancelling_reset_keeps_journal(
    state: FSMContext,
    feed_callback_query: FeedCallbackQuery,
    seed_journal: SeedJournal,
    read_journal: ReadJournal,
    chat_id: int,
) -> None:
    journal = {"word_schedule": {"warten": {"government": {}}}}
    await seed_journal(str(chat_id), journal)

    requests = await feed_callback_query(RESET_CANCEL, course=Course([]))

    assert len(requests) == 2
    assert requests[0].text == RU.reset_cancelled
    assert await read_journal(str(chat_id)) == journal


async def test_reset_command_clears_a_stale_button_left_from_wiederholen(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    await state.update_data(last_buttoned_message_id=77)

    requests = await feed_message("/reset", course=Course([]))

    edits = [r for r in requests if isinstance(r, EditMessageReplyMarkup)]
    assert len(edits) == 1
    assert edits[0].message_id == 77


async def test_reset_command_remembers_its_own_confirm_buttons(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    await feed_message("/reset", course=Course([]))

    data = await state.get_data()
    assert data["last_buttoned_message_id"] is not None


async def test_confirming_reset_offers_a_next_exercise_button(
    feed_callback_query: FeedCallbackQuery,
) -> None:
    requests = await feed_callback_query(RESET_CONFIRM, course=Course([]))

    edit_text = next(r for r in requests if hasattr(r, "text"))
    assert isinstance(edit_text.reply_markup, InlineKeyboardMarkup)
    buttons = [
        btn.callback_data
        for row in edit_text.reply_markup.inline_keyboard
        for btn in row
    ]
    assert buttons == [NEXT_EXERCISE]


async def test_confirming_reset_remembers_its_next_exercise_button(
    state: FSMContext,
    feed_callback_query: FeedCallbackQuery,
) -> None:
    await state.update_data(last_buttoned_message_id=1)

    await feed_callback_query(RESET_CONFIRM, course=Course([]))

    data = await state.get_data()
    assert data["last_buttoned_message_id"] is not None


async def test_cancelling_reset_forgets_its_own_buttons(
    state: FSMContext,
    feed_callback_query: FeedCallbackQuery,
) -> None:
    await state.update_data(last_buttoned_message_id=1)

    await feed_callback_query(RESET_CANCEL, course=Course([]))

    data = await state.get_data()
    assert data.get("last_buttoned_message_id") is None
