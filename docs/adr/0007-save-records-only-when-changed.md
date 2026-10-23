# 0007. Save a student record only when it changes

**Status:** Accepted, 2026-08-23 ([#169](https://github.com/pauk-slon/immer-wiederholen/pull/169))

## Context

Every handler that touches a learner's record loads it, lets `Tutor` change it, and may or may not need to write it back: recording an answer always changes it, `/progress` never does, the reminder changes it only when a reminder is actually sent. When the record moved into its own store, `StudentRecordBook`, each of these needed a way to persist correctly without its own save logic.

## Decision

`StudentRecordBook.check_out(student_id)` is an async context manager. It loads the record, takes a deep copy, yields the record for changing in place, and when the block ends saves it only if it differs from the copy. The comparison runs in a `finally` block, so a change made before an error is still saved. There's no public save method.

## Alternatives considered

None are recorded in [#169](https://github.com/pauk-slon/immer-wiederholen/pull/169).

## Consequences

- Handlers contain no save calls and no conditional writes; read-only handlers don't write.
- A change made before a failure — the answer recorded, the reply failed — isn't lost.
- Every check-out costs a deep copy and a comparison (observed, not discussed in #169).
- Two concurrent check-outs of one record can overwrite each other's changes (observed later, [#249](https://github.com/pauk-slon/immer-wiederholen/issues/249)).
