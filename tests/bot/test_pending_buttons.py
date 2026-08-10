from unittest.mock import AsyncMock, Mock

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.methods import EditMessageReplyMarkup
from aiogram.types import Chat, Message

from wiederholen.bot.pending_buttons import (
    clear_stale_buttons,
    forget_buttoned_message,
    remember_buttoned_message,
)


def _make_message(bot: Bot | None, message_id: int = 1) -> Message:
    message = Mock(spec=Message, message_id=message_id, chat=Mock(spec=Chat, id=1))
    message.bot = bot
    return message


async def test_remember_buttoned_message_stores_the_message_id() -> None:
    state = AsyncMock(spec=FSMContext)
    message = _make_message(bot=None, message_id=42)

    await remember_buttoned_message(state, message)

    state.update_data.assert_awaited_once_with(last_buttoned_message_id=42)


async def test_forget_buttoned_message_clears_the_stored_id() -> None:
    state = AsyncMock(spec=FSMContext)

    await forget_buttoned_message(state)

    state.update_data.assert_awaited_once_with(last_buttoned_message_id=None)


async def test_clear_stale_buttons_does_nothing_when_none_pending() -> None:
    bot = AsyncMock(spec=Bot)
    state = AsyncMock(spec=FSMContext)
    state.get_data.return_value = {}
    message = _make_message(bot=bot)

    await clear_stale_buttons(message, state)

    bot.edit_message_reply_markup.assert_not_awaited()
    state.update_data.assert_not_awaited()


async def test_clear_stale_buttons_clears_and_forgets_a_pending_message() -> None:
    bot = AsyncMock(spec=Bot)
    state = AsyncMock(spec=FSMContext)
    state.get_data.return_value = {"last_buttoned_message_id": 77}
    message = _make_message(bot=bot)

    await clear_stale_buttons(message, state)

    bot.edit_message_reply_markup.assert_awaited_once_with(
        chat_id=1, message_id=77, reply_markup=None
    )
    state.update_data.assert_awaited_once_with(last_buttoned_message_id=None)


async def test_clear_stale_buttons_forgets_even_if_the_message_is_gone() -> None:
    bot = AsyncMock(spec=Bot)
    state = AsyncMock(spec=FSMContext)
    state.get_data.return_value = {"last_buttoned_message_id": 77}
    message = _make_message(bot=bot)
    method = EditMessageReplyMarkup(chat_id=1, message_id=77)
    bot.edit_message_reply_markup.side_effect = TelegramBadRequest(
        method=method, message="message to edit not found"
    )

    await clear_stale_buttons(message, state)

    state.update_data.assert_awaited_once_with(last_buttoned_message_id=None)
