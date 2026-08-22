import os
from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
from aiogram import Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from wiederholen.student_record_book import RedisStudentRecordBook, StudentRecordBook

type SeedStudentRecord = Callable[[str, dict], Awaitable[None]]
type ReadStudentRecord = Callable[[str], Awaitable[dict]]


@pytest.fixture
async def student_record_book(
    redis_storage: RedisStorage,
) -> AsyncIterator[StudentRecordBook]:
    # Depends on redis_storage purely for flush ordering: it shares the same
    # Redis/DB (and the same --redis-db-override pin) as the redis_storage
    # fixture (tests/plugins/aiogram.py) today, just a different key namespace
    # ("student_record:*") and its own env var (STUDENT_RECORD_STORAGE_URL) —
    # redis_storage's own flushdb() already covers this one too, so this
    # fixture doesn't repeat it, just needs to run after.
    # async with, not a bare instance + manual close(): StudentRecordBook has no
    # public close() at all, only the usual context-manager protocol.
    url = os.environ["STUDENT_RECORD_STORAGE_URL"]
    async with RedisStudentRecordBook.from_url(url) as store:
        yield store


@pytest.fixture(autouse=True)
def _set_student_record_book(
    dispatcher: Dispatcher, student_record_book: StudentRecordBook
) -> None:
    # Registered as permanent workflow data (like dispatcher.fsm.storage),
    # not a per-call feed_message(..., student_record_book=...) kwarg the way
    # course is — unlike course, it's the same piece of infrastructure for
    # every test, not per-test data.
    dispatcher["student_record_book"] = student_record_book


@pytest.fixture
def seed_student_record(student_record_book: StudentRecordBook) -> SeedStudentRecord:
    """Test-only convenience for setting up a student's student_record wholesale —
    `StudentRecordBook`'s only public accessor is the mutate-in-place `check_out()`,
    so seeding starting from the empty dict a fresh student always has just
    means updating it with the desired content. A fixture (like
    `feed_message`/`feed_callback_query` in `tests/plugins/aiogram.py`)
    rather than a plain function, so call sites don't need to separately
    request `student_record_book` just to pass it along.
    """

    async def factory(student_id: str, student_record: dict) -> None:
        async with student_record_book.check_out(student_id) as current:
            current.update(student_record)

    return factory


@pytest.fixture
def read_student_record(student_record_book: StudentRecordBook) -> ReadStudentRecord:
    """Test-only convenience for reading a student's student_record without the
    ceremony of an `async with` block at every assertion call site.
    """

    async def factory(student_id: str) -> dict:
        async with student_record_book.check_out(student_id) as student_record:
            return student_record

    return factory
