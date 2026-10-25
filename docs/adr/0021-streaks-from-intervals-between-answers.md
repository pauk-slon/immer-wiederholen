# 0021. Streaks count intervals between answers, not calendar days

**Status:** Accepted, 2026-10-25 ([#307](https://github.com/pauk-slon/immer-wiederholen/pull/307)). Discussed in [#306](https://github.com/pauk-slon/immer-wiederholen/issues/306).

## Context

Spaced repetition needs regular practice. After a missed day, due reviews accumulate, and the next session starts with many overdue pairs. A streak of practice without breaks rewards the behavior that the schedule needs.

A streak needs a rule for a break. The usual rule is "a calendar day without practice". But the bot doesn't know the learner's time zone, and its days are UTC days (see [Repetition schedule](../repetition-schedule.md)). For a learner in UTC−5, a UTC day changes at 7 in the evening. Practice at 20:00 one day and at 18:00 the next day falls on the same UTC day, so the streak would break for a reason that the learner can't see.

## Decision

The streak breaks when more than 36 hours pass between two answers to main exercises. Any answer counts, right or wrong. The next answer after a break starts a new streak.

The length is `floor((last answer − start) / 24 h) + 1`. Several sessions in one day don't make the streak longer. The student record stores only the start (`streak_started_at`). The time of the last answer is already in `last_exercise`.

36 hours is the smallest limit that lets a learner move the practice time by half a day, for example from 9:00 one day to 21:00 the next day.

## Alternatives considered

- **UTC calendar days.** Not chosen, because the break would come at a time that depends on the learner's time zone, which the bot doesn't know.
- **Calendar days in the learner's time zone.** Not chosen for now, because the bot would have to ask for the time zone or guess it. If days ever follow the learner's time zone, this alternative becomes possible.
- **A minimum number of answers per day, or all due reviews done.** Not chosen for the first version, because it needs the start and the end of a session. It can come later.
- **A separate "streak freeze" for a missed day.** Not needed. The 36-hour limit already forgives some missed days (see below).

## Consequences

- No time zone is needed, and the rule matches the reminders, which also count from the last answer (see [ADR 0011](0011-remind-after-the-last-session.md)).
- The bot knows exactly when a streak ends, so a reminder can say "the streak ends in 10 h".
- A learner who practices every 35 hours keeps the streak, although some calendar days have no practice. This is accepted. It works like a built-in streak freeze.
- A practice at 0:30 and the next one at 23:30 on the following day are 47 hours apart. This breaks the streak, although the learner practiced on two consecutive days.
- Records from before streaks have no start. Their streak starts with the next answer, and no break is reported.
