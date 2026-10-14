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
from wiederholen.bot.topic_selection import get_selected_groups
from wiederholen.school import Course, Language

router = Router()

TOGGLE_TOPIC_GROUP_PREFIX: Final = "__topic_group__:"
TOPICS_DONE: Final = "__topics_done__"


def _make_topic_buttons(
    course: Course, selected: list[str], language: Language, locale: Locale
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{'✅' if group_id in selected else '⬜'} {group.title[language]}",
                    callback_data=f"{TOGGLE_TOPIC_GROUP_PREFIX}{group_id}",
                )
            ]
            for group_id, group in course.topic_groups.items()
        ]
        + [
            [
                InlineKeyboardButton(
                    text=locale.btn_topics_done, callback_data=TOPICS_DONE
                )
            ]
        ]
    )


@router.message(Command("topics"))
async def command_topics(message: Message, state: FSMContext, course: Course) -> None:
    await clear_stale_buttons(message.bot, message.chat.id, state)
    data = await state.get_data()
    language = get_language(data)
    locale = LOCALES[language]
    if not course.topic_groups:
        await message.answer(locale.topics_unavailable)
        return
    sent = await message.answer(
        locale.topics_prompt,
        reply_markup=_make_topic_buttons(
            course, get_selected_groups(data, course), language, locale
        ),
    )
    await remember_buttoned_message(state, sent)


@router.callback_query(F.data.startswith(TOGGLE_TOPIC_GROUP_PREFIX))
async def handle_toggle_topic_group(
    callback: CallbackQuery, state: FSMContext, course: Course
) -> None:
    assert callback.data is not None
    group_id = callback.data.removeprefix(TOGGLE_TOPIC_GROUP_PREFIX)
    data = await state.get_data()
    language = get_language(data)
    selected = get_selected_groups(data, course)
    if group_id in selected:
        selected.remove(group_id)
    elif group_id in course.topic_groups:
        selected.append(group_id)
    await state.update_data(topic_groups=selected)
    if isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(
            reply_markup=_make_topic_buttons(
                course, selected, language, LOCALES[language]
            )
        )
    await callback.answer()


@router.callback_query(F.data == TOPICS_DONE)
async def handle_topics_done(
    callback: CallbackQuery, state: FSMContext, course: Course
) -> None:
    data = await state.get_data()
    language = get_language(data)
    locale = LOCALES[language]
    selected = get_selected_groups(data, course)
    summary = (
        locale.topics_selected.format(
            topics=", ".join(
                group.title[language]
                for group_id, group in course.topic_groups.items()
                if group_id in selected
            )
        )
        if selected
        else locale.topics_all_selected
    )
    if isinstance(callback.message, Message):
        await callback.message.edit_text(summary, reply_markup=make_next_button(locale))
        await remember_buttoned_message(state, callback.message)
    await callback.answer()
