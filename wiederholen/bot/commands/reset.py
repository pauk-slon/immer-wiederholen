from typing import Final

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from wiederholen.bot.l10n import LOCALES, Locale, get_language
from wiederholen.tutoring import Journal

router = Router()

RESET_CONFIRM: Final = "__reset_confirm__"
RESET_CANCEL: Final = "__reset_cancel__"


def _make_confirm_buttons(locale: Locale) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=locale.reset_confirm_button, callback_data=RESET_CONFIRM
                ),
                InlineKeyboardButton(
                    text=locale.reset_cancel_button, callback_data=RESET_CANCEL
                ),
            ]
        ]
    )


@router.message(Command("reset"))
async def command_reset(message: Message, state: FSMContext) -> None:
    language = get_language(await state.get_data())
    locale = LOCALES[language]
    await message.answer(
        locale.reset_confirm_prompt,
        reply_markup=_make_confirm_buttons(locale),
    )


@router.callback_query(F.data == RESET_CONFIRM)
async def handle_reset_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    state_data = await state.get_data()
    language = get_language(state_data)
    locale = LOCALES[language]
    journal = state_data.get("journal", {})
    Journal(journal).reset_schedule()
    await state.update_data(journal=journal)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(locale.reset_done)
    await callback.answer()


@router.callback_query(F.data == RESET_CANCEL)
async def handle_reset_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    language = get_language(await state.get_data())
    locale = LOCALES[language]
    if isinstance(callback.message, Message):
        await callback.message.edit_text(locale.reset_cancelled)
    await callback.answer()
