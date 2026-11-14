# 0027. Streaks count finished lessons, not answers

**Status:** Accepted, 2026-11-14 ([#330](https://github.com/pauk-slon/immer-wiederholen/pull/330)). Supersedes [ADR 0021](0021-streaks-from-intervals-between-answers.md). Amends [ADR 0025](0025-second-reminder-for-a-streak.md) and [ADR 0026](0026-lessons-in-conversation-state.md). The feature is discussed in [#325](https://github.com/pauk-slon/immer-wiederholen/issues/325).

## Context

[ADR 0021](0021-streaks-from-intervals-between-answers.md) counts the streak from answers. Any answer to a main exercise is practice. The streak breaks when more than 36 hours pass between two answers, and an answer adds a day if it comes at least 18 hours after the answer that added the previous day.

[#325](https://github.com/pauk-slon/immer-wiederholen/issues/325) groups exercises into lessons (see [ADR 0026](0026-lessons-in-conversation-state.md)). One tap is too little practice for a streak day. With lessons of several exercises, a finished lesson is a clear unit of practice. For now, a lesson has one exercise, so each answer finishes a lesson.

## Decision

A finished lesson is practice for the streak, instead of a single answer. A lesson is finished when the learner answers its last exercise, right or wrong. A lesson that is shorter than the lesson size, because less material is available, also counts. Recall answers still don't count.

The intervals of ADR 0021 stay, but they count from finished lessons:

- The streak breaks when more than 36 hours pass without a finished lesson. `breaks_at` is the time of the last finished lesson plus 36 hours.
- A lesson adds a day if it is finished at least 18 hours after the lesson that added the previous day.

The student record stores the time of the last finished lesson as `last_lesson_finished_at`. A record without this field uses the time of the last answer, `last_exercise.answered_at`.

The answer to the last exercise of a lesson finishes the lesson, also if the lesson started on an earlier day. A lesson from an earlier day gives no more exercises (see ADR 0026), but the learner can still answer the exercise that it gave last.

The streak reminder of [ADR 0025](0025-second-reminder-for-a-streak.md) counts from the last finished lesson, as `breaks_at` does. The usual reminder still counts from the last answer. The streak reminder can now come without an earlier reminder, because an answer in an unfinished lesson puts the usual reminder off.

## Alternatives considered

- **Break the streak by the last answer, and add days by finished lessons.** Not chosen, because one answer every 36 hours would keep the streak forever without any finished lesson.
- **Count a number of answers for a day.** Not chosen, because the rule "a lesson is practice" is clearer to the learner, and the answers would need their own count across lessons.
- **A minimum lesson size for a streak day.** Not chosen, because a learner who selected a small topic in `/topics` would lose days.
- **Finish a lesson only on the day when it started.** Not chosen, because a learner who answers yesterday's last exercise in the morning would get no day for it.
- **The streak reminder from the last answer.** Not chosen, because an answer in an unfinished lesson would move the reminder past `breaks_at`.

## Consequences

- With lessons of one exercise, every answer finishes a lesson, so the streak works as before. A record from before this change uses the time of its last answer, which is the same time, so no migration is needed.
- A learner who stops in the middle of a lesson gets no day for it, although one answer was enough before. Answers in an unfinished lesson don't keep the streak either.
- The bot and the web app have their own lessons, but the streak is in the student record. A finished lesson in either frontend counts.
- `Tutor` reports `StreakExtended` and `StreakBroken` after `LessonFinished`, not after every answer.
