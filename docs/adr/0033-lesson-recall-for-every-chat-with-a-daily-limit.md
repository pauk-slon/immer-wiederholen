# 0033. Every chat gets lesson recalls, with a daily limit

**Status:** Accepted, 2026-11-23 ([#382](https://github.com/pauk-slon/immer-wiederholen/pull/382)). It amends [0031](0031-model-writes-and-checks-a-lesson-recall.md).

## Context

[ADR 0031](0031-model-writes-and-checks-a-lesson-recall.md) put the lesson recall behind the `lesson_recall` feature flag, because it was an experiment. The test chats used it, and the checks of the translations were reliable. Now all learners should get it free of charge, at least for some time.

Each lesson recall costs model calls. With Claude Haiku 5.5, one generation and its checks cost about $0.0024, measured in the traces of two weeks. A learner with two lessons a day costs about $0.15 a month. But nothing stopped a learner from doing many more lessons, so the cost had no upper limit.

ADR 0031 also left two questions for this step. Should the bot tell the learner that the text goes to Anthropic? And [ADR 0032](0032-ai-mode-removed.md) asked for a review of [ADR 0006](0006-ai-generation-fails-visibly.md) before the feature opens to everyone.

## Decision

- **`ANTHROPIC_API_KEY` turns on the lesson recall for every chat.** The `lesson_recall` flag is removed. Without the key, the bot has no lesson recall, the same as other optional integrations. The key has no other use, so the bot doesn't start if the key is set but the course has no `lesson_recall.md`.
- **A chat gets 3 lesson recalls in 24 hours.** The 24 hours move with time, because the bot doesn't know the learner's time zone. Only a generated task counts, so a failed generation doesn't use up the limit. After the limit, a lesson works as a lesson without a lesson recall.
- **The `lesson_recall_unlimited` flag removes the limit** for its chats, for example the author and test chats. The bot doesn't start if the flag has a chat but the key is missing.
- **The bot doesn't tell the learner that the text goes to Anthropic.** The learner translates a sentence that the bot gave, so a translation almost never has personal data. The request has no chat id and no name. The Anthropic API doesn't use the requests to train models by default. A privacy policy of the bot can name Anthropic, outside the code.
- **ADR 0006 stays.** A failed generation shows an error message with a button to the next exercise, so a failure doesn't stop a learner. A silent fallback would show an unchecked verdict, and this is worse for all learners than for test chats.

## Alternatives considered

- **Keep the `lesson_recall` flag and allow `*` for all chats.** Not chosen. A flag that is on for everyone has no use, and the key already shows whether the bot can call the model.
- **A free model instead of Haiku.** Not chosen. In 37 translations, the best free model on Workers AI (gpt-oss-120b) rejected a correct translation, broke a correct word in a correction, and never showed the practiced form after a correct free translation. It was 3 to 4 times slower, and the free plan allows about 120 checks a day. Haiku gave 37 correct verdicts. The free tier of Gemini uses the requests to improve Google's products.
- **A calendar day for the limit.** Not chosen. Without the time zone, the day would end at a random hour of the learner's day.
- **Count a lesson recall at its start.** Not chosen. A failed generation would then use up the limit, and the learner got nothing for it.
- **A message about Anthropic before the first lesson recall.** Not chosen, for the reasons in the decision.

## Consequences

- Every learner gets lesson recalls, and the cost is at most 3 lesson recalls a day for each chat without the unlimited flag.
- The limit is per chat, in the FSM data, so `/reset` doesn't change it.
- The learner doesn't see that the limit was reached. "Continue" shows the next exercise, as in a lesson without a lesson recall.
- `lesson_recall.limit_reached` in the traces shows how often learners reach the limit. If many learners reach it, the limit can go up.
- An old `lesson_recall` entry in `BOT_FEATURE_FLAGS` has no effect, because the bot ignores flags that it doesn't know.
