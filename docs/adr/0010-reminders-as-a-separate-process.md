# 0010. Reminders run as a separate process

**Status:** Accepted, 2026-07-19 ([#62](https://github.com/pauk-slon/immer-wiederholen/pull/62)); reason written down in [#63](https://github.com/pauk-slon/immer-wiederholen/pull/63)

## Context

The bot sends a reminder to learners who have gone quiet while something is due. That needs a loop running on a timer, independent of incoming updates.

## Decision

Reminders run in their own process, `python -m wiederholen.bot.reminder`, as a separate service, rather than as an `asyncio` task inside the polling bot.

## Alternatives considered

- **A background task in the bot.** One process fewer. Rejected because the bot's tests call `main()` repeatedly, and each call would leave an uncancelled background task running ([#63](https://github.com/pauk-slon/immer-wiederholen/pull/63)).

## Consequences

- The bot's startup and tests stay free of timers.
- One more service to run and configure; it needs the same storage variables as the bot.
- The reminder has no incoming updates, so it builds its own FSM context and opens its own spans (see [Telegram bot](../bot.md#reminders), [Tracing](../tracing.md)).
