import datetime
from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from aiogram import Bot, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from wiederholen.bot import dispatcher as _dp


type MessageFactory = Callable[..., dict]
type FeedRawUpdate = Callable[..., Awaitable[list[Any]]]
type FeedCallbackQuery = Callable[..., Awaitable[list[Any]]]
type FeedMessage = Callable[..., Awaitable[list[Any]]]


@pytest.fixture
def bot_token() -> str:
    return "1234567890:AAHHte3GRDo4KzHsY6U6xZTMSfI7xv3c_xY"


@pytest.fixture
def bot(bot_token: str) -> Bot:
    return Bot(token=bot_token)


@pytest.fixture
def dispatcher() -> Dispatcher:
    return _dp


@pytest.fixture
def user_id() -> int:
    return 1


@pytest.fixture
def chat_id() -> int:
    return 1


@pytest.fixture
def message_factory(user_id: int, chat_id: int) -> MessageFactory:
    def factory(text: str, *, reply_to_message_id: int | None = None):
        message: dict = {
            "message_id": 1,
            "date": datetime.datetime.now(),
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": user_id, "is_bot": False, "first_name": "Test"},
            "text": text,
        }
        if reply_to_message_id is not None:
            message["reply_to_message"] = {
                "message_id": reply_to_message_id,
                "date": datetime.datetime.now(),
                "chat": {"id": chat_id, "type": "private"},
                "from": {"id": 123, "is_bot": True, "first_name": "Bot"},
                "text": "question",
            }
        return {"update_id": 1, "message": message}

    return factory


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
    user_id: int,
    chat_id: int,
) -> FeedCallbackQuery:
    async def factory(data: str | None, **kwargs) -> list[Any]:
        raw_update = {
            "update_id": 2,
            "callback_query": {
                "id": "test_callback_id",
                "from": {"id": user_id, "is_bot": False, "first_name": "Test"},
                "message": {
                    "message_id": 1,
                    "date": datetime.datetime.now(),
                    "chat": {"id": chat_id, "type": "private"},
                    "from": {"id": 123, "is_bot": True, "first_name": "Bot"},
                    "text": "question",
                },
                "chat_instance": "test",
                "data": data,
            },
        }
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
def _clear_storage(dispatcher: Dispatcher) -> None:
    # MemoryStorage.close() is a no-op, so clear its backing dict directly
    # to reset FSM state between tests (all tests share one dispatcher).
    storage = dispatcher.storage
    assert isinstance(storage, MemoryStorage)
    storage.storage.clear()
