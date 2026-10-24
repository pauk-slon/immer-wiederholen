# 0013. Word banks are data, not text in the question

**Status:** Accepted, 2026-08-26 ([#190](https://github.com/pauk-slon/immer-wiederholen/pull/190), from [#191](https://github.com/pauk-slon/immer-wiederholen/issues/191))

## Context

Word-order exercises showed their scrambled words as text in `question`, for example `'...sondern ___. (in Hamburg / wohnt / sie)'`. The web widget was about to get tiles that the learner arranges with taps, and the tiles needed the pieces as a list. [#191](https://github.com/pauk-slon/immer-wiederholen/issues/191) found two problems:

- The text in parentheses was a scrambled copy of `answer`. Authors kept it in sync by hand, and nothing checked it.
- The pieces are phrases, not words. For example, `in Hamburg` is one piece. A split of `answer` on spaces would have made a different exercise with more pieces.

## Decision

`Exercise.word_bank` holds the pieces of the answer in the correct order. The loader validates them. Joined with spaces, they must equal `answer`. `question` no longer contains them. Each frontend shuffles them when it shows the exercise, with the shared `shuffle_word_bank()`. The bot creates the text in parentheses again, and the web widget shows tiles. A non-empty `word_bank` is the only signal for a word-order exercise. There is no separate setting in `topics.yaml`.

## Alternatives considered

- **Split `answer` on spaces** (the first version of #190). This needs no new field, but the pieces are too small.
- **A `word_order` setting in `topics.yaml`** (also in an earlier version of #190). It was dropped, because `word_bank` itself says how to show the exercise, in the same way as `choices: null` does for typed answers.

## Consequences

- There is one source of truth, and every load checks it.
- The answer check needed no change, because the arranged pieces, joined, are the answer.
- The content needed a migration of 54 exercises. A one-off script in the content repo did it.
