# 0014. Illustrations are generated ahead of time and keyed by the question

**Status:** Accepted, 2026-10-17 ([#194](https://github.com/pauk-slon/immer-wiederholen/pull/194))

## Context

A hand-made pilot suggested that an illustration of the sentence helps learners remember `_meaning` exercises. Images had to be generated, stored and found again by the bot for each question.

## Decision

- Illustrations ("cues") are generated ahead of time by a one-off command, not on the fly: Cloudflare Workers AI generates them, Cloudflare R2 stores them, chosen because the project's Cloudflare account already existed and the free tiers cover this volume.
- Each is stored under `Exercise.cue_key`, the SHA-256 of `question`, computed in one place for both the generator and the bot.
- Eligibility is opt-in per topic (`cue_generation`), separate from whether an exercise has a `description`.
- The bot caches lookups in-process for 12 hours, "no cue yet" included, and falls back to a text question on any failure.

## Alternatives considered

- **Key by word and topic.** Not unique: several exercises of a topic can share a word, each with its own sentence.
- **Derive eligibility from `description`.** They coincide today, but a description can exist only to disambiguate a sentence ([#194](https://github.com/pauk-slon/immer-wiederholen/pull/194)).

## Consequences

- Rendering a question never waits for image generation, and only rarely for R2.
- Editing a question's text orphans its cue: it's never shown for the wrong sentence, but the generator has to run again.
- A new cue can take up to 12 hours to appear for a question already looked up.
- The free tier allows about 90 images a day, so a full run takes several days (observed after #194, whose estimate was higher).
