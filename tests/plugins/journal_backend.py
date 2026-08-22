import os
from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
from aiogram import Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from wiederholen.journal_backend import JournalBackend, RedisJournalBackend

type SeedJournal = Callable[[str, dict], Awaitable[None]]
type ReadJournal = Callable[[str], Awaitable[dict]]


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


@pytest.fixture
def seed_journal(journal_backend: JournalBackend) -> SeedJournal:
    """Test-only convenience for setting up a student's journal wholesale —
    `JournalBackend`'s only public accessor is the mutate-in-place `open()`,
    so seeding starting from the empty dict a fresh student always has just
    means updating it with the desired content. A fixture (like
    `feed_message`/`feed_callback_query` in `tests/plugins/aiogram.py`)
    rather than a plain function, so call sites don't need to separately
    request `journal_backend` just to pass it along.
    """

    async def factory(student_id: str, journal: dict) -> None:
        async with journal_backend.open(student_id) as current:
            current.update(journal)

    return factory


@pytest.fixture
def read_journal(journal_backend: JournalBackend) -> ReadJournal:
    """Test-only convenience for reading a student's journal without the
    ceremony of an `async with` block at every assertion call site.
    """

    async def factory(student_id: str) -> dict:
        async with journal_backend.open(student_id) as journal:
            return journal

    return factory
