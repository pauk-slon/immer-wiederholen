# 0009. One environment variable per store

**Status:** Accepted, 2026-08-23 ([#169](https://github.com/pauk-slon/immer-wiederholen/pull/169)). Every store added since then follows it.

## Context

When the student record got its own store ([0008](0008-student-record-separate-from-chat-state.md)), it could have used the same Redis URL as the FSM storage, because both are on the same Redis server.

## Decision

Each store has its own URL variable and its own database number, even though the stores use one server today. The variables are `STUDENT_RECORD_STORAGE_URL`, `BOT_FSM_STORAGE_URL`, and later `STUDENT_IDENTITY_STORAGE_URL` and `WEB_SESSION_STORAGE_URL`.

## Alternatives considered

- **One shared URL.** This needs fewer variables. But [#169](https://github.com/pauk-slon/immer-wiederholen/pull/169) notes that the stores are independent of each other. With a shared URL, a deployment couldn't move one store to another server without a change to the others.

## Consequences

- Any store can move to another server, or to another backend, with a change of one variable.
- An operator sets four variables instead of one (see [Configuration](../configuration.md#redis)).
- In CI, the stores are in different databases, so a test that reads from the wrong store fails there. With one shared database, it would pass.
