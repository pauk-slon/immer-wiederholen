# 0011. Reminders count from the last session

**Status:** Accepted, 2026-10-15 ([#229](https://github.com/pauk-slon/immer-wiederholen/pull/229)). Amended by [0025](0025-second-reminder-for-a-streak.md). The 24-hour rule has existed since [#62](https://github.com/pauk-slon/immer-wiederholen/pull/62).

## Context

Since [#62](https://github.com/pauk-slon/immer-wiederholen/pull/62), a learner got one reminder after 24 hours without an answer, if something was due. The 24 hours were fixed for everyone. [#229](https://github.com/pauk-slon/immer-wiederholen/pull/229) let each learner choose the interval. Its description doesn't say what caused the change.

## Decision

With `/reminders`, a learner chooses how long after their **last answer** the reminder comes. The choices are 4, 8, 12 or 24 hours, or no reminders. A learner still gets at most one reminder per period of inactivity. The bot doesn't handle time zones.

## Alternatives considered

- **"Every N hours" or "N times a day".** Not chosen, because reminders would accumulate overnight and would keep coming to a learner who stopped practicing. An interval from the last session avoids both problems. Without a fixed schedule, the bot also doesn't need the learner's time zone ([#229](https://github.com/pauk-slon/immer-wiederholen/pull/229)).

## Consequences

- An inactive learner gets one reminder, not a series.
- An active learner can get several reminders a day, one after each session.
- A reminder can arrive at night. The learner's phone can mute it.
