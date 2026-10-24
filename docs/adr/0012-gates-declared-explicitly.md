# 0012. Gates are declared explicitly

**Status:** Accepted, 2026-07-22 ([#79](https://github.com/pauk-slon/immer-wiederholen/pull/79)). Replaces the derived gating of [#74](https://github.com/pauk-slon/immer-wiederholen/pull/74).

## Context

Some topics make sense only after another topic. For example, a sentence with a Partizip II form makes sense only after the form itself. [#74](https://github.com/pauk-slon/immer-wiederholen/pull/74) derived this from the chain configuration. A topic that appeared only as a dependent of another topic was locked until the learner answered its source.

Some topics chain to each other, so that an answer to either topic makes the other due earlier. Examples are `partizip_ii` and `praeteritum`. With derived gating, such topics would lock each other. Each would wait for the other to unlock.

## Decision

`topics.yaml` declares the two relations separately for each source topic ([#79](https://github.com/pauk-slon/immer-wiederholen/pull/79)). `chains` only schedule. `gates` schedule and also lock the topic until the learner answers the source. A gated topic doesn't need to appear in `chains` too.

## Alternatives considered

- **Derive gating from the chain graph** (#74). This needs one list instead of two. But it can't express "make due earlier, but don't lock", and mutual chains would lock each other forever.

## Consequences

- Topics can chain to each other without locking.
- Course authors decide about locking explicitly (see [Course format](../course-format.md#linking-topics)).
- Two topics that gate each other would still lock each other forever. The format leaves this to the author.
