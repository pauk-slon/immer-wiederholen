from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from tests.plugins.curriculum import make_exercise
from wiederholen.school.cue_store import CachedCueStore, CueStore, R2CueStore


class _StubCueStore(CueStore):
    def __init__(self, url: str | None = None) -> None:
        self.url = url
        self.get_calls = 0
        self.uploaded: tuple | None = None

    async def get_cue_url(self, exercise) -> str | None:
        self.get_calls += 1
        return self.url

    async def upload_cue(self, exercise, image_bytes: bytes) -> None:
        self.uploaded = (exercise, image_bytes)


async def test_cached_store_returns_the_wrapped_stores_result() -> None:
    exercise = make_exercise()
    wrapped = _StubCueStore(url="https://example.com/img.png")
    store = CachedCueStore(wrapped)

    assert await store.get_cue_url(exercise) == "https://example.com/img.png"


async def test_cached_store_does_not_recheck_within_the_ttl() -> None:
    exercise = make_exercise()
    wrapped = _StubCueStore(url="https://example.com/img.png")
    store = CachedCueStore(wrapped)

    await store.get_cue_url(exercise)
    await store.get_cue_url(exercise)

    assert wrapped.get_calls == 1


async def test_cached_store_rechecks_once_the_ttl_has_expired() -> None:
    exercise = make_exercise()
    wrapped = _StubCueStore(url="https://example.com/img.png")
    store = CachedCueStore(wrapped)
    await store.get_cue_url(exercise)
    # Seed an already-stale cache entry directly, rather than mocking the
    # clock or actually waiting 12 hours — this class's own _TTL is the only
    # thing under test here.
    store._cache[exercise.cue_key] = (
        wrapped.url,
        datetime.now(UTC) - CachedCueStore._TTL - timedelta(seconds=1),
    )

    await store.get_cue_url(exercise)

    assert wrapped.get_calls == 2


async def test_cached_store_caches_a_negative_result_too() -> None:
    exercise = make_exercise()
    wrapped = _StubCueStore(url=None)
    store = CachedCueStore(wrapped)

    await store.get_cue_url(exercise)
    await store.get_cue_url(exercise)

    assert wrapped.get_calls == 1


async def test_cached_store_upload_forwards_and_invalidates() -> None:
    exercise = make_exercise()
    wrapped = _StubCueStore(url="https://example.com/img.png")
    store = CachedCueStore(wrapped)
    await store.get_cue_url(exercise)

    await store.upload_cue(exercise, b"bytes")

    assert wrapped.uploaded == (exercise, b"bytes")
    assert exercise.cue_key not in store._cache


def _make_r2_store() -> R2CueStore:
    return R2CueStore(
        account_id="acc",
        access_key_id="key",
        secret_access_key="secret",
        bucket="images",
        public_url_base="https://images.example.com/",
    )


def _fake_client(mock_client: Mock):
    @asynccontextmanager
    async def factory(*args, **kwargs):
        yield mock_client

    return factory


async def test_r2_store_returns_a_url_when_the_object_exists() -> None:
    store = _make_r2_store()
    exercise = make_exercise()
    mock_client = Mock()
    mock_client.head_object = AsyncMock(return_value=None)
    mock_session = Mock()
    mock_session.client = Mock(side_effect=lambda *a, **k: _fake_client(mock_client)())

    with patch(
        "wiederholen.school.cue_store.aioboto3.Session", return_value=mock_session
    ):
        url = await store.get_cue_url(exercise)

    assert url == f"https://images.example.com/{exercise.cue_key}"
    mock_client.head_object.assert_awaited_once_with(
        Bucket="images", Key=exercise.cue_key
    )


async def test_r2_store_returns_none_when_the_object_is_missing() -> None:
    store = _make_r2_store()
    exercise = make_exercise()

    class _ClientError(Exception):
        def __init__(self) -> None:
            self.response = {"ResponseMetadata": {"HTTPStatusCode": 404}}

    mock_client = Mock()
    mock_client.exceptions = Mock(ClientError=_ClientError)
    mock_client.head_object = AsyncMock(side_effect=_ClientError())
    mock_session = Mock()
    mock_session.client = Mock(side_effect=lambda *a, **k: _fake_client(mock_client)())

    with patch(
        "wiederholen.school.cue_store.aioboto3.Session", return_value=mock_session
    ):
        url = await store.get_cue_url(exercise)

    assert url is None


async def test_r2_store_reraises_a_non_404_client_error() -> None:
    store = _make_r2_store()
    exercise = make_exercise()

    class _ClientError(Exception):
        def __init__(self) -> None:
            self.response = {"ResponseMetadata": {"HTTPStatusCode": 500}}

    mock_client = Mock()
    mock_client.exceptions = Mock(ClientError=_ClientError)
    mock_client.head_object = AsyncMock(side_effect=_ClientError())
    mock_session = Mock()
    mock_session.client = Mock(side_effect=lambda *a, **k: _fake_client(mock_client)())

    with (
        patch(
            "wiederholen.school.cue_store.aioboto3.Session", return_value=mock_session
        ),
        pytest.raises(_ClientError),
    ):
        await store.get_cue_url(exercise)


async def test_r2_store_uploads_with_the_image_content_type() -> None:
    store = _make_r2_store()
    exercise = make_exercise()
    mock_client = Mock()
    mock_client.put_object = AsyncMock(return_value=None)
    mock_session = Mock()
    mock_session.client = Mock(side_effect=lambda *a, **k: _fake_client(mock_client)())

    with patch(
        "wiederholen.school.cue_store.aioboto3.Session", return_value=mock_session
    ):
        await store.upload_cue(exercise, b"bytes")

    mock_client.put_object.assert_awaited_once_with(
        Bucket="images",
        Key=exercise.cue_key,
        Body=b"bytes",
        ContentType="image/png",
    )
