# 0007. Save a student record only when it changes

**Status:** Accepted, 2026-08-23 ([#169](https://github.com/pauk-slon/immer-wiederholen/pull/169))

## Context

Every handler that uses a learner's record loads it and lets `Tutor` change it. Then the handler may or may not need to save it. An answer always changes the record, `/progress` never does, and the reminder changes it only when it actually sends a reminder. When the record moved into its own store, `StudentRecordBook`, each of these handlers needed a way to save correctly without save logic of its own.

## Decision

`StudentRecordBook.check_out(student_id)` is an async context manager. It loads the record, makes a deep copy and yields the record for changes in place. When the block ends, it saves the record only if the record differs from the copy. The comparison runs in a `finally` block, so a change made before an error is still saved. There's no public save method.

## Alternatives considered

[#169](https://github.com/pauk-slon/immer-wiederholen/pull/169) records no alternatives.

## Consequences

- Handlers contain no save calls and no conditional writes. Handlers that only read don't write.
- A change made before a failure isn't lost. For example, if the answer was recorded and then the reply failed, the answer stays.
- Every `check_out()` costs a deep copy and a comparison (observed, not discussed in #169).
- Two concurrent `check_out()` calls for one record can overwrite each other's changes (observed later, [#249](https://github.com/pauk-slon/immer-wiederholen/issues/249)).
