import hashlib
import hmac
from collections.abc import Callable
from datetime import UTC, datetime
from typing import NotRequired, Unpack

import pytest
from typing_extensions import TypedDict


class TelegramLoginPayload(TypedDict, closed=True):
    id: str
    first_name: str
    auth_date: str
    hash: str
    last_name: NotRequired[str]
    username: NotRequired[str]
    photo_url: NotRequired[str]


class TelegramLoginKwargs(TypedDict, total=False):
    id: str
    first_name: str
    auth_date: str
    last_name: str
    username: str
    photo_url: str


type TelegramLoginPayloadFactory = Callable[..., TelegramLoginPayload]


@pytest.fixture
def telegram_login_payload_factory(
    telegram_bot_token: str,
    telegram_user_id: int,
) -> TelegramLoginPayloadFactory:
    def factory(**kwargs: Unpack[TelegramLoginKwargs]) -> TelegramLoginPayload:
        payload = TelegramLoginPayload(
            id=kwargs.get("id", str(telegram_user_id)),
            first_name=kwargs.get("first_name", "Test"),
            auth_date=kwargs.get("auth_date", str(int(datetime.now(UTC).timestamp()))),
            hash="",
        )
        if "last_name" in kwargs:
            payload["last_name"] = kwargs["last_name"]
        if "username" in kwargs:
            payload["username"] = kwargs["username"]
        if "photo_url" in kwargs:
            payload["photo_url"] = kwargs["photo_url"]
        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(payload.items()) if k != "hash"
        )
        secret_key = hashlib.sha256(telegram_bot_token.encode()).digest()
        payload["hash"] = hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()
        return payload

    return factory
