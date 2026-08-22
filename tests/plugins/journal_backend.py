import os
from collections.abc import AsyncIterator

import pytest
from aiogram import Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from wiederholen.journal_backend import JournalBackend, RedisJournalBackend


@pytest.fixture
async def journal_backend(
    redis_storage: RedisStorage,
) -> AsyncIterator[JournalBackend]:
    # Depends on redis_storage purely for flush ordering: it shares the same
    # Redis/DB (and the same --fsm-storage-db-override pin) as the
    # redis_storage fixture (tests/plugins/aiogram.py), just a different key
    # namespace ("journal:*") — redis_storage's own flushdb() already covers
    # this one too, so this fixture doesn't repeat it, just needs to run after.
    backend = RedisJournalBackend.from_url(os.environ["FSM_STORAGE_URL"])
    yield backend
    await backend.close()


@pytest.fixture(autouse=True)
def _set_journal_backend(
    dispatcher: Dispatcher, journal_backend: JournalBackend
) -> None:
    # Registered as permanent workflow data (like dispatcher.fsm.storage),
    # not a per-call feed_message(..., journal_backend=...) kwarg the way
    # course is — unlike course, it's the same piece of infrastructure for
    # every test, not per-test data.
    dispatcher["journal_backend"] = journal_backend


async def seed_journal(
    journal_backend: JournalBackend, student_id: str, journal: dict
) -> None:
    """Test-only convenience for setting up a student's journal wholesale —
    `JournalBackend`'s only public accessor is the mutate-in-place `open()`,
    so seeding starting from the empty dict a fresh student always has just
    means updating it with the desired content.
    """
    async with journal_backend.open(student_id) as current:
        current.update(journal)


async def read_journal(journal_backend: JournalBackend, student_id: str) -> dict:
    """Test-only convenience for reading a student's journal without the
    ceremony of an `async with` block at every assertion call site.
    """
    async with journal_backend.open(student_id) as journal:
        return journal
