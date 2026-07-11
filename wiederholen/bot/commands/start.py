from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from wiederholen.bot.l10n import LOCALES, get_language

router = Router()


@router.message(Command("start"))
async def command_start(message: Message, state: FSMContext) -> None:
    language = get_language(await state.get_data())
    await message.answer(LOCALES[language].start)
