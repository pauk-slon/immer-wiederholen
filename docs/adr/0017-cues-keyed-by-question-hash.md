# 0017. Illustrations are keyed by the question's hash

**Status:** Accepted, 2026-10-17 ([#194](https://github.com/pauk-slon/immer-wiederholen/pull/194), `CLAUDE.md`)

## Context

The generator uploads an illustration for an exercise, and the bot looks for it when it shows the question ([0014](0014-cues-generated-ahead.md)). Both need the same key for the same exercise. The key must also be different for exercises that need different pictures.

## Decision

The key is `Exercise.cue_key`, the SHA-256 of the exercise's `question`. One property computes it, and both the generator and the bot use that property.

## Alternatives considered

- **Key by word and topic.** This key isn't unique, because several exercises of one `_meaning` topic can share a word, each with its own sentence and picture ([#194](https://github.com/pauk-slon/immer-wiederholen/pull/194), `CLAUDE.md`).

## Consequences

- The generator and the bot can't disagree about a key.
- If you edit the text of a question, its old illustration is no longer used. The bot never shows it for the wrong sentence. But the question has no illustration until the generator runs again.
- The unused images stay in R2, and nothing removes them (observed, not discussed in #194).
