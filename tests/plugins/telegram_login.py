import hashlib
import hmac
from collections.abc import Callable
from datetime import UTC, datetime

import pytest

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

    def factory(**overrides: str) -> dict[str, str]:
        payload: dict[str, str] = {
            "id": str(telegram_user_id),
            "first_name": "Test",
            "auth_date": str(int(datetime.now(UTC).timestamp())),
            "hash": "",
        }
        payload.update(overrides)
        data_check_string = "\n".join(
            f"{key}={payload[key]}" for key in sorted(payload) if key != "hash"
        )
        secret_key = hashlib.sha256(bot_token.encode()).digest()
        payload["hash"] = hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()
        return payload

    return factory
