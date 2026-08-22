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

from wiederholen.bot.commands.wiederholen import make_next_button
from wiederholen.bot.l10n import LOCALES, Locale, get_language
from wiederholen.bot.pending_buttons import (
    clear_stale_buttons,
    forget_buttoned_message,
    remember_buttoned_message,
)
from wiederholen.student_record_book import StudentRecordBook
from wiederholen.tutoring import StudentRecord

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
    await clear_stale_buttons(message, state)
    language = get_language(await state.get_data())
    locale = LOCALES[language]
    sent = await message.answer(
        locale.reset_confirm_prompt,
        reply_markup=_make_confirm_buttons(locale),
    )
    await remember_buttoned_message(state, sent)


@router.callback_query(F.data == RESET_CONFIRM)
async def handle_reset_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    student_record_book: StudentRecordBook,
) -> None:
    state_data = await state.get_data()
    language = get_language(state_data)
    locale = LOCALES[language]
    async with student_record_book.check_out(
        str(callback.from_user.id)
    ) as student_record:
        StudentRecord.reset_progress(student_record)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            locale.reset_done, reply_markup=make_next_button(locale)
        )
        await remember_buttoned_message(state, callback.message)
    await callback.answer()


@router.callback_query(F.data == RESET_CANCEL)
async def handle_reset_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    language = get_language(await state.get_data())
    locale = LOCALES[language]
    if isinstance(callback.message, Message):
        await callback.message.edit_text(locale.reset_cancelled, reply_markup=None)
        await forget_buttoned_message(state)
    await callback.answer()
