# 0025. A live streak gets a second reminder

**Status:** Accepted, 2026-10-31 ([#314](https://github.com/pauk-slon/immer-wiederholen/pull/314)). Amends [ADR 0011](0011-remind-after-the-last-session.md).

## Context

[ADR 0011](0011-remind-after-the-last-session.md) gives a learner one reminder per period of inactivity. A learner with a 4-hour interval gets this reminder 32 hours before the streak ends (see [ADR 0021](0021-streaks-from-intervals-between-answers.md)). If the learner forgets about it, the bot says nothing more and the streak breaks. With the default interval of 24 hours, this problem doesn't occur, because the reminder comes 12 hours before the streak ends.

## Decision

A learner who already got a reminder gets one more reminder if all of these conditions are true:

- **The streak has at least 2 days.** Every first answer creates a streak of 1 day, so a lower limit would remind a learner who tried the bot once. Such a learner has no streak to protect.
- **The time is in the hour after the 24-hour mark since the last answer.** 24 hours is the one time before the break that needs no time zone. It is the time of day when the learner last practiced, so the learner is probably awake. The learner also has about 12 hours left. The reminder process runs every 15 minutes, so 1 hour is sufficient. After this hour, the bot sends no second reminder, because the time of day could be wrong and little time would be left.
- **The first reminder came at least 6 hours before the mark.** The first reminder can come late, because the bot sends no reminder while there's nothing to practice. Without this limit, two similar messages could come minutes apart. The limit is 6 hours and not 12 hours, because the first reminder of a 12-hour interval can come some minutes after 12 hours.

With the default interval of 24 hours, the first reminder comes after the mark, so this learner gets no second reminder.

The reminder already says when the streak ends, so the text doesn't change. `last_reminded_at` is sufficient to find out which reminder is next, so the student record doesn't change.

## Alternatives considered

- **A reminder a fixed time before the break, such as 6 hours.** Not chosen, because it can come at night. After a session at 20:00, it comes at 2:00.
- **The learner's time zone with quiet hours.** Not chosen, because the bot would have to ask for the time zone, and a reminder at 24 hours is already at a suitable time of day (see [ADR 0021](0021-streaks-from-intervals-between-answers.md)).
- **A third reminder close to the break.** Not chosen, because it can come at night, and 12 hours are sufficient to practice.
- **Delete the first reminder when the second one comes.** Not chosen, because a chat keeps its history, and the time of the message explains its text. The first reminder loses only its button.

## Consequences

- A learner with a streak of at least 2 days gets at most two reminders per period of inactivity. Other learners still get one.
- A learner who stopped practicing gets no more reminders after the hour at the 24-hour mark, so the concern about a series of reminders in ADR 0011 doesn't apply.
- If the reminder process doesn't run in that hour, the learner gets no second reminder. This also means that a deploy doesn't send second reminders to all learners at once.
- A learner who changes the interval from 4 to 24 hours after the first reminder can still get the second reminder. This is harmless, because the learner would get a reminder at that time anyway.
- If the learner opened a question after the first reminder and didn't answer, the second reminder removes the buttons of that question, as the first reminder already does. The new reminder has its own button for the next exercise.
- The notification of the first reminder stays on the phone until the learner opens the chat, because Telegram can remove a notification only together with its message.
