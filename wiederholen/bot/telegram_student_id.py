"""Encodes/decodes the `StudentID` this bot addresses `StudentRecordBook`
with — `str(chat_id)` alone has no way to tell it apart from an id another
frontend (a future web chat, say) might use for the same shared store, so
every Telegram-originated id is tagged with a `telegram:` prefix.
"""

from typing import Final

from wiederholen.school import StudentID


class NotATelegramStudentIdError(ValueError):
    """A `StudentID` that doesn't carry the `telegram:` prefix — e.g. one
    belonging to a different frontend sharing the same `StudentRecordBook`.
    """


class TelegramStudentID:
    _PREFIX: Final = "telegram:"

    @classmethod
    def encode(cls, chat_id: int) -> StudentID:
        return f"{cls._PREFIX}{chat_id}"

    @classmethod
    def decode(cls, student_id: StudentID) -> int:
        if not student_id.startswith(cls._PREFIX):
            raise NotATelegramStudentIdError(student_id)
        return int(student_id.removeprefix(cls._PREFIX))
