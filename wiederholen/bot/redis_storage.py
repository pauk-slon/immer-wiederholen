from collections.abc import Mapping
from typing import Any, cast

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StateType, StorageKey

from wiederholen.students import StudentStore


class AiogramFsmStorage(BaseStorage):
    """Thin aiogram `BaseStorage` adapter over `StudentStore` — the only piece
    of this codebase that still knows aiogram's `StorageKey` shape. Everything
    it stores lives in `StudentStore` under the plain `str(chat_id)` a Telegram
    private chat already uniquely identifies (bot_id/user_id are dropped, same
    as this bot has always effectively assumed).

    aiogram's own state-name concept (the `UserState.answering`/`.recalling`
    a router filters on) is folded into the same per-student JSON blob
    `StudentStore` already holds the rest of the data in, under one reserved
    key, rather than a separate Redis key the way aiogram's own `RedisStorage`
    keeps it — `get_data()`/`set_data()` read/write around it so callers never
    see it. This isn't materially less atomic than today: `BaseStorage.
    update_data()` (which every `state.update_data(...)` call in
    `wiederholen.bot.commands` goes through) is itself already an unguarded
    get-then-set over `get_data`/`set_data`, so folding state into the same
    blob doesn't introduce a race that wasn't already there.
    """

    _STATE_FIELD = "__state__"

    def __init__(self, store: StudentStore) -> None:
        self.store = store

    @staticmethod
    def _student_id(key: StorageKey) -> str:
        return str(key.chat_id)

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        data = await self.store.get(self._student_id(key))
        data.pop(self._STATE_FIELD, None)
        return data

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        student_id = self._student_id(key)
        current = await self.store.get(student_id)
        new_data = dict(data)
        if self._STATE_FIELD in current:
            new_data[self._STATE_FIELD] = current[self._STATE_FIELD]
        await self.store.set(student_id, new_data)

    async def get_state(self, key: StorageKey) -> str | None:
        data = await self.store.get(self._student_id(key))
        return cast(str | None, data.get(self._STATE_FIELD))

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        student_id = self._student_id(key)
        data = await self.store.get(student_id)
        if state is None:
            data.pop(self._STATE_FIELD, None)
        else:
            data[self._STATE_FIELD] = state.state if isinstance(state, State) else state
        await self.store.set(student_id, data)

    async def close(self) -> None:
        await self.store.close()
