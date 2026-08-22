from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from wiederholen.bot.commands.wiederholen import make_next_button
from wiederholen.bot.l10n import LOCALES, format_count, get_language
from wiederholen.bot.pending_buttons import (
    clear_stale_buttons,
    remember_buttoned_message,
)
from wiederholen.journal_store import JournalStore
from wiederholen.tutoring import Course, Tutor

router = Router()


@router.message(Command("progress"))
async def command_progress(
    message: Message,
    state: FSMContext,
    course: Course,
    journal_store: JournalStore,
) -> None:
    await clear_stale_buttons(message, state)
    data = await state.get_data()
    language = get_language(data)
    locale = LOCALES[language]
    # progress() is read-only (see wiederholen.tutoring.session) — open()
    # detects that nothing changed and skips the write on its own.
    async with journal_store.check_out(str(message.chat.id)) as journal:
        progress = Tutor(course, journal).progress()
    sent = await message.answer(
        locale.progress_text.format(
            remaining_today=format_count(
                progress.remaining_today,
                "exercises",
                language,
            ),
            new_today=format_count(progress.new_today, "words", language),
            learning=format_count(progress.learning, "words", language),
            mastered=format_count(progress.mastered, "words", language),
            answered_today=format_count(
                progress.answered_today,
                "exercises",
                language,
            ),
            answered_count=progress.answered_today,
            correct_today=progress.correct_today,
        ),
        reply_markup=make_next_button(locale),
    )
    await remember_buttoned_message(state, sent)
