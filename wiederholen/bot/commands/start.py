from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from wiederholen.bot.l10n import LOCALES, get_language
from wiederholen.school import LANGUAGES

router = Router()


@router.message(Command("start"))
async def command_start(
    message: Message, state: FSMContext, command: CommandObject
) -> None:
    # A "start the bot" link can carry a language as the deep-link payload
    # (t.me/<bot>?start=en), which Telegram delivers as this command's args.
    # The payload only picks the starting language of a new chat, one the bot
    # stores nothing about yet. It never changes the language of a learner
    # who already uses the bot, because links in the docs or the README carry
    # a payload too (#282). A missing "language" key isn't enough to tell: a
    # learner who never ran /language uses the default without storing it.
    data = await state.get_data()
    if not data and command.args in LANGUAGES:
        language = command.args
        await state.update_data(language=language)
    else:
        language = get_language(data)
    await message.answer(LOCALES[language].start)
