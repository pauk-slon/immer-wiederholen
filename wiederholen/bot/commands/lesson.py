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
from wiederholen.bot.l10n import LOCALES, Locale, format_count, get_language
from wiederholen.bot.lesson_settings import LESSON_SIZE_OPTIONS, get_lesson_size
from wiederholen.bot.pending_buttons import (
    clear_stale_buttons,
    remember_buttoned_message,
)

router = Router()

SET_LESSON_SIZE_PREFIX: Final = "__lesson_size__:"


def _make_lesson_size_buttons(selected: int, locale: Locale) -> InlineKeyboardMarkup:
    def button(size: int) -> InlineKeyboardButton:
        text = locale.btn_lesson_size.format(size=size)
        return InlineKeyboardButton(
            text=f"✅ {text}" if size == selected else text,
            callback_data=f"{SET_LESSON_SIZE_PREFIX}{size}",
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[[button(size) for size in LESSON_SIZE_OPTIONS]]
    )


@router.message(Command("lesson"))
async def command_lesson(message: Message, state: FSMContext) -> None:
    await clear_stale_buttons(message.bot, message.chat.id, state)
    data = await state.get_data()
    locale = LOCALES[get_language(data)]
    sent = await message.answer(
        locale.lesson_size_prompt,
        reply_markup=_make_lesson_size_buttons(get_lesson_size(data), locale),
    )
    await remember_buttoned_message(state, sent)


@router.callback_query(F.data.startswith(SET_LESSON_SIZE_PREFIX))
async def handle_set_lesson_size(callback: CallbackQuery, state: FSMContext) -> None:
    assert callback.data is not None
    await state.update_data(
        lesson_size=int(callback.data.removeprefix(SET_LESSON_SIZE_PREFIX))
    )
    data = await state.get_data()
    language = get_language(data)
    locale = LOCALES[language]
    # Read back so that a stale or forged value is reported as the size
    # that the bot actually uses
    summary = locale.lesson_size_set.format(
        count=format_count(get_lesson_size(data), "exercises", language)
    )
    if isinstance(callback.message, Message):
        await callback.message.edit_text(summary, reply_markup=make_next_button(locale))
        await remember_buttoned_message(state, callback.message)
    await callback.answer()
