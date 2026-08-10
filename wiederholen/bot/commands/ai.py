from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from wiederholen.bot.feature_flags import has_feature
from wiederholen.bot.l10n import LOCALES, get_language
from wiederholen.bot.pending_buttons import clear_stale_buttons

router = Router()


@router.message(Command("ai"))
async def command_ai(
    message: Message,
    state: FSMContext,
    feature_flags: dict[str, frozenset[int]] | None = None,
) -> None:
    # Not registered in setMyCommands and no-ops for anyone the flag doesn't
    # cover — same invisible-to-everyone-else shape as the flag mechanism's
    # other check points (see feature_flags.py).
    if not has_feature(feature_flags or {}, "ai_exercises", message.chat.id):
        return
    await clear_stale_buttons(message, state)
    data = await state.get_data()
    locale = LOCALES[get_language(data)]
    ai_mode = not data.get("ai_mode", False)
    await state.update_data(ai_mode=ai_mode)
    await message.answer(locale.ai_mode_on if ai_mode else locale.ai_mode_off)
