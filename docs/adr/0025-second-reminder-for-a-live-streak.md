# 0025. A live streak gets a second reminder

**Status:** Accepted, 2026-10-31 ([#314](https://github.com/pauk-slon/immer-wiederholen/pull/314)). Amends [ADR 0011](0011-remind-after-the-last-session.md).

## Context

[ADR 0011](0011-remind-after-the-last-session.md) gives a learner one reminder per period of inactivity. A learner with a 4-hour interval gets this reminder 32 hours before the streak ends (see [ADR 0021](0021-streaks-from-intervals-between-answers.md)). If the learner forgets about it, the bot says nothing more and the streak breaks. With the default interval of 24 hours, this problem doesn't occur, because the reminder comes 12 hours before the streak ends.

## Decision

If a learner already got a reminder and the streak is alive, the bot sends one more reminder 24 hours after the last answer. If the first reminder came at that time or later, the bot sends no second reminder. So only intervals of 4, 8 and 12 hours get a second reminder.

24 hours is the one time before the break that needs no time zone. It is the time of day when the learner last practiced, so the learner is probably awake. The learner also has 12 hours left.

The reminder already says when the streak ends, so the text doesn't change. `last_reminded_at` is sufficient to find out which reminder is next, so the student record doesn't change.

## Alternatives considered

- **A reminder a fixed time before the break, such as 6 hours.** Not chosen, because it can come at night. After a session at 20:00, it comes at 2:00.
- **The learner's time zone with quiet hours.** Not chosen, because the bot would have to ask for the time zone, and a reminder at 24 hours is already at a suitable time of day (see [ADR 0021](0021-streaks-from-intervals-between-answers.md)).
- **A third reminder close to the break.** Not chosen, because it can come at night, and 12 hours are sufficient to practice.
- **Delete the first reminder when the second one comes.** Not chosen, because a chat keeps its history, and the time of the message explains its text. The first reminder loses only its button.

## Consequences

- A learner with a streak gets at most two reminders per period of inactivity. A learner without a streak still gets one.
- A learner who stopped practicing gets no more reminders after the streak breaks, so the concern about a series of reminders in ADR 0011 doesn't apply.
- The notification of the first reminder stays on the phone until the learner opens the chat, because Telegram can remove a notification only together with its message.
