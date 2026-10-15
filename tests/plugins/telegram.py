import datetime
from collections.abc import Callable

import pytest

type MessageFactory = Callable[..., dict]
type CallbackQueryFactory = Callable[..., dict]
type MyChatMemberFactory = Callable[..., dict]


@pytest.fixture
def telegram_bot_token() -> str:
    return "1234567890:AAHHte3GRDo4KzHsY6U6xZTMSfI7xv3c_xY"


@pytest.fixture
def telegram_user_id() -> int:
    return 1


@pytest.fixture
def chat_id() -> int:
    return 1


@pytest.fixture
def message_factory(telegram_user_id: int, chat_id: int) -> MessageFactory:
    def factory(text: str, *, reply_to_message_id: int | None = None):
        message: dict = {
            "message_id": 1,
            "date": datetime.datetime.now(tz=datetime.UTC),
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": telegram_user_id, "is_bot": False, "first_name": "Test"},
            "text": text,
        }
        if reply_to_message_id is not None:
            message["reply_to_message"] = {
                "message_id": reply_to_message_id,
                "date": datetime.datetime.now(tz=datetime.UTC),
                "chat": {"id": chat_id, "type": "private"},
                "from": {"id": 123, "is_bot": True, "first_name": "Bot"},
                "text": "question",
            }
        return {"update_id": 1, "message": message}

    return factory


@pytest.fixture
def callback_query_factory(telegram_user_id: int, chat_id: int) -> CallbackQueryFactory:
    def factory(data: str | None) -> dict:
        return {
            "update_id": 2,
            "callback_query": {
                "id": "test_callback_id",
                "from": {"id": telegram_user_id, "is_bot": False, "first_name": "Test"},
                "message": {
                    "message_id": 1,
                    "date": datetime.datetime.now(tz=datetime.UTC),
                    "chat": {"id": chat_id, "type": "private"},
                    "from": {"id": 123, "is_bot": True, "first_name": "Bot"},
                    "text": "question",
                },
                "chat_instance": "test",
                "data": data,
            },
        }

    return factory


@pytest.fixture
def my_chat_member_factory(telegram_user_id: int, chat_id: int) -> MyChatMemberFactory:
    # What Telegram sends when a learner blocks ("kicked") or unblocks
    # ("member") the bot in a private chat.
    def factory(old_status: str, new_status: str) -> dict:
        bot_user = {"id": 123, "is_bot": True, "first_name": "Bot"}

        def member(status: str) -> dict:
            # A block is a "kicked" status with until_date=0 — i.e. forever.
            extra = {"until_date": 0} if status == "kicked" else {}
            return {"status": status, "user": bot_user, **extra}

        return {
            "update_id": 3,
            "my_chat_member": {
                "chat": {"id": chat_id, "type": "private"},
                "from": {"id": telegram_user_id, "is_bot": False, "first_name": "Test"},
                "date": datetime.datetime.now(tz=datetime.UTC),
                "old_chat_member": member(old_status),
                "new_chat_member": member(new_status),
            },
        }

    return factory
