"""Encodes/validates the `StudentID` this web frontend addresses
`StudentRecordBook` with — mirrors `wiederholen.bot.telegram_student_id.
TelegramStudentID`, tagging every web-originated id with its own `web:`
prefix so it can never collide with a Telegram (or any other frontend's) id
sharing the same store.

Unlike a Telegram `chat_id`, there's no pre-existing identity to encode: an
anonymous visitor's id is a fresh, unguessable random token generated
server-side on first visit and handed back as a cookie — see
`wiederholen.web.app` for where that cookie is read/set.
"""

import secrets
from typing import Final

from wiederholen.school import StudentID


class NotAWebStudentIdError(ValueError):
    """A `StudentID` that doesn't carry the `web:` prefix — e.g. one
    belonging to a different frontend sharing the same `StudentRecordBook`,
    or a cookie value that was never one of ours to begin with.
    """


class WebStudentID:
    _PREFIX: Final = "web:"

    @classmethod
    def generate(cls) -> StudentID:
        return f"{cls._PREFIX}{secrets.token_urlsafe(32)}"

    @classmethod
    def validate(cls, student_id: str) -> StudentID:
        if not student_id.startswith(cls._PREFIX):
            raise NotAWebStudentIdError(student_id)
        return student_id
