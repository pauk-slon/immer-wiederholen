# 0014. Illustrations are generated ahead of time

**Status:** Accepted, 2026-10-17 ([#194](https://github.com/pauk-slon/immer-wiederholen/pull/194))

## Context

A hand-made pilot suggested that an illustration of the sentence helps learners remember `_meaning` exercises. Images had to be generated, stored, and shown by the bot with each question.

## Decision

- Illustrations ("cues") are generated ahead of time by a one-off command, not when a question is shown: Cloudflare Workers AI generates them and Cloudflare R2 stores them, chosen because the project's Cloudflare account already existed and the free tiers cover this volume ([#194](https://github.com/pauk-slon/immer-wiederholen/pull/194)).
- Eligibility is opt-in per topic (`cue_generation`), separate from whether an exercise has a `description`.
- The bot only looks illustrations up, and falls back to a text question on any failure.

How illustrations are found is [0017](0017-cues-keyed-by-question-hash.md).

## Alternatives considered

- **Derive eligibility from `description`.** They coincide today, but a description can exist only to disambiguate a sentence, and adding one shouldn't turn illustrations on ([#194](https://github.com/pauk-slon/immer-wiederholen/pull/194)).

## Consequences

- Rendering a question never waits for image generation. To keep R2 off that path too, the bot caches lookups in-process for 12 hours, "no cue yet" included, so a new illustration can take that long to appear.
- The generator has to be run after content changes.
- The free tier allows about 90 images a day, so a full run takes several days (observed after #194, whose estimate was higher).
