from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from aiogram import Bot, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from wiederholen.bot import dispatcher as _dp

from .telegram import CallbackQueryFactory, MessageFactory


type FeedRawUpdate = Callable[..., Awaitable[list[Any]]]
type FeedCallbackQuery = Callable[..., Awaitable[list[Any]]]
type FeedMessage = Callable[..., Awaitable[list[Any]]]


@pytest.fixture
def bot(bot_token: str) -> Bot:
    return Bot(token=bot_token)


@pytest.fixture
def dispatcher() -> Dispatcher:
    return _dp


@pytest.fixture
def feed_raw_update(bot: Bot, dispatcher: Dispatcher) -> FeedRawUpdate:
    async def factory(raw_update: dict, **kwargs) -> list[Any]:
        mock_request = AsyncMock(return_value=True)
        with patch.object(bot.session, "make_request", mock_request):
            await dispatcher.feed_raw_update(bot, raw_update, **kwargs)
        return [call.args[1] for call in mock_request.call_args_list]

    return factory


@pytest.fixture
def feed_callback_query(
    feed_raw_update: FeedRawUpdate,
    callback_query_factory: CallbackQueryFactory,
) -> FeedCallbackQuery:
    async def factory(data: str | None, **kwargs) -> list[Any]:
        raw_update = callback_query_factory(data)
        return await feed_raw_update(raw_update, **kwargs)

    return factory


@pytest.fixture
def feed_message(
    feed_raw_update: FeedRawUpdate,
    message_factory: MessageFactory,
) -> FeedMessage:
    async def factory(
        text: str, *, reply_to_message_id: int | None = None, **kwargs
    ) -> list[Any]:
        raw_update = message_factory(text, reply_to_message_id=reply_to_message_id)
        return await feed_raw_update(raw_update, **kwargs)

    return factory


@pytest.fixture
def state(bot: Bot, dispatcher: Dispatcher, user_id: int, chat_id: int) -> FSMContext:
    return FSMContext(
        storage=dispatcher.storage,
        key=StorageKey(bot_id=bot.id, chat_id=chat_id, user_id=user_id),
    )


@pytest.fixture(autouse=True)
def _reset_storage(dispatcher: Dispatcher) -> None:
    # Force a fresh in-memory store for every test, regardless of what
    # backend the dispatcher was actually configured with (e.g. FSM_STORAGE_URL
    # set in the environment) — tests must stay fast and isolated.
    dispatcher.fsm.storage = MemoryStorage()
