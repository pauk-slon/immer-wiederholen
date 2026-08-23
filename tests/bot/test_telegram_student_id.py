import pytest

from wiederholen.bot.telegram_student_id import (
    NotATelegramStudentIdError,
    TelegramStudentID,
)


def test_encode_prefixes_the_chat_id() -> None:
    assert TelegramStudentID.encode(123) == "telegram:123"


def test_decode_recovers_the_chat_id() -> None:
    assert TelegramStudentID.decode("telegram:123") == 123


def test_decode_raises_for_a_student_id_from_a_different_frontend() -> None:
    with pytest.raises(NotATelegramStudentIdError):
        TelegramStudentID.decode("web:123")
