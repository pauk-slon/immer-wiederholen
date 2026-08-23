import os
from collections.abc import AsyncIterator

import pytest

from wiederholen.web.session import WebSessionStore


@pytest.fixture
async def web_session_store() -> AsyncIterator[WebSessionStore]:
    # Flushes its own DB rather than assuming it coincides with any other
    # store's — same reasoning as student_record_book's own fixture (see
    # tests/plugins/student_record_book.py).
    url = os.environ["WEB_SESSION_STORAGE_URL"]
    async with WebSessionStore.from_url(url) as store:
        await store.redis.flushdb()
        yield store
