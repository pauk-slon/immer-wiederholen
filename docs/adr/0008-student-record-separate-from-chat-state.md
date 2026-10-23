# 0008. Keep the student record separate from chat state

**Status:** Accepted, 2026-08-23 ([#169](https://github.com/pauk-slon/immer-wiederholen/pull/169))

## Context

All per-chat state — the learning schedule, the language, the exercise being answered, which message has live buttons — lived in aiogram's FSM storage. A second frontend, a web widget on a landing page, was planned. It would need the learner's schedule, but not a Telegram chat's language or pending buttons.

## Decision

The student record — the learner's schedule and progress — moves into its own transport-agnostic store, `StudentRecordBook` in `wiederholen.school`, addressed by a plain `StudentID`. Everything else about a Telegram chat stays in aiogram's FSM storage, used as aiogram ships it, without a custom storage subclass. The same pull request split the code into `wiederholen.school` (learning, shared by every frontend) and `wiederholen.bot` (Telegram).

## Alternatives considered

None are recorded in [#169](https://github.com/pauk-slon/immer-wiederholen/pull/169).

## Consequences

- The web app could reuse the same records when it was added the same day ([#176](https://github.com/pauk-slon/immer-wiederholen/pull/176)), with its own session store for the shown exercise.
- `/reset` wipes the record and leaves chat settings alone.
- Each new piece of per-chat state needs a decision about which store it belongs to; the question is whether another frontend would need it.
