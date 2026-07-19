import re
from collections.abc import AsyncIterator
from typing import Any, Self, cast

from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.redis import RedisStorage


class ScanningRedisStorage(RedisStorage):
    _CHAT_ID_MARKER = "\x00CHAT_ID\x00"
    _USER_ID_MARKER = "\x00USER_ID\x00"

    @classmethod
    def from_url(
        cls,
        url: str,
        connection_kwargs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Self:
        # RedisStorage.from_url is annotated to return RedisStorage, not Self.
        return cast(Self, super().from_url(url, connection_kwargs, **kwargs))

    def _scan_pattern_and_regex(self, bot_id: int) -> tuple[str, re.Pattern[str]]:
        marker_key = StorageKey(
            bot_id=bot_id,
            chat_id=self._CHAT_ID_MARKER,  # ty: ignore[invalid-argument-type]
            user_id=self._USER_ID_MARKER,  # ty: ignore[invalid-argument-type]
        )
        built = self.key_builder.build(marker_key, "data")
        pattern = built.replace(self._CHAT_ID_MARKER, "*").replace(
            self._USER_ID_MARKER, "*"
        )
        regex_source = (
            re.escape(built)
            .replace(re.escape(self._CHAT_ID_MARKER), r"(?P<chat_id>-?\d+)")
            .replace(re.escape(self._USER_ID_MARKER), r"-?\d+")
        )
        return pattern, re.compile(regex_source)

    async def iter_fsm_data(self, bot_id: int) -> AsyncIterator[tuple[int, dict]]:
        pattern, chat_id_regex = self._scan_pattern_and_regex(bot_id)
        seen: set[int] = set()
        async for raw_key in self.redis.scan_iter(match=pattern):
            key = raw_key.decode() if isinstance(raw_key, bytes) else raw_key
            match = chat_id_regex.fullmatch(key)
            if match is None:
                continue
            chat_id = int(match.group("chat_id"))
            if chat_id in seen:
                continue
            seen.add(chat_id)
            storage_key = StorageKey(bot_id=bot_id, chat_id=chat_id, user_id=chat_id)
            data = await self.get_data(storage_key)
            yield chat_id, data
