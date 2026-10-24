# 0014. Illustrations are generated ahead of time

**Status:** Accepted, 2026-10-17 ([#194](https://github.com/pauk-slon/immer-wiederholen/pull/194))

## Context

A manual pilot suggested that an illustration of the sentence helps learners remember `_meaning` exercises. The project needed to generate the images, store them and show them in the bot with each question.

## Decision

- A one-off command generates the illustrations ("cues") ahead of time, not when the bot shows a question. Cloudflare Workers AI generates them, and Cloudflare R2 stores them. The choice was Cloudflare, because the project already had a Cloudflare account and the free tiers cover this volume ([#194](https://github.com/pauk-slon/immer-wiederholen/pull/194)).
- Each topic enables illustrations explicitly (`cue_generation`). This setting is separate from whether an exercise has a `description`.
- The bot only reads illustrations. On any failure, it shows a text question.

[0017](0017-cues-keyed-by-question-hash.md) describes how the bot finds illustrations.

## Alternatives considered

- **Derive the setting from `description`.** Today the two match. But a description can exist only to make a sentence unambiguous, and a new description shouldn't turn illustrations on ([#194](https://github.com/pauk-slon/immer-wiederholen/pull/194)).

## Consequences

- The bot never waits for image generation when it shows a question. To keep R2 out of that path too, the bot caches lookups in-process for 12 hours, including "no cue yet", so a new illustration can take up to 12 hours to appear.
- Someone has to run the generator after content changes.
- The free tier allows about 90 images a day, so a full run takes several days (observed after #194, which estimated more).
