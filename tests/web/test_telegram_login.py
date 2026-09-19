from datetime import UTC, datetime, timedelta

import pytest

from tests.plugins.telegram_login import TelegramLoginPayloadFactory
from wiederholen.web.telegram_login import (
    InvalidTelegramLoginError,
    validate_telegram_login,
)


def test_validate_accepts_a_correctly_signed_payload(
    bot_token: str,
    telegram_user_id: int,
    telegram_login_payload_factory: TelegramLoginPayloadFactory,
) -> None:
    payload = telegram_login_payload_factory()

    assert validate_telegram_login(payload, bot_token) == telegram_user_id


def test_validate_rejects_a_field_tampered_with_after_signing(
    bot_token: str, telegram_login_payload_factory: TelegramLoginPayloadFactory
) -> None:
    payload = telegram_login_payload_factory()
    payload["id"] = "999"

    with pytest.raises(InvalidTelegramLoginError):
        validate_telegram_login(payload, bot_token)


def test_validate_rejects_a_payload_signed_for_a_different_bot_token(
    telegram_login_payload_factory: TelegramLoginPayloadFactory,
) -> None:
    payload = telegram_login_payload_factory()

    with pytest.raises(InvalidTelegramLoginError):
        validate_telegram_login(
            payload, "0000000000:BBdifferenttokenxxxxxxxxxxxxxxxxxxx"
        )


def test_validate_rejects_a_missing_hash(
    bot_token: str, telegram_login_payload_factory: TelegramLoginPayloadFactory
) -> None:
    payload = telegram_login_payload_factory()
    del payload["hash"]

    with pytest.raises(InvalidTelegramLoginError):
        validate_telegram_login(payload, bot_token)


def test_validate_rejects_a_stale_auth_date(
    bot_token: str, telegram_login_payload_factory: TelegramLoginPayloadFactory
) -> None:
    stale = str(int((datetime.now(UTC) - timedelta(days=2)).timestamp()))
    payload = telegram_login_payload_factory(auth_date=stale)

    with pytest.raises(InvalidTelegramLoginError):
        validate_telegram_login(payload, bot_token)


def test_validate_accepts_an_auth_date_just_under_the_limit(
    bot_token: str,
    telegram_user_id: int,
    telegram_login_payload_factory: TelegramLoginPayloadFactory,
) -> None:
    fresh_enough = str(int((datetime.now(UTC) - timedelta(hours=23)).timestamp()))
    payload = telegram_login_payload_factory(auth_date=fresh_enough)

    assert validate_telegram_login(payload, bot_token) == telegram_user_id


def test_validate_rejects_a_non_numeric_id(
    bot_token: str, telegram_login_payload_factory: TelegramLoginPayloadFactory
) -> None:
    payload = telegram_login_payload_factory(id="not-a-number")

    with pytest.raises(InvalidTelegramLoginError):
        validate_telegram_login(payload, bot_token)
