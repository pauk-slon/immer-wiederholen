# 0017. Illustrations are keyed by the question's hash

**Status:** Accepted, 2026-10-17 ([#194](https://github.com/pauk-slon/immer-wiederholen/pull/194), `CLAUDE.md`)

## Context

The generator uploads an illustration for an exercise, and the bot looks it up when showing the question ([0014](0014-cues-generated-ahead.md)). Both need the same key for the same exercise, and the key has to tell apart exercises that need different pictures.

## Decision

The key is `Exercise.cue_key`, the SHA-256 of the exercise's `question`, computed in one property used by both the generator and the bot.

## Alternatives considered

- **Key by word and topic.** Not unique: several exercises of one `_meaning` topic can share a word, each with its own sentence and picture ([#194](https://github.com/pauk-slon/immer-wiederholen/pull/194), `CLAUDE.md`).

## Consequences

- The generator and the bot can't disagree about a key.
- Editing a question's text orphans its illustration: it's never shown for the wrong sentence, but the question has none until the generator runs again.
- Orphaned images stay in R2; nothing removes them (observed, not discussed in #194).
