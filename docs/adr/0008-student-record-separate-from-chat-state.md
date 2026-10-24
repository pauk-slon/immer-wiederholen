# 0008. Keep the student record separate from chat state

**Status:** Accepted, 2026-08-23 ([#169](https://github.com/pauk-slon/immer-wiederholen/pull/169))

## Context

All state of a chat was in aiogram's FSM storage. This included the learning schedule, the language, the exercise that the learner was answering and the message with active buttons. A second frontend was planned, a web widget on a landing page. It would need the learner's schedule, but not the language of a Telegram chat or its pending buttons.

## Decision

The student record, which is the learner's schedule and progress, moves into its own store, `StudentRecordBook` in `wiederholen.school`. This store doesn't depend on Telegram or HTTP, and a plain `StudentID` addresses its records. The rest of a Telegram chat's state stays in aiogram's FSM storage. The bot uses that storage without a custom storage subclass. The same pull request split the code into `wiederholen.school` (learning, shared by all frontends) and `wiederholen.bot` (Telegram).

## Alternatives considered

[#169](https://github.com/pauk-slon/immer-wiederholen/pull/169) records no alternatives.

## Consequences

- The web app was added on the same day ([#176](https://github.com/pauk-slon/immer-wiederholen/pull/176)) and could use the same records. It has its own session store for the shown exercise.
- `/reset` deletes the record and doesn't change the chat settings.
- Each new piece of chat state needs a decision about its store. A rule in [Architecture](../architecture.md#processes-and-state) later made this decision simple. It asks whether another frontend would need the state.
