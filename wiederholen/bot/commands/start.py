from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from opentelemetry import trace

from wiederholen.bot.commands.topics import describe_selected_groups
from wiederholen.bot.commands.wiederholen import make_next_button
from wiederholen.bot.l10n import LOCALES, get_language
from wiederholen.bot.pending_buttons import (
    clear_stale_buttons,
    remember_buttoned_message,
)
from wiederholen.school import LANGUAGES, Course, Language

router = Router()


def _parse_payload(
    payload: str | None, course: Course
) -> tuple[Language, list[str]] | None:
    # "ru" or "ru-verb_government-prepositions": the language, then topic
    # groups. Group ids have no "-". A group that the course doesn't have is
    # skipped, so a broken link gives a usual start
    if payload is None:
        return None
    language, *group_ids = payload.split("-")
    if language not in LANGUAGES:
        return None
    return language, [
        group_id for group_id in course.topic_groups if group_id in group_ids
    ]


@router.message(Command("start"))
async def command_start(
    message: Message, state: FSMContext, command: CommandObject, course: Course
) -> None:
    # A "start the bot" link can carry a language and topic groups as the
    # deep-link payload (t.me/<bot>?start=en-nouns), which Telegram delivers
    # as this command's args. The landing site links to the bot this way, so
    # that a learner continues with the topics of the page (#345).
    # The payload only sets up a new chat, one the bot stores nothing about
    # yet. It never changes the settings of a learner who already uses the
    # bot, because links in the docs or the README carry a payload too
    # (#282, ADR 0019, ADR 0029). A missing "language" key isn't enough to
    # tell: a learner who never ran /language uses the default without
    # storing it.
    data = await state.get_data()
    span = trace.get_current_span()
    span.set_attribute("telegram.start.new_chat", not data)
    parsed = None if data else _parse_payload(command.args, course)
    if parsed is None:
        language, groups = get_language(data), []
    else:
        language, groups = parsed
        span.set_attribute("telegram.start.language", language)
        if groups:
            await state.update_data(language=language, topic_groups=groups)
            # Only ids that the course has, never text from the link itself
            span.set_attribute("telegram.start.topic_groups", groups)
        else:
            await state.update_data(language=language)
    await clear_stale_buttons(message.bot, message.chat.id, state)
    locale = LOCALES[language]
    text = locale.start
    if groups:
        text += (
            f"\n\n{describe_selected_groups(course, groups, language)}"
            f"\n{locale.topics_change_hint}"
        )
    sent = await message.answer(text, reply_markup=make_next_button(locale))
    await remember_buttoned_message(state, sent)
