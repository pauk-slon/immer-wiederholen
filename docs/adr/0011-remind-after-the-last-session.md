# 0011. Reminders count from the last session

**Status:** Accepted, 2026-10-15 ([#229](https://github.com/pauk-slon/immer-wiederholen/pull/229)); the 24-hour rule since [#62](https://github.com/pauk-slon/immer-wiederholen/pull/62)

## Context

Since [#62](https://github.com/pauk-slon/immer-wiederholen/pull/62), a learner got one reminder after 24 hours without answering, if something was due, at a fixed interval for everyone. [#229](https://github.com/pauk-slon/immer-wiederholen/pull/229) made the interval a learner's choice; its description doesn't say what prompted it.

## Decision

`/reminders` lets a learner pick how long after their **last answer** the reminder comes — 4, 8, 12 or 24 hours — or turn reminders off. It's still at most one reminder per period of inactivity. There's no time zone handling.

## Alternatives considered

- **"Every N hours" or "N times a day".** Not chosen: reminders would pile up overnight and keep nagging a learner who has stopped practicing. Counting from the last session avoids both, and without a schedule there's no need for the learner's time zone ([#229](https://github.com/pauk-slon/immer-wiederholen/pull/229)).

## Consequences

- An inactive learner gets one reminder, not a series.
- An active learner can get several a day, one after each session.
- Muting at night is left to the phone; a reminder can arrive at night.
