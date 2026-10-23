# 0012. Gates are declared explicitly

**Status:** Accepted, 2026-07-22 ([#79](https://github.com/pauk-slon/immer-wiederholen/pull/79)); replaces the derived gating of [#74](https://github.com/pauk-slon/immer-wiederholen/pull/74)

## Context

Some topics only make sense after another — a sentence using a Partizip II form after the form itself. [#74](https://github.com/pauk-slon/immer-wiederholen/pull/74) derived this from the chain configuration: a topic that only ever appeared as a dependent of another was locked until its source was answered.

Some topics chain to each other, so that answering either brings the other forward — `partizip_ii` and `praeteritum`. Under derived gating, making them depend on each other would lock both: each would wait for the other to unlock.

## Decision

`topics.yaml` declares the two relations separately per source topic ([#79](https://github.com/pauk-slon/immer-wiederholen/pull/79)): `chains` only schedule, `gates` schedule and lock until the source is answered. A gated topic doesn't need to be repeated in `chains`.

## Alternatives considered

- **Derive gating from the chain graph** (#74). One list instead of two, but it can't express "bring forward, don't lock", and mutual chains would deadlock.

## Consequences

- Topics can chain to each other without locking.
- Course authors decide locking explicitly (see [Course format](../course-format.md#linking-topics)).
- Two topics gating each other would still deadlock; the format leaves that to the author.
