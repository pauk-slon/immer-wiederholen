# 0009. One environment variable per store

**Status:** Accepted, 2026-08-23 ([#169](https://github.com/pauk-slon/immer-wiederholen/pull/169)); followed for every store added since

## Context

When the student record got its own store ([0008](0008-student-record-separate-from-chat-state.md)), it could have shared the FSM storage's Redis URL: both live on the same Redis server.

## Decision

Each store has its own URL variable — `STUDENT_RECORD_STORAGE_URL`, `BOT_FSM_STORAGE_URL`, and later `STUDENT_IDENTITY_STORAGE_URL` and `WEB_SESSION_STORAGE_URL` — and its own database number, even though they point at one server today.

## Alternatives considered

- **One shared URL.** Fewer variables, but [#169](https://github.com/pauk-slon/immer-wiederholen/pull/169) notes the stores are conceptually independent, and a shared URL would stop a deployment from moving one of them to another server without touching the others.

## Consequences

- Any store can move to another server, or another backend, by changing one variable.
- Four variables to set instead of one (see [Configuration](../configuration.md#redis)).
- In CI the stores sit in different databases, so a test that reads from the wrong store fails there instead of passing because everything shares one database.
