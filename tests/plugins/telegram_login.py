import hashlib
import hmac
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TypedDict, Unpack

import pytest


class TelegramLoginKwargs(TypedDict, total=False):
    """The fields of a Telegram Login Widget payload a test can plausibly
    override before it gets signed — not `hash`, which the factory always
    computes itself from the rest.
    """

    id: str
    first_name: str
    auth_date: str
    last_name: str
    username: str
    photo_url: str


type TelegramLoginPayloadFactory = Callable[..., dict[str, str]]


@pytest.fixture
def telegram_login_payload_factory(
    bot_token: str,
    telegram_user_id: int,
) -> TelegramLoginPayloadFactory:
    """A correctly-signed Telegram Login Widget callback payload — the same
    shape validate_telegram_login() expects, signed for bot_token so it
    round-trips through real validation. Overrides apply *before* signing
    (e.g. a stale auth_date), matching what a genuinely different payload
    from Telegram would have looked like — tampering *after* signing is
    what the "rejects a tampered field" tests exercise instead.
    """

    def factory(**kwargs: Unpack[TelegramLoginKwargs]) -> dict[str, str]:
        payload: dict[str, str] = {
            "id": kwargs.get("id", str(telegram_user_id)),
            "first_name": kwargs.get("first_name", "Test"),
            "auth_date": kwargs.get(
                "auth_date", str(int(datetime.now(UTC).timestamp()))
            ),
        }
        if "last_name" in kwargs:
            payload["last_name"] = kwargs["last_name"]
        if "username" in kwargs:
            payload["username"] = kwargs["username"]
        if "photo_url" in kwargs:
            payload["photo_url"] = kwargs["photo_url"]
        data_check_string = "\n".join(f"{k}={payload[k]}" for k in sorted(payload))
        secret_key = hashlib.sha256(bot_token.encode()).digest()
        payload["hash"] = hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()
        return payload

    return factory
