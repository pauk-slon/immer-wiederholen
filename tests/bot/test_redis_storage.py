from unittest.mock import AsyncMock, patch

from aiogram.fsm.storage.base import StorageKey

from wiederholen.bot.redis_storage import AiogramFsmStorage

KEY = StorageKey(bot_id=1, chat_id=111, user_id=111)
OTHER_CHAT_KEY = StorageKey(bot_id=1, chat_id=222, user_id=222)


async def test_get_data_is_empty_for_an_unknown_key(
    redis_storage: AiogramFsmStorage,
) -> None:
    assert await redis_storage.get_data(KEY) == {}


async def test_set_data_roundtrips_through_get_data(
    redis_storage: AiogramFsmStorage,
) -> None:
    await redis_storage.set_data(KEY, {"marker": True})

    assert await redis_storage.get_data(KEY) == {"marker": True}


async def test_data_is_addressed_by_chat_id_only(
    redis_storage: AiogramFsmStorage,
) -> None:
    # bot_id/user_id are dropped — a private chat's chat_id already uniquely
    # identifies it, and this is what lets AiogramFsmStorage and StudentStore
    # agree on the exact same student_id for a given chat.
    await redis_storage.set_data(KEY, {"marker": True})
    await redis_storage.set_data(OTHER_CHAT_KEY, {"marker": False})

    assert await redis_storage.get_data(KEY) == {"marker": True}
    assert await redis_storage.get_data(OTHER_CHAT_KEY) == {"marker": False}


async def test_get_state_is_none_for_an_unknown_key(
    redis_storage: AiogramFsmStorage,
) -> None:
    assert await redis_storage.get_state(KEY) is None


async def test_set_state_roundtrips_through_get_state(
    redis_storage: AiogramFsmStorage,
) -> None:
    await redis_storage.set_state(KEY, "some-state")

    assert await redis_storage.get_state(KEY) == "some-state"


async def test_set_state_none_clears_it(redis_storage: AiogramFsmStorage) -> None:
    await redis_storage.set_state(KEY, "some-state")

    await redis_storage.set_state(KEY, None)

    assert await redis_storage.get_state(KEY) is None


async def test_state_and_data_are_independent(
    redis_storage: AiogramFsmStorage,
) -> None:
    await redis_storage.set_data(KEY, {"marker": True})
    await redis_storage.set_state(KEY, "some-state")

    assert await redis_storage.get_data(KEY) == {"marker": True}
    assert await redis_storage.get_state(KEY) == "some-state"

    await redis_storage.set_data(KEY, {"marker": False})

    # Overwriting data must not clobber the state stashed alongside it in the
    # same underlying blob (see AiogramFsmStorage's own docstring).
    assert await redis_storage.get_state(KEY) == "some-state"


async def test_close_closes_the_underlying_student_store(
    redis_storage: AiogramFsmStorage,
) -> None:
    with patch.object(redis_storage.store, "close", AsyncMock()) as mock_close:
        await redis_storage.close()

    mock_close.assert_awaited_once()


async def test_underlying_student_store_holds_data_and_state_together(
    redis_storage: AiogramFsmStorage,
) -> None:
    # The underlying StudentStore is the one thing a future non-Telegram
    # frontend would read directly — confirm AiogramFsmStorage really does
    # write through it rather than keeping any state of its own.
    await redis_storage.set_data(KEY, {"marker": True})
    await redis_storage.set_state(KEY, "some-state")

    assert await redis_storage.store.get("111") == {
        "marker": True,
        AiogramFsmStorage._STATE_FIELD: "some-state",
    }
