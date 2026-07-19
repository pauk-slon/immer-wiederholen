import json
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

from aiogram.fsm.storage.base import DefaultKeyBuilder, KeyBuilder, StorageKey
from redis.asyncio import Redis

from wiederholen.bot.redis_storage import ScanningRedisStorage


def _storage_with_keys(
    *keys: str | bytes, key_builder: KeyBuilder | None = None
) -> ScanningRedisStorage:
    async def fake_scan_iter(match: str) -> AsyncIterator[str | bytes]:
        for key in keys:
            yield key

    redis = MagicMock(spec=Redis)
    redis.scan_iter = fake_scan_iter
    redis.get = AsyncMock(return_value=json.dumps({"marker": True}))
    return ScanningRedisStorage(redis=redis, key_builder=key_builder)


async def test_iter_fsm_data_parses_chat_id_from_key() -> None:
    storage = _storage_with_keys("fsm:111:111:data")

    results = [item async for item in storage.iter_fsm_data(bot_id=1)]

    assert results == [(111, {"marker": True})]


async def test_iter_fsm_data_decodes_bytes_keys() -> None:
    storage = _storage_with_keys(b"fsm:111:111:data")

    chat_ids = [chat_id async for chat_id, _ in storage.iter_fsm_data(bot_id=1)]

    assert chat_ids == [111]


async def test_iter_fsm_data_deduplicates_multiple_fields_per_chat() -> None:
    # a real chat has "data"/"state"/"lock" keys, but our scan pattern only
    # matches "data" keys anyway — dedup still guards against repeats.
    storage = _storage_with_keys("fsm:111:111:data", "fsm:111:111:data")

    chat_ids = [chat_id async for chat_id, _ in storage.iter_fsm_data(bot_id=1)]

    assert chat_ids == [111]


async def test_iter_fsm_data_handles_multiple_chats() -> None:
    storage = _storage_with_keys("fsm:111:111:data", "fsm:222:222:data")

    chat_ids = [chat_id async for chat_id, _ in storage.iter_fsm_data(bot_id=1)]

    assert sorted(chat_ids) == [111, 222]


async def test_iter_fsm_data_skips_keys_that_do_not_match_the_regex() -> None:
    # defensive: scan_iter's glob match is looser than our derived regex, so
    # a key matching the glob but not the exact shape must be skipped rather
    # than raising.
    storage = _storage_with_keys("fsm:not-an-int:111:data", "fsm:111:111:data")

    chat_ids = [chat_id async for chat_id, _ in storage.iter_fsm_data(bot_id=1)]

    assert chat_ids == [111]


async def test_iter_fsm_data_adapts_to_a_differently_shaped_key_builder() -> None:
    # the pattern/parsing are derived from key_builder.build() itself, not
    # hardcoded — this should keep working even if the key shape changes,
    # e.g. when bot_id is included (for sharing one Redis across bots).
    key_builder = DefaultKeyBuilder(with_bot_id=True)
    real_key = key_builder.build(StorageKey(bot_id=999, chat_id=42, user_id=42), "data")
    storage = _storage_with_keys(real_key, key_builder=key_builder)

    chat_ids = [chat_id async for chat_id, _ in storage.iter_fsm_data(bot_id=999)]

    assert chat_ids == [42]
