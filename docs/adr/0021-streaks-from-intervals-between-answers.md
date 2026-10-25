# 0021. Streaks count intervals between answers, not calendar days

**Status:** Accepted, 2026-10-25 ([#307](https://github.com/pauk-slon/immer-wiederholen/pull/307)). The feature is discussed in [#306](https://github.com/pauk-slon/immer-wiederholen/issues/306).

## Context

A streak needs a rule for a break and a way to count days. The usual rule is "a calendar day without practice". But the bot doesn't know the learner's time zone, and its days are UTC days. For a learner in UTC−5, a UTC day changes at 7 in the evening, so a streak would break for a reason that the learner can't see.

## Decision

The streak uses only the times of answers, not calendar days. It breaks when more than 36 hours pass between two answers. An answer adds a day if it comes at least 18 hours after the answer that added the last day. The record stores the number of days and the time of that answer. [Repetition schedule](../repetition-schedule.md#streak) describes the rules and shows examples.

36 hours is the smallest limit that lets a learner move the practice time by half a day. 18 hours is more than the time between two sessions on one day, such as 8:00 and 20:00.

## Alternatives considered

- **UTC calendar days.** Not chosen, because the break would come at a time that depends on the learner's time zone.
- **Calendar days in the learner's time zone.** Not chosen for now, because the bot would have to ask for the time zone.
- **The time since the first answer, in days.** The first version of [#307](https://github.com/pauk-slon/immer-wiederholen/pull/307) used `floor((last answer − start) / 24 h) + 1`. Not chosen, because it shows too few days. Sessions at 20:00 and at 9:00 the next day give 1 day.
- **12 hours for a new day.** Not chosen, because two sessions on one day would add 2 days.

## Consequences

- No time zone is needed, and the rule matches the reminders, which also count from the last answer (see [ADR 0011](0011-remind-after-the-last-session.md)). A reminder can say when the streak ends.
- Without a time zone, the count is wrong in some cases. A switch from evening to morning sessions loses a day. A learner who practices every 35 hours keeps the streak, although some calendar days have no practice.
- If days ever follow the learner's time zone, the stored count and the rules change, and existing streaks need a migration or a reset.
