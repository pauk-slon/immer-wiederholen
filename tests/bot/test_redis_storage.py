from aiogram.fsm.storage.base import StorageKey

from wiederholen.bot.redis_storage import ScanningRedisStorage


async def test_iter_fsm_data_parses_chat_id_from_key(
    redis_storage: ScanningRedisStorage,
) -> None:
    key = StorageKey(bot_id=1, chat_id=111, user_id=111)
    await redis_storage.set_data(key, {"marker": True})

    results = [item async for item in redis_storage.iter_fsm_data(bot_id=1)]

    assert results == [(111, {"marker": True})]


async def test_iter_fsm_data_handles_multiple_chats(
    redis_storage: ScanningRedisStorage,
) -> None:
    await redis_storage.set_data(
        StorageKey(bot_id=1, chat_id=111, user_id=111), {"marker": True}
    )
    await redis_storage.set_data(
        StorageKey(bot_id=1, chat_id=222, user_id=222), {"marker": True}
    )

    chat_ids = [chat_id async for chat_id, _ in redis_storage.iter_fsm_data(bot_id=1)]

    assert sorted(chat_ids) == [111, 222]


async def test_iter_fsm_data_ignores_state_and_lock_keys(
    redis_storage: ScanningRedisStorage,
) -> None:
    # set_state() writes a "state" key next to "data" for the same chat —
    # only "data" keys should ever surface.
    key = StorageKey(bot_id=1, chat_id=111, user_id=111)
    await redis_storage.set_data(key, {"marker": True})
    await redis_storage.set_state(key, "some-state")

    results = [item async for item in redis_storage.iter_fsm_data(bot_id=1)]

    assert results == [(111, {"marker": True})]


async def test_iter_fsm_data_deduplicates_same_chat_id_across_keys(
    redis_storage: ScanningRedisStorage,
) -> None:
    # two distinct real keys that both parse to chat_id 111 (differing only
    # in the user_id segment, which our pattern doesn't capture) must only
    # yield that chat once.
    await redis_storage.redis.set("fsm:111:222:data", '{"marker": true}')
    await redis_storage.redis.set("fsm:111:333:data", '{"marker": true}')

    chat_ids = [chat_id async for chat_id, _ in redis_storage.iter_fsm_data(bot_id=1)]

    assert chat_ids == [111]


async def test_iter_fsm_data_skips_a_key_that_does_not_match_the_regex(
    redis_storage: ScanningRedisStorage,
) -> None:
    # a key that happens to match the glob but not the stricter regex must
    # be skipped defensively rather than raising.
    await redis_storage.redis.set("fsm:not-an-int:111:data", "{}")
    await redis_storage.set_data(
        StorageKey(bot_id=1, chat_id=111, user_id=111), {"marker": True}
    )

    chat_ids = [chat_id async for chat_id, _ in redis_storage.iter_fsm_data(bot_id=1)]

    assert chat_ids == [111]
