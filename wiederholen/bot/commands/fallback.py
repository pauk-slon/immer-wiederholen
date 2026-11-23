"""The reply to a message that no other handler takes (see docs/bot.md)."""

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from opentelemetry import trace

from wiederholen.bot.commands.wiederholen import make_next_button
from wiederholen.bot.l10n import LOCALES, get_language
from wiederholen.bot.pending_buttons import (
    clear_stale_buttons,
    remember_buttoned_message,
)

router = Router()


@router.message()
async def reply_to_an_unexpected_message(message: Message, state: FSMContext) -> None:
    trace.get_current_span().set_attribute("telegram.fallback", True)
    await clear_stale_buttons(message.bot, message.chat.id, state)
    locale = LOCALES[get_language(await state.get_data())]
    sent = await message.answer(
        locale.unexpected_message, reply_markup=make_next_button(locale)
    )
    await remember_buttoned_message(state, sent)
