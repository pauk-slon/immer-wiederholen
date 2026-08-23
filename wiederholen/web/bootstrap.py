import os
from pathlib import Path

from wiederholen.school import Course, RedisStudentRecordBook, StudentRecordBook
from wiederholen.web.session import WebSessionStore


def load_web_course_and_storage() -> tuple[Course, StudentRecordBook, WebSessionStore]:
    course = Course.load(Path(os.environ.get("COURSE_PATH", "data")))
    student_record_book = RedisStudentRecordBook.from_url(
        os.environ["STUDENT_RECORD_STORAGE_URL"]
    )
    session_store = WebSessionStore.from_url(os.environ["WEB_SESSION_STORAGE_URL"])
    return course, student_record_book, session_store
