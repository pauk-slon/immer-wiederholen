from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from wiederholen.bot.l10n import LOCALES, get_language
from wiederholen.exercises import School

router = Router()


@router.message(Command("progress"))
async def command_progress(
    message: Message,
    state: FSMContext,
    school: School,
) -> None:
    data = await state.get_data()
    language = get_language(data)
    journal = data.get("journal", {})
    progress = school(journal).progress()
    await message.answer(
        LOCALES[language].progress_text.format(
            due=progress.due,
            new=progress.new,
            learning=progress.learning,
            mastered=progress.mastered,
            total=progress.total,
        )
    )
