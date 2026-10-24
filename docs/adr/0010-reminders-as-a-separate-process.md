# 0010. Reminders run as a separate process

**Status:** Accepted, 2026-07-19 ([#62](https://github.com/pauk-slon/immer-wiederholen/pull/62)). The reason is written down in [#63](https://github.com/pauk-slon/immer-wiederholen/pull/63).

## Context

The bot sends a reminder to learners who stopped answering while something is due. This needs a loop that runs on a timer, independent of incoming updates.

## Decision

Reminders run in their own process, `python -m wiederholen.bot.reminder`, as a separate service. They don't run as an `asyncio` task inside the polling bot.

## Alternatives considered

- **A background task in the bot.** This needs one process fewer. It was rejected, because the bot's tests call `main()` many times, and each call would leave a background task running that nobody cancels ([#63](https://github.com/pauk-slon/immer-wiederholen/pull/63)).

## Consequences

- The bot's startup and tests have no timers.
- There is one more service to run and configure. It needs the same storage variables as the bot.
- The reminder has no incoming updates, so it builds its own FSM context and opens its own spans (see [Telegram bot](../bot.md#reminders), [Observability](../tracing.md)).
