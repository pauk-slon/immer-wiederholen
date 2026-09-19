from datetime import UTC, datetime, timedelta

import pytest

from tests.plugins.telegram_login import make_telegram_login_payload
from wiederholen.web.telegram_login import (
    InvalidTelegramLoginError,
    validate_telegram_login,
)


def test_validate_accepts_a_correctly_signed_payload(bot_token: str) -> None:
    payload = make_telegram_login_payload(bot_token, id="777")

    assert validate_telegram_login(payload, bot_token) == 777


def test_validate_rejects_a_field_tampered_with_after_signing(bot_token: str) -> None:
    payload = make_telegram_login_payload(bot_token, id="777")
    payload["id"] = "999"

    with pytest.raises(InvalidTelegramLoginError):
        validate_telegram_login(payload, bot_token)


def test_validate_rejects_a_payload_signed_for_a_different_bot_token(
    bot_token: str,
) -> None:
    payload = make_telegram_login_payload(bot_token)

    with pytest.raises(InvalidTelegramLoginError):
        validate_telegram_login(
            payload, "0000000000:BBdifferenttokenxxxxxxxxxxxxxxxxxxx"
        )


def test_validate_rejects_a_missing_hash(bot_token: str) -> None:
    payload = make_telegram_login_payload(bot_token)
    del payload["hash"]

    with pytest.raises(InvalidTelegramLoginError):
        validate_telegram_login(payload, bot_token)


def test_validate_rejects_a_stale_auth_date(bot_token: str) -> None:
    stale = str(int((datetime.now(UTC) - timedelta(days=2)).timestamp()))
    payload = make_telegram_login_payload(bot_token, auth_date=stale)

    with pytest.raises(InvalidTelegramLoginError):
        validate_telegram_login(payload, bot_token)


def test_validate_accepts_an_auth_date_just_under_the_limit(bot_token: str) -> None:
    fresh_enough = str(int((datetime.now(UTC) - timedelta(hours=23)).timestamp()))
    payload = make_telegram_login_payload(bot_token, auth_date=fresh_enough)

    assert validate_telegram_login(payload, bot_token) == 12345


def test_validate_rejects_a_non_numeric_id(bot_token: str) -> None:
    payload = make_telegram_login_payload(bot_token, id="not-a-number")

    with pytest.raises(InvalidTelegramLoginError):
        validate_telegram_login(payload, bot_token)
