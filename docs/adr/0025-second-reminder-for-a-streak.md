# 0025. A streak of 2 days or more gets a second reminder

**Status:** Accepted, 2026-10-31 ([#314](https://github.com/pauk-slon/immer-wiederholen/pull/314)). Amends [ADR 0011](0011-remind-after-the-last-session.md).

## Context

[ADR 0011](0011-remind-after-the-last-session.md) gives a learner one reminder per period of inactivity. A learner with a 4-hour interval gets this reminder 32 hours before the streak breaks (see [ADR 0021](0021-streaks-from-intervals-between-answers.md)). If the learner forgets the reminder, the bot says nothing more and the streak breaks. With the default interval of 24 hours, this problem doesn't occur, because the reminder comes 12 hours before the streak breaks.

## Decision

A learner who already got a reminder gets one more reminder if all of these conditions are true:

- The streak has at least 2 days.
- The time is in the hour after the 24-hour mark since the last answer.
- The first reminder came at least 6 hours before the mark.

So only the intervals of 4, 8 and 12 hours can get a second reminder. With the default interval of 24 hours, the first reminder comes after the mark.

Every first answer creates a streak of 1 day. With a limit of 1 day, the bot would remind a learner who tried the bot once. Such a learner has no streak to protect.

24 hours is the only time before the break when the bot can expect a suitable time of day without a time zone. It is the time of day when the learner last practiced, so the learner is probably awake. The learner also has about 12 hours left. The reminder process runs every 15 minutes, so 1 hour is enough. A later reminder can come at night, and fewer hours are left.

The first reminder can come late, because the bot sends no reminder while there's nothing to practice. Without the gap, two similar messages could come minutes apart. 6 hours is an estimate. With this gap, the second message is a new reminder and not a repeat of the first one. The gap is not 12 hours, because the first reminder of a 12-hour interval can come some minutes after 12 hours.

The reminder already says when the streak breaks, so the text doesn't change. `last_reminded_at` is enough to decide which reminder is next, so the student record doesn't change.

## Alternatives considered

- **Keep one reminder.** Not chosen, because a learner with a short interval gets no warning when the streak has few hours left.
- **A reminder a fixed time before the break, such as 6 hours.** Not chosen, because it can come at night. After a session at 20:00, it comes at 2:00.
- **The learner's time zone with quiet hours.** Not chosen, because the bot would have to ask for the time zone, and a reminder at 24 hours is already at a suitable time of day (see [ADR 0021](0021-streaks-from-intervals-between-answers.md)).
- **A third reminder close to the break.** Not chosen, because it can come at night, and 12 hours are enough to practice.
- **Delete the first reminder when the second one comes.** Not chosen, because a chat keeps its history, and the time of the message explains its text.

## Consequences

- A learner with a streak of at least 2 days gets at most two reminders per period of inactivity. Other learners still get at most one.
- A learner who stopped practicing gets no second reminder after the hour after the 24-hour mark, so the bot never sends a series of reminders. This is the concern of ADR 0011.
- If the reminder process doesn't run in the hour after the 24-hour mark, the learner gets no second reminder. For the same reason, the first sweep after a deploy or a stop of the process doesn't send second reminders to all learners. It sends them only to learners in that hour.
- A learner who changes the interval from 4 to 24 hours after the first reminder can still get the second reminder. This is acceptable, because the learner still gets at most two reminders.
- If the learner opened a question after the first reminder and didn't answer, the second reminder removes the buttons of that question, as the first reminder already does. The new reminder has its own button for the next exercise.
- The first reminder stays in the chat and loses only its button. Its notification stays on the phone until the learner opens the chat or dismisses it, because Telegram can remove a notification only together with its message.
