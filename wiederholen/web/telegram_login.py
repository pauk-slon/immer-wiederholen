"""Validates a Telegram Login Widget callback — https://core.telegram.org/widgets/login#checking-authorization.
Deliberately not OIDC/OAuth: Telegram has no real standards-based identity
provider, just this one bespoke, per-surface HMAC scheme (a different one
again from a Mini App's own `initData`, which this module doesn't handle).
"""

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import Final


class InvalidTelegramLoginError(ValueError):
    """The payload's signature doesn't check out, or its auth_date is too
    old to trust as a fresh login (rather than a stale, replayed callback
    URL — e.g. one saved from a browser history entry)."""


_MAX_AUTH_AGE: Final = timedelta(days=1)


def _data_check_string(payload: dict[str, str]) -> str:
    return "\n".join(
        f"{key}={payload[key]}" for key in sorted(payload) if key != "hash"
    )


def validate_telegram_login(payload: dict[str, str], bot_token: str) -> int:
    """Returns the Telegram user id a Login Widget callback payload
    (id, first_name, ..., auth_date, hash) vouches for, once its signature
    and freshness both check out. Raises InvalidTelegramLoginError otherwise.
    """
    if "hash" not in payload:
        raise InvalidTelegramLoginError("missing hash")
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    expected_hash = hmac.new(
        secret_key, _data_check_string(payload).encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_hash, payload["hash"]):
        raise InvalidTelegramLoginError("signature mismatch")
    try:
        auth_date = datetime.fromtimestamp(int(payload["auth_date"]), tz=UTC)
        user_id = int(payload["id"])
    except (KeyError, ValueError) as e:
        raise InvalidTelegramLoginError("missing or malformed id/auth_date") from e
    if datetime.now(UTC) - auth_date > _MAX_AUTH_AGE:
        raise InvalidTelegramLoginError("auth_date too old")
    return user_id
