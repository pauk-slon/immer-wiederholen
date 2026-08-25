from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from wiederholen.bot.l10n import LOCALES, get_language
from wiederholen.bot.pending_buttons import clear_stale_buttons

router = Router()


@router.message(Command("language"))
async def command_language(message: Message, state: FSMContext) -> None:
    await clear_stale_buttons(message.bot, message.chat.id, state)
    language = get_language(await state.get_data())
    new_language = "en" if language == "ru" else "ru"
    await state.update_data(language=new_language)
    await message.answer(LOCALES[new_language].start)
