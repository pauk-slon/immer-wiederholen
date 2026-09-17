import os
from collections.abc import AsyncIterator

import pytest
from aiogram import Dispatcher

from wiederholen.school import StudentID, StudentIdentityStore
from wiederholen.school.student_identity_store import RedisStudentIdentityStore


@pytest.fixture
async def student_identity_store() -> AsyncIterator[StudentIdentityStore]:
    # Own DB (STUDENT_IDENTITY_STORAGE_URL), flushed directly rather than
    # assuming it coincides with student_record_book's or redis_storage's —
    # same reasoning as tests/plugins/student_record_book.py's own fixture.
    url = os.environ["STUDENT_IDENTITY_STORAGE_URL"]
    async with RedisStudentIdentityStore.from_url(url) as store:
        await store.redis.flushdb()
        yield store


@pytest.fixture(autouse=True)
def _set_student_identity_store(
    dispatcher: Dispatcher, student_identity_store: StudentIdentityStore
) -> None:
    # Permanent workflow data, like student_record_book — the same piece of
    # infrastructure for every test, not per-test data.
    dispatcher["student_identity_store"] = student_identity_store


@pytest.fixture
async def student_id(
    student_identity_store: StudentIdentityStore, chat_id: int
) -> StudentID:
    """The StudentID a handler resolves `chat_id` to via the telegram
    provider — pre-resolved here so a test's own setup (seed_student_record)
    and the handler under test address the same student_record. Resolving
    it here first is what makes that convergence work: resolve_or_create_
    student_id() only ever mints once per (provider, identifier), so the
    handler's own later call just reads back this same id.
    """
    return await student_identity_store.resolve_or_create_student_id(
        "telegram", str(chat_id)
    )
