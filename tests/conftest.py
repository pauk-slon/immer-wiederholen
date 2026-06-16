from collections.abc import Awaitable, Callable
import datetime
from unittest.mock import AsyncMock, patch

import pytest
from aiogram import Bot, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.methods import SendMessage
from aiogram.types import Chat, Message

from iwh.bot import dp as _dp


@pytest.fixture
def bot() -> Bot:
    return Bot(token="1234567890:AAHHte3GRDo4KzHsY6U6xZTMSfI7xv3c_xY")


@pytest.fixture
def dispatcher() -> Dispatcher:
    return _dp


@pytest.fixture
def user_id() -> int:
    return 1


@pytest.fixture
def chat_id() -> int:
    return 1


@pytest.fixture(autouse=True)
async def _clear_storage(dispatcher: Dispatcher) -> None:
    await dispatcher.storage.close()


type RawUpdateFactory = Callable[[str], dict]


@pytest.fixture
def raw_update_factory(user_id: int, chat_id: int) -> RawUpdateFactory:
    def factory(text: str):
        return {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "date": datetime.datetime.now(),
                "chat": {"id": chat_id, "type": "private"},
                "from": {"id": user_id, "is_bot": False, "first_name": "Test"},
                "text": text,
            },
        }

    return factory


type FeedRawUpdate = Callable[..., Awaitable[SendMessage]]


@pytest.fixture
def feed_raw_update(
    bot: Bot,
    dispatcher: Dispatcher,
    raw_update_factory: RawUpdateFactory,
) -> FeedRawUpdate:
    async def factory(text: str, **kwargs):
        mock_request = AsyncMock(
            return_value=Message(
                message_id=2,
                date=datetime.datetime.now(),
                chat=Chat(id=1, type="private"),
            ),
        )
        with patch.object(bot.session, "make_request", mock_request):
            await dispatcher.feed_raw_update(bot, raw_update_factory(text), **kwargs)
        mock_request.assert_called_once()
        return mock_request.call_args.args[1]

    return factory


@pytest.fixture
def state(bot: Bot, dispatcher: Dispatcher, user_id: int, chat_id: int) -> FSMContext:
    return FSMContext(
        storage=dispatcher.storage,
        key=StorageKey(bot_id=bot.id, chat_id=chat_id, user_id=user_id),
    )
