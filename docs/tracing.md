# Observability

The bot, the reminder and the web app record OpenTelemetry traces. This page describes what they record, what they don't record, and how to add more. The project has no metrics. Logs go to the container's output through Python's `logging`.

Tracing is off until you set an OTLP endpoint. [Configuration](configuration.md#tracing) describes how to enable it.

## What gets traced

Each unit of work has one root span. Redis calls inside it become child spans, and `Tutor` events become span events.

| Span | Process | Attributes |
|---|---|---|
| `telegram.message` | bot | `telegram.chat_id`, and `telegram.command` (the first word, such as `/wiederholen`) if the text starts with `/` |
| `telegram.callback_query` | bot | `telegram.callback_data`, and `telegram.chat_id` unless the button belongs to an old message that Telegram no longer returns |
| `telegram.my_chat_member` | bot | `telegram.chat_id`, `telegram.chat_member.status` (`kicked` when the learner blocks the bot, `member` when they unblock it) |
| `telegram.update` | bot | none (any other kind of update) |
| `reminder.tick` | reminder | none (one sweep over all chats) |
| `reminder.check_chat` | reminder (child of `reminder.tick`) | `telegram.chat_id`, `reminder.sent` (the reminder went out), `reminder.bot_blocked` (the learner had blocked the bot, or Telegram refused the message for that reason) |
| an HTTP server span per request | web | the standard HTTP attributes from Litestar's OpenTelemetry plugin, and `client.error.step` and `client.error.status` for `POST /api/client-error` |
| a span per Redis command | all three | from `opentelemetry-instrumentation-redis` |

The web widget reports its own failures to `POST /api/client-error`. It sends the step that failed and the HTTP status, if there was a response, so you can query browser-side errors next to the server's traces.

The traces never contain text that a learner typed. A message span records only the command. Callback data is always a value that the bot made itself. It is a button id, sometimes with a topic group id or a reminder interval after it (`__topic_group__:verbs`, `__remind_after__:8`).

When code inside a span raises an exception, OpenTelemetry records it on that span. In the reminder, an error in one chat is recorded on that chat's `reminder.check_chat` span. The sweep then logs the error and continues with the next chat.

### Events from the repetition engine

`Tutor`, the repetition engine, adds span events to the current span. In the bot this is the update's span. In the web app it is the request's span.

| Event | When | Attributes |
|---|---|---|
| `ExerciseAnswered` | every `check_answer()` | `word`, `topic`, `is_correct`, `is_new`, `recall_mode` (`none`, `optional`, `required`), `prev_repetition_interval` (not set on a pair's first answer), `next_repetition_interval` |
| `TopicUnlocked` | `Tutor` schedules a linked topic for a word (see [Course format](course-format.md#linking-topics)) | `source_topic`, `dependent_topic`, `via` (`chain` or `gate`) |
| `NoExerciseAvailable` | `next_exercise()` finds nothing to show | `reason` (`daily_cap_reached` when only new words are left and today's limit is used up, otherwise `nothing_available`) |

`request_recall()` and `check_recall()` emit no events.

### What isn't traced

- **Outgoing HTTP calls.** The instrumentation covers only Redis and incoming web requests. Calls to the Telegram Bot API, Anthropic, R2 and Workers AI have no spans. The time spent in them appears as a gap inside the parent span.
- **The cue generator.** It doesn't call `configure_tracing()`.
- **Bot startup.** The bot sets its commands and profile before polling starts, outside any span.

## How tracing is set up

[`wiederholen.tracing`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/tracing.py) holds the setup that all three processes share:

- **`configure_tracing()`** installs a `TracerProvider` that exports over OTLP/HTTP. If neither `OTEL_EXPORTER_OTLP_ENDPOINT` nor `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` is set, it does nothing. The code adds no resource attributes. The service name and the other attributes come from `OTEL_SERVICE_NAME` and `OTEL_RESOURCE_ATTRIBUTES`.
- **`instrument_redis()`** patches the Redis client globally, so every store's commands are traced without changes at the call sites. A second call only logs a warning.
- **`default_tracer`** is created at import time. Until a provider is installed, it makes no-op spans. After `configure_tracing()` installs a provider, it records spans.

The `main()` functions of the bot, the reminder and the web app call `configure_tracing()` and `instrument_redis()`. Nothing calls them at import time, so an import, for example in tests, never configures export.

An earlier version had a fallback service name in the code. It was removed because a process without its `OTEL_*` variables then appeared under another process's name. Without a fallback, such a process appears as `unknown_service`, which is easy to notice.

### Root spans per process

Each process opens its own root spans:

- **Bot.** [`TracingMiddleware`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/tracing.py) opens a span per update.
- **Reminder.** [`reminder.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/reminder.py) opens its spans directly. It opens `reminder.tick` for each sweep and `reminder.check_chat` for each chat.
- **Web.** `create_app()` registers Litestar's `OpenTelemetryPlugin`, which opens a span per request.

Without these root spans, every Redis call would be a root span of its own.

> **Register `TracingMiddleware` before aiogram's FSM middleware.** The FSM middleware reads the chat's state from Redis before aiogram routes the update. Middlewares wrap each other in registration order. If tracing comes second, that Redis read appears as a separate root span instead of part of the update's span. For this reason, [`wiederholen/bot/__init__.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/__init__.py) creates the dispatcher with `Dispatcher(disable_fsm=True)`. This stops aiogram from registering its FSM middleware itself. The code then registers both middlewares on `dispatcher.update`, tracing first and `dispatcher.fsm` second.

### How `Tutor` emits events

[`wiederholen.school.tutoring.events`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/school/tutoring/events.py) defines the three events as frozen dataclasses. `emit(event)` adds an event to `trace.get_current_span()` and names it after the dataclass. First, `_to_otel_attributes()` converts the dataclass fields to span attributes. It replaces enum values with their `.value` and omits `None` fields, because neither is a valid attribute value.

`Tutor` adds events to the span instead of returning them, and the events are dataclasses instead of dict literals. [ADR 0002](adr/0002-tutoring-events-on-the-current-span.md) explains both choices.

Because of `emit()`, `tutoring` depends on the OpenTelemetry API, but not on the SDK. Without a configured provider, the API does nothing, so `Tutor`'s tests need no tracing setup.

The events are internal to `tutoring`. The package exports only `RecallMode`, because the bot needs it for its recall flow.

## Adding a span or attribute

- **Get the tracer from `wiederholen.tracing`** and call `default_tracer.start_as_current_span(...)`. Don't create a tracer of your own. With one tracer, all the project's spans have the same instrumentation scope.
- **Name spans `area.action`**, like `reminder.check_chat`. Put attributes in a namespace, such as `telegram.*`, `reminder.*` or `client.error.*`.
- **Prefer an attribute on the current span** (`trace.get_current_span().set_attribute(...)`) to a new span when you only record a fact. `/api/client-error` does this.
- **For a decision that `Tutor` makes, add an event.** Make it a frozen dataclass in `events.py`. Emit it with `emit()` at the point where `Tutor` makes the decision.
- **Never record text that a learner typed.**
- **Test it** with the `tracer` and `exporter` fixtures (see [Testing](#testing)). Check the span's attributes or events.

## Testing

- **Tests export nothing.** `tests/plugins/tracing.py::pytest_configure` sets `OTEL_SDK_DISABLED=true` for the whole session. Tests run in the `bot` service (`docker compose run --rm bot pytest`) and get its environment. Without this setting, a test run would send spans to any OTLP endpoint in that environment.
- **Tests check span content with an in-memory exporter.** The shared `tracer` and `exporter` fixtures build a recording `TracerProvider` with an `InMemorySpanExporter`. They enable the SDK again for that provider only. `tests/bot/test_tracing.py` uses them for `TracingMiddleware`. `tests/school/tutoring/test_tutoring_events.py` uses them for the events. It runs `check_answer()` or `next_exercise()` inside `tracer.start_as_current_span(...)` and reads `span.events`.
- **Tests never use the global provider.** `trace.set_tracer_provider()` works only once per process and silently ignores later calls, so tests create their providers directly. `tests/test_tracing.py` tests `configure_tracing()` and `instrument_redis()` themselves.

## Local setup

To send traces from a local run, put the `OTEL_*` variables in a gitignored `compose.override.yaml` next to `compose.yaml` (see [Contributing](https://github.com/pauk-slon/immer-wiederholen/blob/main/CONTRIBUTING.md#setup)). Compose merges `environment` per service, so each of `bot`, `reminder` and `web` needs its own block with its own `OTEL_SERVICE_NAME`.

Compose accepts a stray `=` in a key, like `OTEL_RESOURCE_ATTRIBUTES=: ...`, without an error. The `=` silently becomes part of the value. For `OTEL_RESOURCE_ATTRIBUTES`, OpenTelemetry then logs an `invalid key` warning. `docker compose config` shows the values that the variables actually get.

## Decisions

- [The repetition engine reports events on the current span](adr/0002-tutoring-events-on-the-current-span.md) (ADR 0002)
