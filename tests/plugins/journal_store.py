import os
from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
from aiogram import Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from wiederholen.journal_store import JournalStore, RedisJournalStore

type SeedJournal = Callable[[str, dict], Awaitable[None]]
type ReadJournal = Callable[[str], Awaitable[dict]]


@pytest.fixture
async def journal_store(
    redis_storage: RedisStorage,
) -> AsyncIterator[JournalStore]:
    # Depends on redis_storage purely for flush ordering: it shares the same
    # Redis/DB (and the same --fsm-storage-db-override pin) as the
    # redis_storage fixture (tests/plugins/aiogram.py), just a different key
    # namespace ("journal:*") — redis_storage's own flushdb() already covers
    # this one too, so this fixture doesn't repeat it, just needs to run after.
    store = RedisJournalStore.from_url(os.environ["FSM_STORAGE_URL"])
    yield store
    await store.close()


@pytest.fixture(autouse=True)
def _set_journal_store(dispatcher: Dispatcher, journal_store: JournalStore) -> None:
    # Registered as permanent workflow data (like dispatcher.fsm.storage),
    # not a per-call feed_message(..., journal_store=...) kwarg the way
    # course is — unlike course, it's the same piece of infrastructure for
    # every test, not per-test data.
    dispatcher["journal_store"] = journal_store


@pytest.fixture
def seed_journal(journal_store: JournalStore) -> SeedJournal:
    """Test-only convenience for setting up a student's journal wholesale —
    `JournalStore`'s only public accessor is the mutate-in-place `check_out()`,
    so seeding starting from the empty dict a fresh student always has just
    means updating it with the desired content. A fixture (like
    `feed_message`/`feed_callback_query` in `tests/plugins/aiogram.py`)
    rather than a plain function, so call sites don't need to separately
    request `journal_store` just to pass it along.
    """

    async def factory(student_id: str, journal: dict) -> None:
        async with journal_store.check_out(student_id) as current:
            current.update(journal)

    return factory


@pytest.fixture
def read_journal(journal_store: JournalStore) -> ReadJournal:
    """Test-only convenience for reading a student's journal without the
    ceremony of an `async with` block at every assertion call site.
    """

    async def factory(student_id: str) -> dict:
        async with journal_store.check_out(student_id) as journal:
            return journal

    return factory
