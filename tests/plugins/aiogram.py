import os
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock, patch
from urllib.parse import urlsplit, urlunsplit

import pytest
from aiogram import Bot, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey

from wiederholen.bot import dispatcher as _dp
from wiederholen.bot.bootstrap import load_storage
from wiederholen.bot.redis_storage import ScanningRedisStorage

from .telegram import CallbackQueryFactory, MessageFactory

type FeedRawUpdate = Callable[..., Awaitable[list[Any]]]
type FeedCallbackQuery = Callable[..., Awaitable[list[Any]]]
type FeedMessage = Callable[..., Awaitable[list[Any]]]


def _db_override(value: str) -> int | None:
    if not value:
        return None
    return int(value)


def pytest_addoption(parser):
    parser.addoption(
        "--fsm-storage-db-override",
        action="store",
        type=_db_override,
    )


def pytest_configure(config) -> None:
    if (db_override := config.getoption("--fsm-storage-db-override")) is None:
        return
    fsm_storage_url = os.environ["FSM_STORAGE_URL"]
    os.environ["FSM_STORAGE_URL"] = urlunsplit(
        urlsplit(fsm_storage_url)._replace(path=f"/{db_override}"),
    )


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


@pytest.fixture
async def redis_storage() -> AsyncIterator[ScanningRedisStorage]:
    storage = load_storage()
    await storage.redis.flushdb()
    yield storage
    await storage.close()


@pytest.fixture(autouse=True)
def _reset_storage(dispatcher: Dispatcher, redis_storage: ScanningRedisStorage) -> None:
    dispatcher.fsm.storage = redis_storage
