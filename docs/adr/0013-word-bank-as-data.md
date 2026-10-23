# 0013. Word banks are data, not text in the question

**Status:** Accepted, 2026-08-26 ([#190](https://github.com/pauk-slon/immer-wiederholen/pull/190), from [#191](https://github.com/pauk-slon/immer-wiederholen/issues/191))

## Context

Word-order exercises showed their scrambled words as text written into `question`, e.g. `'...sondern ___. (in Hamburg / wohnt / sie)'`. The web widget was getting a tap-to-arrange tile UI, which needed the pieces as a list. Two problems ([#191](https://github.com/pauk-slon/immer-wiederholen/issues/191)):

- the parenthetical was a hand-scrambled copy of `answer` that authors kept in sync by hand, with nothing checking it;
- the pieces are phrases, not words — `in Hamburg` is one piece — so splitting `answer` on spaces would have made a different, more fragmented exercise.

## Decision

`Exercise.word_bank` holds the answer's pieces in the correct order, validated at load time: joined with spaces, they must equal `answer`. `question` no longer contains them. Each frontend shuffles them at render time with the shared `shuffle_word_bank()`: the bot re-creates the parenthetical, the web widget shows tiles. A non-empty `word_bank` is the only signal; there's no separate `topics.yaml` flag.

## Alternatives considered

- **Split `answer` on spaces** (the first version of #190). No new field, but the wrong granularity.
- **A `word_order` flag in `topics.yaml`** (also in an earlier version of #190). Dropped: `word_bank` itself says how to render the exercise, as `choices: null` does for typed answers.

## Consequences

- One source of truth, checked on every load.
- Checking an answer needed no change: the arranged pieces, joined, are the answer.
- The content had to be migrated: 54 exercises, done with a one-off script in the content repo.
- Changing `question` changed those exercises' illustration keys (see [0014](0014-cues-generated-ahead-keyed-by-question.md)).
