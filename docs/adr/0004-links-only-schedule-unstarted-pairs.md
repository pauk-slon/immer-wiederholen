# 0004. Topic links only schedule pairs that haven't started

**Status:** Accepted, 2026-07-29 ([#107](https://github.com/pauk-slon/immer-wiederholen/pull/107))

## Context

A topic link (`chains`, `gates` or `chains_by_answer` in `topics.yaml`) makes an answer in one topic schedule a linked topic for the same word (see [Course format](../course-format.md#linking-topics)). Originally, `_expedite_dependent()` also moved the due date of an already scheduled linked pair to today, every time the learner answered the source topic.

For a one-way link, this only showed the linked pair earlier than its own interval required. For topics that link to each other, such as `partizip_ii` and `praeteritum`, it was a trap. Each correct answer to one topic reset the due date of the other topic to today. The intervals kept doubling, but the due dates never stayed. A learner reported that they had to answer the two forms of `ziehen` again and again. "Remaining today" stayed at 1, no matter how many correct answers they gave.

## Decision

`_expedite_dependent()` only creates an entry, due today, for a linked pair that has no entry. A link never changes a pair that already has an entry, because such a pair has its own schedule.

## Alternatives considered

[#107](https://github.com/pauk-slon/immer-wiederholen/pull/107) records no alternatives. It was a fix for the reported loop.

## Consequences

- Links do one thing. They give a pair its first entry. This is enough to unlock gated topics and to add a linked topic to today's new material.
- Topics can link to each other safely.
- A link no longer makes a topic that the learner already started due earlier. That topic follows its own interval.
