from aiogram.fsm.context import FSMContext
from aiogram.methods import EditMessageReplyMarkup

from tests.plugins.aiogram import FeedMessage
from wiederholen.bot.l10n import EN, RU


async def test_does_nothing_when_the_flag_is_not_configured_for_the_chat(
    feed_message: FeedMessage,
) -> None:
    requests = await feed_message("/ai")

    assert requests == []


async def test_does_nothing_when_the_chat_id_is_not_listed(
    feed_message: FeedMessage, chat_id: int
) -> None:
    requests = await feed_message(
        "/ai", feature_flags={"ai_exercises": frozenset({chat_id + 1})}
    )

    assert requests == []


async def test_turns_ai_mode_on(
    state: FSMContext, feed_message: FeedMessage, chat_id: int
) -> None:
    requests = await feed_message(
        "/ai", feature_flags={"ai_exercises": frozenset({chat_id})}
    )

    assert len(requests) == 1
    assert requests[0].text == RU.ai_mode_on
    data = await state.get_data()
    assert data["ai_mode"] is True


async def test_turns_ai_mode_off_on_the_second_call(
    state: FSMContext, feed_message: FeedMessage, chat_id: int
) -> None:
    flags = {"ai_exercises": frozenset({chat_id})}
    await feed_message("/ai", feature_flags=flags)

    requests = await feed_message("/ai", feature_flags=flags)

    assert requests[0].text == RU.ai_mode_off
    data = await state.get_data()
    assert data["ai_mode"] is False


async def test_responds_in_current_language(
    state: FSMContext, feed_message: FeedMessage, chat_id: int
) -> None:
    await state.update_data(language="en")

    requests = await feed_message(
        "/ai", feature_flags={"ai_exercises": frozenset({chat_id})}
    )

    assert requests[0].text == EN.ai_mode_on


async def test_clears_a_stale_button_left_from_wiederholen(
    state: FSMContext, feed_message: FeedMessage, chat_id: int
) -> None:
    await state.update_data(last_buttoned_message_id=77)

    requests = await feed_message(
        "/ai", feature_flags={"ai_exercises": frozenset({chat_id})}
    )

    edits = [r for r in requests if isinstance(r, EditMessageReplyMarkup)]
    assert len(edits) == 1
    assert edits[0].message_id == 77
