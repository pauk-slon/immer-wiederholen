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
    # A landing page's "start the bot" link can carry a language as the
    # deep-link payload (t.me/<bot>?start=en), which Telegram delivers as
    # this command's args. A valid payload sets/overrides the stored
    # language outright, matching what the learner just clicked; anything
    # else (no payload, or a payload that isn't a known language) falls
    # back to whatever language was already stored, same as before this
    # existed.
    if command.args in LANGUAGES:
        language = command.args
        await state.update_data(language=language)
    else:
        language = get_language(await state.get_data())
    await message.answer(LOCALES[language].start)
