import os
from pathlib import Path

from wiederholen.school import (
    Course,
    RedisStudentIdentityStore,
    RedisStudentRecordBook,
    StudentIdentityStore,
    StudentRecordBook,
)
from wiederholen.web.session import WebSessionStore


def load_web_course_and_storage() -> tuple[
    Course, StudentRecordBook, WebSessionStore, StudentIdentityStore
]:
    course = Course.load(Path(os.environ.get("COURSE_PATH", "data")))
    student_record_book = RedisStudentRecordBook.from_url(
        os.environ["STUDENT_RECORD_STORAGE_URL"]
    )
    session_store = WebSessionStore.from_url(os.environ["WEB_SESSION_STORAGE_URL"])
    student_identity_store = RedisStudentIdentityStore.from_url(
        os.environ["STUDENT_IDENTITY_STORAGE_URL"]
    )
    return course, student_record_book, session_store, student_identity_store


def load_bot_token() -> str:
    # Required, no fallback — used to validate Telegram Login Widget
    # callbacks (telegram_login.py), not to call the Bot API.
    return os.environ["BOT_TOKEN"]
