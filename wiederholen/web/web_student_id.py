"""Encodes/validates the `StudentID` this web frontend addresses
`StudentRecordBook` with. An anonymous visitor's id is a fresh,
unguessable random token generated server-side on first visit and handed
back as a cookie — see `wiederholen.web.app` for where that cookie is
read/set. Tagged with its own `web:` prefix so it can never collide with a
`StudentID` minted elsewhere for the same shared store — e.g. the bare,
unprefixed tokens `wiederholen.school.student_identity_store.
StudentIdentityStore.resolve_or_create_student_id()` mints for the bot's
own Telegram-identified students, which by construction never contain a
`:` (`secrets.token_urlsafe()`'s alphabet has none).
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
