"""One-shot worker: generates and uploads visual cues for exercises whose
topic has opted in via `Course.cue_generatable_topics` (see CLAUDE.md's
"AI-generated exercises") but don't have one yet.

Run on demand — `python -m wiederholen.cues` — whenever content changes,
not a standing service like `wiederholen.bot.reminder`: that one polls
every 15 minutes because reminders are genuinely time-sensitive, but new
exercises are added rarely, at content-authoring time, so there's nothing
here worth polling for.

No automated approval gate on what gets uploaded — the one combined summary
line logged at the end (generated/already-had-one/no-description/failed
counts) is what the person who just ran this actually reads afterward, to
spot-check the result themselves rather than trusting the pipeline blindly
(see CLAUDE.md).
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import httpx

from wiederholen.school import Course, Exercise, R2CueStore
from wiederholen.school.authoring import generate_exercise_cue

logger = logging.getLogger(__name__)


@dataclass
class _Summary:
    generated: int = 0
    skipped_existing: int = 0
    skipped_no_description: int = 0
    failed: int = 0


async def _process_exercise(
    exercise: Exercise,
    store: R2CueStore,
    client: httpx.AsyncClient,
    *,
    account_id: str,
    api_token: str,
    summary: _Summary,
) -> None:
    # Checked first, before spending a Workers AI call, since it's a single
    # cheap HEAD request — re-running this worker after adding a handful of
    # new exercises shouldn't re-generate cues for everything already done.
    if await store.get_cue_url(exercise) is not None:
        summary.skipped_existing += 1
        return
    try:
        image_bytes = await generate_exercise_cue(
            client, exercise, account_id=account_id, api_token=api_token
        )
    except httpx.HTTPError:
        logger.exception("Failed to generate cue for %r", exercise.question)
        summary.failed += 1
        return
    # None means the exercise has no description to build a prompt from —
    # see build_cue_prompt()'s own docstring — not a failure, just nothing
    # to generate here.
    if image_bytes is None:
        summary.skipped_no_description += 1
        return
    await store.upload_cue(exercise, image_bytes)
    summary.generated += 1
    logger.info("Generated cue for %r", exercise.question)


async def run() -> None:
    course = Course.load(Path(os.environ.get("COURSE_PATH", "data")))
    store = R2CueStore(
        account_id=os.environ["R2_ACCOUNT_ID"],
        access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        bucket=os.environ["R2_BUCKET"],
        public_url_base=os.environ["R2_PUBLIC_URL_BASE"],
    )
    account_id = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    api_token = os.environ["CLOUDFLARE_API_TOKEN"]
    eligible = [
        exercise
        for exercise in course.exercises
        if exercise.topic in course.cue_generatable_topics
    ]
    summary = _Summary()
    async with httpx.AsyncClient(timeout=60.0) as client:
        for exercise in eligible:
            await _process_exercise(
                exercise,
                store,
                client,
                account_id=account_id,
                api_token=api_token,
                summary=summary,
            )
    logger.info(
        "Done: %d generated, %d already had one, %d had no description, %d failed",
        summary.generated,
        summary.skipped_existing,
        summary.skipped_no_description,
        summary.failed,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())


if __name__ == "__main__":  # pragma: no cover
    main()
