# Observability

The bot, the reminder and the web app are observed through OpenTelemetry traces. This page describes what they record, what they don't, and how to add more. There are no metrics. Warnings and errors are logged with Python's `logging` and end up in the container's output.

Tracing is off unless an OTLP endpoint is set. How to turn it on is covered in [Configuration](configuration.md#tracing).

## What gets traced

Every unit of work gets one root span. Everything it does, such as Redis calls and events from the repetition engine, hangs under it.

| Span | Process | Attributes |
|---|---|---|
| `telegram.message` | bot | `telegram.chat_id`. If the text starts with `/`, also `telegram.command`, the first word, such as `/wiederholen` |
| `telegram.callback_query` | bot | `telegram.callback_data`. Also `telegram.chat_id`, unless the button belongs to an old message Telegram no longer returns |
| `telegram.my_chat_member` | bot | `telegram.chat_id`, `telegram.chat_member.status` (`kicked` when the learner blocks the bot, `member` when they unblock it) |
| `telegram.update` | bot | none. Used for any other kind of update |
| `reminder.tick` | reminder | none. One sweep over all chats |
| `reminder.check_chat` | reminder | `telegram.chat_id`, `reminder.sent` (the reminder went out), `reminder.bot_blocked` (the chat was skipped because the learner had blocked the bot, or Telegram refused the message for that reason). Nested in `reminder.tick` |
| an HTTP server span per request | web | the usual HTTP attributes, from Litestar's OpenTelemetry plugin. For `POST /api/client-error`, also `client.error.step` and `client.error.status` |
| a span per Redis command | all three | from `opentelemetry-instrumentation-redis` |

The web widget reports its own failures to `POST /api/client-error`. It sends the step that failed and the HTTP status, if there was one. This way browser-side errors can be queried next to the server's traces.

Text typed by learners is never recorded. A message span carries only the command. Callback data is always a value the bot generated itself. It is a button id, sometimes with a topic group id or a reminder interval appended (`__topic_group__:verbs`, `__remind_after__:8`).

An exception raised inside a span is recorded on it automatically. In the reminder, a failing chat is recorded on its `reminder.check_chat` span. Then the sweep catches the error, logs it and moves on to the next chat.

### Events from the repetition engine

`Tutor` adds span events to the current span. In the bot that is the update's span, and in the web app it is the request's span.

| Event | When | Attributes |
|---|---|---|
| `ExerciseAnswered` | every `check_answer()` | `word`, `topic`, `is_correct`, `is_new`, `recall_mode` (`none`, `optional`, `required`), `prev_repetition_interval` (absent on a pair's first answer), `next_repetition_interval` |
| `TopicUnlocked` | a linked topic is scheduled for a word (see [Course format](course-format.md#linking-topics)) | `source_topic`, `dependent_topic`, `via` (`chain` or `gate`) |
| `NoExerciseAvailable` | `next_exercise()` finds nothing to show | `reason`. It is `daily_cap_reached` when only new words are left and today's limit is used up, and `nothing_available` otherwise |

Recalls produce no events. `request_recall()` and `check_recall()` don't emit anything.

### What isn't traced

- **Outgoing HTTP calls.** Only Redis and incoming web requests are instrumented. Calls to the Telegram Bot API, Anthropic, R2 and Workers AI don't appear as spans. Time spent in them shows up as a gap inside the parent span.
- **The cue generator.** It doesn't call `configure_tracing()`.
- **Bot startup.** The bot sets its commands and profile before polling starts, outside any span.

## How it's wired

[`wiederholen.tracing`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/tracing.py) holds the setup shared by all three processes:

- **`configure_tracing()`** installs a `TracerProvider` that exports over OTLP/HTTP. If neither `OTEL_EXPORTER_OTLP_ENDPOINT` nor `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` is set, it does nothing. The resource gets no attributes from code. The service name and the rest come from `OTEL_SERVICE_NAME` and `OTEL_RESOURCE_ATTRIBUTES`. A hardcoded fallback service name was tried and dropped. It hid a process that was missing its `OTEL_*` variables under another process's name. Without a fallback, such a process shows up as `unknown_service`.
- **`instrument_redis()`** patches the Redis client globally, so every store's commands are traced without changes at the call sites. Calling it again only logs a warning.
- **`default_tracer`** is obtained at import time. Until a provider is installed it produces no-op spans, and it starts recording once `configure_tracing()` installs one.

The `main()` of the bot, the reminder and the web app call `configure_tracing()` and `instrument_redis()`. Nothing calls them at import time, so importing a package, for example in tests, never sets up exporting.

### Root spans per process

**Bot.** [`TracingMiddleware`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/tracing.py) opens a span per update.

> **It must be registered before aiogram's FSM middleware.** In [`wiederholen/bot/__init__.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/__init__.py) the dispatcher is created with `Dispatcher(disable_fsm=True)`, which stops aiogram from registering its FSM middleware itself. The two are then registered by hand on `dispatcher.update`, tracing first and `dispatcher.fsm` second. The FSM middleware reads the chat's state from Redis before the update is routed, and middlewares wrap in registration order. With tracing second, that read would show up as a separate root span instead of part of the update.

**Reminder.** [`reminder.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/reminder.py) opens its spans by hand. It opens `reminder.tick` for each sweep and `reminder.check_chat` for each chat.

**Web.** `create_app()` registers Litestar's `OpenTelemetryPlugin`, which opens a span per request.

Without these, every Redis call would be a root span of its own.

### Repetition engine: emit()

[`wiederholen.school.tutoring.events`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/school/tutoring/events.py) defines the three events as frozen dataclasses. `emit(event)` adds one to `trace.get_current_span()`, named after the dataclass. Before that, `_to_otel_attributes()` turns the dataclass into span attributes. Enum values are replaced by their `.value`, and `None` fields are left out, since neither is a valid attribute value. Events go onto the span rather than being returned, and they are dataclasses rather than dict literals (see [ADR 0002](adr/0002-tutoring-events-on-the-current-span.md)).

This makes `tutoring` depend on the OpenTelemetry API. It depends only on the API, which is a safe no-op without a configured provider, so `Tutor`'s tests don't need any tracing setup.

The events are internal to `tutoring`. Only `RecallMode` is exported, since the bot needs it for its recall flow.

## Adding a span or attribute

- **Get the tracer from `wiederholen.tracing`** and call `default_tracer.start_as_current_span(...)`. Don't create a tracer of your own.
- **Name spans `area.action`**, like `reminder.check_chat`, and put attributes in a namespace, such as `telegram.*`, `reminder.*` or `client.error.*`.
- **Prefer an attribute on the current span** (`trace.get_current_span().set_attribute(...)`) over a new span when you only want to record a fact, as `/api/client-error` does.
- **For something `Tutor` decides, add an event.** Make it a frozen dataclass in `events.py` and emit it with `emit()` where the decision is made.
- **Never record text a learner typed.**
- **Test it** with the `tracer` and `exporter` fixtures (see below), checking the span's attributes or events.

## Testing

- **Nothing is exported from tests.** `tests/plugins/tracing.py::pytest_configure` sets `OTEL_SDK_DISABLED=true` for the whole session. `docker compose run --rm bot pytest` shares the `bot` service's configuration. Without this setting, a test run with real exporter settings would send spans to the real backend.
- **Span content is checked against an in-memory exporter.** The shared `tracer` and `exporter` fixtures build a recording `TracerProvider` with an `InMemorySpanExporter` and re-enable the SDK just for that provider. `tests/bot/test_tracing.py` uses them for `TracingMiddleware`. `tests/school/tutoring/test_tutoring_events.py` uses them for the events. It runs `check_answer()` or `next_exercise()` inside `tracer.start_as_current_span(...)` and reads `span.events`.
- **The global provider is never used in tests.** `trace.set_tracer_provider()` works only once per process, and later calls are silently ignored, so tests construct their providers directly. `configure_tracing()` and `instrument_redis()` themselves are tested in `tests/test_tracing.py`.

## Local setup

To send traces from a local run, put the `OTEL_*` variables in a gitignored `compose.override.yaml` next to `compose.yaml` (see [Contributing](https://github.com/pauk-slon/immer-wiederholen/blob/main/CONTRIBUTING.md)). Compose merges `environment` per service, so each of `bot`, `reminder` and `web` needs its own block, with its own `OTEL_SERVICE_NAME`.

A stray `=` in a key, like `OTEL_RESOURCE_ATTRIBUTES=: ...`, isn't an error in Compose. The `=` silently ends up in the value. For `OTEL_RESOURCE_ATTRIBUTES` that shows up as an `invalid key` warning from OpenTelemetry. `docker compose config` shows what the variables actually resolve to.

## Decisions

- [The repetition engine reports events on the current span](adr/0002-tutoring-events-on-the-current-span.md) (ADR 0002)
