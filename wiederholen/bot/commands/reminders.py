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
    remember_buttoned_message,
)
from wiederholen.bot.reminder_settings import (
    REMIND_AFTER_HOURS_OPTIONS,
    REMINDERS_OFF,
    get_remind_after_hours,
)

router = Router()

SET_REMIND_AFTER_PREFIX: Final = "__remind_after__:"


def _make_reminder_buttons(selected: int, locale: Locale) -> InlineKeyboardMarkup:
    def button(text: str, hours: int) -> InlineKeyboardButton:
        return InlineKeyboardButton(
            text=f"✅ {text}" if hours == selected else text,
            callback_data=f"{SET_REMIND_AFTER_PREFIX}{hours}",
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(locale.btn_remind_after.format(hours=hours), hours)
                for hours in REMIND_AFTER_HOURS_OPTIONS
            ],
            [button(locale.btn_reminders_off, REMINDERS_OFF)],
        ]
    )


@router.message(Command("reminders"))
async def command_reminders(message: Message, state: FSMContext) -> None:
    await clear_stale_buttons(message.bot, message.chat.id, state)
    data = await state.get_data()
    locale = LOCALES[get_language(data)]
    sent = await message.answer(
        locale.reminders_prompt,
        reply_markup=_make_reminder_buttons(get_remind_after_hours(data), locale),
    )
    await remember_buttoned_message(state, sent)


@router.callback_query(F.data.startswith(SET_REMIND_AFTER_PREFIX))
async def handle_set_remind_after(callback: CallbackQuery, state: FSMContext) -> None:
    assert callback.data is not None
    await state.update_data(
        remind_after_hours=int(callback.data.removeprefix(SET_REMIND_AFTER_PREFIX))
    )
    data = await state.get_data()
    locale = LOCALES[get_language(data)]
    # Read back through get_remind_after_hours() so a stale or forged
    # callback value is reported as whatever the setting actually resolves to.
    hours = get_remind_after_hours(data)
    summary = (
        locale.reminders_off
        if hours == REMINDERS_OFF
        else locale.reminders_set.format(hours=hours)
    )
    if isinstance(callback.message, Message):
        await callback.message.edit_text(summary, reply_markup=make_next_button(locale))
        await remember_buttoned_message(state, callback.message)
    await callback.answer()
