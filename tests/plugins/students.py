from collections.abc import AsyncIterator

import pytest

from wiederholen.bot.bootstrap import load_student_store
from wiederholen.students import StudentStore


@pytest.fixture
async def student_store() -> AsyncIterator[StudentStore]:
    store = load_student_store()
    await store.redis.flushdb()
    yield store
    await store.close()
