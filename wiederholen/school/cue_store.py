"""Storage for the visual cues `wiederholen.cues` generates for
`_meaning`-topic exercises (see CLAUDE.md's "AI-generated exercises") — a
`CueStore` maps an `Exercise` (via its `cue_key`, see curriculum.py) to a
public URL if one has been generated for it, and lets the worker upload one.
Named "cue" rather than "image": the pedagogical point is dual coding — a
relevant illustration acting as a retrieval cue for the sentence — not
"an image" as a generic asset.

Interface and implementation live together in one module, the same shape
`student_record_book.py` already uses for `StudentRecordBook`/
`RedisStudentRecordBook` — no separate interface-only module until a second
implementation genuinely needs one independently of R2.
"""

from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta

import aioboto3

from wiederholen.school.curriculum import Exercise


class CueStore(ABC):
    @abstractmethod
    async def get_cue_url(self, exercise: Exercise) -> str | None:
        """A public URL for exercise's cue, or None if none has been
        generated for it yet."""

    @abstractmethod
    async def upload_cue(self, exercise: Exercise, image_bytes: bytes) -> None:
        """Stores image_bytes as exercise's cue, overwriting any existing
        one under the same key."""


class R2CueStore(CueStore):
    def __init__(
        self,
        *,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        public_url_base: str,
    ) -> None:
        self._endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._bucket = bucket
        # No trailing slash assumed either way — normalized once here so
        # every URL this class builds is consistent regardless of how the
        # env var happened to be written.
        self._public_url_base = public_url_base.rstrip("/")

    def _client(self):
        # A fresh client per call, not one held on self: aioboto3's client is
        # itself an async context manager tied to one `async with` block —
        # matches boto3's own recommended usage, and this class's callers
        # already only ever make one request at a time.
        return aioboto3.Session().client(
            "s3",
            endpoint_url=self._endpoint_url,
            aws_access_key_id=self._access_key_id,
            aws_secret_access_key=self._secret_access_key,
        )

    async def get_cue_url(self, exercise: Exercise) -> str | None:
        key = exercise.cue_key
        async with self._client() as client:
            try:
                await client.head_object(Bucket=self._bucket, Key=key)
            except client.exceptions.ClientError as e:
                # head_object's own 404 comes back as a generic ClientError,
                # not a dedicated exception type (unlike get_object's 404,
                # which boto3 gives a NoSuchKey class) — the response's own
                # status code is the only reliable signal.
                if e.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404:
                    return None
                raise
        return f"{self._public_url_base}/{key}"

    async def upload_cue(self, exercise: Exercise, image_bytes: bytes) -> None:
        async with self._client() as client:
            await client.put_object(
                Bucket=self._bucket,
                Key=exercise.cue_key,
                Body=image_bytes,
                ContentType="image/png",
            )


class CachedCueStore(CueStore):
    _TTL: timedelta = timedelta(hours=12)

    def __init__(self, wrapped: CueStore) -> None:
        self._wrapped = wrapped
        # In-process only — wiederholen.bot runs as a single polling
        # process, so a plain dict needs no external storage (unlike
        # StudentRecordBook/WebSessionStore, this isn't per-student data
        # that needs to survive a restart or be shared across workers).
        # A negative result (None — "no cue yet") is cached exactly the
        # same as a real URL: a newly-uploaded cue can take up to _TTL to
        # actually appear for a question already rendered before the
        # upload, a deliberate tradeoff for never hitting R2 on every
        # render (see CLAUDE.md).
        self._cache: dict[str, tuple[str | None, datetime]] = {}

    async def get_cue_url(self, exercise: Exercise) -> str | None:
        key = exercise.cue_key
        cached = self._cache.get(key)
        if cached is not None:
            url, checked_at = cached
            if datetime.now(UTC) - checked_at < self._TTL:
                return url
        url = await self._wrapped.get_cue_url(exercise)
        self._cache[key] = (url, datetime.now(UTC))
        return url

    async def upload_cue(self, exercise: Exercise, image_bytes: bytes) -> None:
        # Never called on the bot's own CachedCueStore in practice (the
        # worker uploads through a bare store instead — see
        # wiederholen.cues), but implemented for completeness rather than
        # raising NotImplementedError: forwarding to the wrapped store and
        # invalidating this key's cache entry is the obviously-correct
        # behavior if it ever were called.
        await self._wrapped.upload_cue(exercise, image_bytes)
        self._cache.pop(exercise.cue_key, None)
