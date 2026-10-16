from typing import Any, Final

from aiogram import Router
from aiogram.filters import KICKED, MEMBER, ChatMemberUpdatedFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import ChatMemberUpdated

router = Router()

# FSM data key: True once the learner has blocked the bot. Bot API has no way
# to ask "am I blocked?" — Telegram only tells us via a my_chat_member update
# (status "kicked" in a private chat) or a 403 on the next send, so both paths
# record it here and the reminder worker reads it back to skip the chat.
BOT_BLOCKED: Final = "bot_blocked"


def is_bot_blocked(state_data: dict[str, Any]) -> bool:
    return bool(state_data.get(BOT_BLOCKED))


async def mark_bot_blocked(state: FSMContext) -> None:
    await state.update_data({BOT_BLOCKED: True})


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=KICKED))
async def handle_bot_blocked(event: ChatMemberUpdated, state: FSMContext) -> None:
    await mark_bot_blocked(state)


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=MEMBER))
async def handle_bot_unblocked(event: ChatMemberUpdated, state: FSMContext) -> None:
    data = await state.get_data()
    data.pop(BOT_BLOCKED, None)
    await state.set_data(data)
