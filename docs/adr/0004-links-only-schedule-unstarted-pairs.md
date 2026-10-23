# 0004. Topic links only schedule pairs that haven't started

**Status:** Accepted, 2026-07-29 ([#107](https://github.com/pauk-slon/immer-wiederholen/pull/107))

## Context

A topic link (`chains`, `gates`, `chains_by_answer` in `topics.yaml`) makes an answer in one topic schedule a linked topic for the same word (see [Course format](../course-format.md#linking-topics)). Originally, `_expedite_dependent()` also pulled an already-scheduled linked pair's due date forward to today, every time the source topic was answered.

For a one-way link this only showed the linked pair sooner than its own interval asked for. For topics that link to each other — `partizip_ii` and `praeteritum` — it was a trap: each correct answer to one topic reset the other's due date to today. The intervals kept doubling, but the due dates never held. A learner reported being stuck answering `ziehen`'s two forms over and over, with "remaining today" at 1 no matter how many correct answers they gave.

## Decision

`_expedite_dependent()` only creates an entry, due today, for a linked pair that has none. A pair that already has an entry — that has its own schedule — is never changed by a link.

## Alternatives considered

None are recorded in [#107](https://github.com/pauk-slon/immer-wiederholen/pull/107), which was a fix for the reported loop.

## Consequences

- Links do one thing: give a pair its first entry. That's enough to unlock gated topics and to bring a linked topic into today's new material.
- Topics may link to each other safely.
- A link no longer brings forward a topic the learner has already started; that topic follows its own interval.
