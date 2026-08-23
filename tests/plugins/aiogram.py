import itertools
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch
from urllib.parse import urlsplit, urlunsplit

import pytest
from aiogram import Bot, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.methods import SendMessage, TelegramMethod
from aiogram.types import Chat, Message

from wiederholen.bot import dispatcher as _dp

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
        "--redis-db-override",
        action="store",
        type=_db_override,
    )


def pytest_configure(config) -> None:
    if (db_override := config.getoption("--redis-db-override")) is None:
        return
    # All three env vars point at the same physical Redis/Valkey in dev/prod
    # today (see CLAUDE.md's Persistence section) — pin all of them to the
    # same dedicated test DB, so RedisStorage/RedisStudentRecordBook/
    # WebSessionStore can never touch a DB a real dev/prod bot might be
    # using, regardless of what's set in the environment.
    for env_var in (
        "BOT_FSM_STORAGE_URL",
        "STUDENT_RECORD_STORAGE_URL",
        "WEB_SESSION_STORAGE_URL",
    ):
        os.environ[env_var] = urlunsplit(
            urlsplit(os.environ[env_var])._replace(path=f"/{db_override}"),
        )


@pytest.fixture
def bot(bot_token: str) -> Bot:
    return Bot(token=bot_token)


@pytest.fixture
def dispatcher() -> Dispatcher:
    return _dp


@pytest.fixture
def feed_raw_update(bot: Bot, dispatcher: Dispatcher) -> FeedRawUpdate:
    # A real SendMessage response carries the message_id Telegram assigned it —
    # handlers that remember it (to strip a stale button later) need a
    # realistic fake here, not the bare `True` every other method still gets.
    sent_message_ids = itertools.count(1000)

    def make_fake_response(method: TelegramMethod) -> Any:
        if isinstance(method, SendMessage):
            assert isinstance(method.chat_id, int)
            return Message(
                message_id=next(sent_message_ids),
                date=datetime.now(tz=UTC),
                chat=Chat(id=method.chat_id, type="private"),
            )
        return True

    async def factory(raw_update: dict, **kwargs) -> list[Any]:
        mock_request = AsyncMock(
            side_effect=lambda bot, method, timeout=None: make_fake_response(method)
        )
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
async def redis_storage() -> AsyncIterator[RedisStorage]:
    storage = RedisStorage.from_url(os.environ["BOT_FSM_STORAGE_URL"])
    await storage.redis.flushdb()
    yield storage
    await storage.close()


@pytest.fixture(autouse=True)
def _reset_storage(dispatcher: Dispatcher, redis_storage: RedisStorage) -> None:
    dispatcher.fsm.storage = redis_storage
