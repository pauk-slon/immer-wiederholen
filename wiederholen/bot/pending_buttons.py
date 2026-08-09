"""Tracks the one message (if any) that still has an inline keyboard attached
to it, so any command entry point can strip it before doing anything else.

A callback handler (tapping "Следующее задание"/"Закрепить"/etc.) already
gets a reference to the exact message its button lives on and clears it
directly via `edit_reply_markup`. A plain command (`/wiederholen`,
`/progress`, `/reset`, `/language`) gets no such reference — Telegram never
tells a bot which earlier message a command "replaces" — so without this,
typing a command instead of tapping a button leaves that button visibly
attached to the old message forever.

The fix: remember the message_id of the most recently sent buttoned message
in FSM state, and have every command entry point clear it proactively before
doing anything else. Only one id is ever tracked at a time — a chat only
ever has at most one live set of buttons pending a tap, since sending a new
one (or a command handler clearing the old one) always supersedes it.
"""

from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message


async def remember_buttoned_message(state: FSMContext, message: Message) -> None:
    await state.update_data(last_buttoned_message_id=message.message_id)


async def forget_buttoned_message(state: FSMContext) -> None:
    await state.update_data(last_buttoned_message_id=None)


async def clear_stale_buttons(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    message_id = data.get("last_buttoned_message_id")
    if message_id is None:
        return
    bot = message.bot
    assert bot is not None
    try:
        await bot.edit_message_reply_markup(
            chat_id=message.chat.id, message_id=message_id, reply_markup=None
        )
    except TelegramBadRequest:
        # Already edited/deleted, or too old to edit — nothing to clean up.
        pass
    await forget_buttoned_message(state)
