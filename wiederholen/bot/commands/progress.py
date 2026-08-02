from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from wiederholen.bot.l10n import LOCALES, format_count, get_language
from wiederholen.tutoring import Course, Tutor

router = Router()


@router.message(Command("progress"))
async def command_progress(
    message: Message,
    state: FSMContext,
    course: Course,
) -> None:
    data = await state.get_data()
    language = get_language(data)
    journal = data.get("journal", {})
    progress = Tutor(course, journal).progress()
    await message.answer(
        LOCALES[language].progress_text.format(
            remaining_today=format_count(progress.remaining_today, "exercises", language),
            new_today=format_count(progress.new_today, "words", language),
            learning=format_count(progress.learning, "words", language),
            mastered=format_count(progress.mastered, "words", language),
        )
    )
