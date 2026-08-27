"""Visual cues for `_meaning`-topic exercises (see CLAUDE.md's
"AI-generated exercises" and issue discussion): given an `Exercise` whose
topic has opted in via `Course.cue_generatable_topics`, generate an
illustration of its sentence via Cloudflare Workers AI (`@cf/black-forest-
labs/flux-1-schnell`, free at this project's scale) — a relevant image
acting as a retrieval cue for the sentence (dual coding), not "an image" as
a generic asset.

A sibling of `shadow_exercises.py`, not a dependency of it — the two share
nothing beyond both taking an `Exercise` and calling out to a generative AI
API. Storing/serving the resulting bytes is a separate concern entirely
(see `wiederholen.school.cue_store`); this module only ever produces raw
image bytes from an `Exercise`, the same way `generate_shadow_exercise()`
only ever produces a new `Exercise`, neither one touching storage.
"""

import base64
from typing import Final

import httpx

from wiederholen.school.curriculum import Exercise

_MODEL: Final = "@cf/black-forest-labs/flux-1-schnell"

# Appended to every prompt, not left to description's own wording: keeps the
# generated cues visually consistent with each other, and — this matters
# specifically for a language-learning app — steers the model away from
# rendering any in-image text at all, which image models frequently garble
# and which would otherwise risk showing the learner incorrect German (or
# any language) baked into the picture itself.
_STYLE_SUFFIX: Final = (
    ", simple clear illustration, single scene, no text or letters in the image"
)


def build_cue_prompt(exercise: Exercise) -> str | None:
    # None (no description) means nothing to build a prompt from — matches
    # Course.cue_generatable_topics being a topic-level opt-in independent
    # of whether a given exercise within it happens to carry one; today the
    # two coincide for every eligible topic (see CLAUDE.md), but this
    # function doesn't assume that stays true.
    if exercise.description is None:
        return None
    return exercise.description["en"] + _STYLE_SUFFIX


async def generate_exercise_cue(
    client: httpx.AsyncClient,
    exercise: Exercise,
    *,
    account_id: str,
    api_token: str,
) -> bytes | None:
    """Generates a cue image for exercise, or None if its topic/description
    combination has nothing to generate a prompt from (see
    build_cue_prompt()). Raises httpx.HTTPError on a failed API call."""
    prompt = build_cue_prompt(exercise)
    if prompt is None:
        return None
    response = await client.post(
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{_MODEL}",
        headers={"Authorization": f"Bearer {api_token}"},
        json={"prompt": prompt},
    )
    response.raise_for_status()
    # Cloudflare returns the image base64-encoded inside a JSON body, not as
    # the response's raw bytes directly — the "image" key sits under the
    # standard {"result": {...}, "success": ...} envelope most Cloudflare
    # REST APIs use, but the docs for this specific model only ever show the
    # bare {"image": ...} shape, so both are checked rather than assuming
    # one.
    data = response.json()
    result = data.get("result", data)
    encoded = result.get("image")
    if not isinstance(encoded, str):
        raise httpx.HTTPError(f"unexpected Workers AI response shape: {data!r}")
    return base64.b64decode(encoded)
