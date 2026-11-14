# 0028. A lesson expires after two hours without activity, not at the end of a day

**Status:** Accepted, 2026-11-14 ([#332](https://github.com/pauk-slon/immer-wiederholen/pull/332)). Amends [ADR 0026](0026-lessons-in-conversation-state.md). The feature is discussed in [#325](https://github.com/pauk-slon/immer-wiederholen/issues/325).

## Context

[ADR 0026](0026-lessons-in-conversation-state.md) lets a lesson give exercises only on the day when it started. The day is a UTC day, because the bot doesn't know the learner's time zone. For a learner in UTC−5, a UTC day changes at 7 in the evening, so a lesson can stop in the middle of a session. [ADR 0021](0021-streaks-from-intervals-between-answers.md) rejected UTC days for the streak for the same reason.

With lessons of several exercises, a lesson also needs a limit within a day. A lesson that the learner left in the morning shouldn't continue in the evening as if no time passed.

## Decision

A lesson stores the time of its last activity as `active_at`, instead of the day when it started. Activity is the start of the lesson, an exercise that the lesson gives and an answer to the lesson. A lesson gives exercises only if its last activity was at most 2 hours ago (`Lesson.EXPIRES_AFTER`). After that, `next_exercise()` starts a new lesson, and the pairs of the old lesson come back as due reviews.

Because an answer is activity, the lesson continues if the learner answers an exercise that waited for more than 2 hours.

The answer to the last exercise still finishes a lesson after it expired (see [ADR 0027](0027-streaks-count-finished-lessons.md)).

## Alternatives considered

- **The UTC day, as in ADR 0026.** Not chosen, because the lesson stops at a time that depends on the learner's time zone.
- **1 hour, the same time as in `WebSessionStore`.** Not chosen, because a break of an hour is usual in a chat, for example for a call or a meal.
- **More than 4 hours.** Not chosen, because the shortest reminder comes 4 hours after the last answer. After a reminder, a new lesson is a better start than the rest of an old one.
- **The time since the start of the lesson.** Not chosen, because a learner who takes long over one exercise would lose the lesson while practicing.

## Consequences

- After a reminder, a learner who left between two exercises gets a new lesson. A learner who left an exercise without an answer gets that exercise again, and the answer lets the old lesson continue.
- A lesson can continue after midnight UTC. Its new words count for the limit of the day when the learner answers them, and the next lesson chooses new words by that count. So the daily limit still holds.
- In the web app, the session and the lesson in `WebSessionStore` expire after 1 hour, so the lesson there lives at most 1 hour.
- A lesson saved with `date` before this change has no `active_at`, so it counts as expired. It gives no more exercises, but the answer to the exercise that it gave still finishes it, so that answer still counts for the streak.
