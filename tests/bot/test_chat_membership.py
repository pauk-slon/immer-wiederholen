from aiogram.fsm.context import FSMContext

from tests.plugins.aiogram import FeedRawUpdate
from tests.plugins.telegram import MyChatMemberFactory


async def test_blocking_the_bot_is_remembered(
    state: FSMContext,
    feed_raw_update: FeedRawUpdate,
    my_chat_member_factory: MyChatMemberFactory,
) -> None:
    await state.update_data(language="en")

    requests = await feed_raw_update(my_chat_member_factory("member", "kicked"))

    assert requests == []
    assert await state.get_data() == {"language": "en", "bot_blocked": True}


async def test_unblocking_the_bot_forgets_it(
    state: FSMContext,
    feed_raw_update: FeedRawUpdate,
    my_chat_member_factory: MyChatMemberFactory,
) -> None:
    await state.update_data(language="en", bot_blocked=True)

    requests = await feed_raw_update(my_chat_member_factory("kicked", "member"))

    assert requests == []
    assert await state.get_data() == {"language": "en"}
