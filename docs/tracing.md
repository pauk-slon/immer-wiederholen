# Tracing

What the bot, the reminder and the web app record as OpenTelemetry traces, what they don't, and how to add more. Turning tracing on is covered in [Configuration](configuration.md#tracing): it's off unless an OTLP endpoint is set.

## What gets traced

Every unit of work gets one root span; everything it does — Redis calls, events from the repetition engine — hangs under it.

| Span | Process | Attributes |
|---|---|---|
| `telegram.message` | bot | `telegram.chat_id`; `telegram.command` — the first word, e.g. `/wiederholen` — if the text starts with `/` |
| `telegram.callback_query` | bot | `telegram.callback_data`; `telegram.chat_id`, unless the button belongs to an old message Telegram no longer returns |
| `telegram.my_chat_member` | bot | `telegram.chat_id`, `telegram.chat_member.status` (`kicked` when the learner blocks the bot, `member` when they unblock it) |
| `telegram.update` | bot | none — any other kind of update |
| `reminder.tick` | reminder | none — one sweep over all chats |
| `reminder.check_chat` | reminder | `telegram.chat_id`; `reminder.sent` — the reminder went out; `reminder.bot_blocked` — the chat was skipped because the learner had blocked the bot, or Telegram refused the message for that reason. Nested in `reminder.tick` |
| an HTTP server span per request | web | the usual HTTP attributes, from Litestar's OpenTelemetry plugin; for `POST /api/client-error`, also `client.error.step` and `client.error.status` |
| a span per Redis command | all three | from `opentelemetry-instrumentation-redis` |

The web widget reports its own failures to `POST /api/client-error` — the step that failed and, if there was one, the HTTP status — so browser-side errors can be queried next to everything else.

Text typed by learners is never recorded. A message span carries only the command, and callback data is always a value the bot generated itself: a button id, sometimes with a topic group id or a reminder interval appended (`__topic_group__:verbs`, `__remind_after__:8`).

An exception raised inside a span is recorded on it automatically. In the reminder, a failing chat is recorded on its `reminder.check_chat` span before the sweep catches the error, logs it and moves on to the next chat.

### Events from the repetition engine

`Tutor` adds span events to whatever span is current — the update's span in the bot, the request's span in the web app:

| Event | When | Attributes |
|---|---|---|
| `ExerciseAnswered` | every `check_answer()` | `word`, `topic`, `is_correct`, `is_new`, `recall_mode` (`none`, `optional`, `required`), `prev_repetition_interval` (absent on a pair's first answer), `next_repetition_interval` |
| `TopicUnlocked` | a linked topic is scheduled for a word (see [Course format](course-format.md#linking-topics)) | `source_topic`, `dependent_topic`, `via` (`chain` or `gate`) |
| `NoExerciseAvailable` | `next_exercise()` finds nothing to show | `reason`: `nothing_available`, or `daily_cap_reached` when only new words are left and today's limit is used up |

Recalls produce no events: `request_recall()` and `check_recall()` don't emit anything.

### What isn't traced

- **Outgoing HTTP calls.** Only Redis and incoming web requests are instrumented. Calls to the Telegram Bot API, Anthropic, R2 and Workers AI don't appear as spans; time spent in them shows up as a gap inside the parent span.
- **The cue generator.** It doesn't call `configure_tracing()`.
- **Bot startup.** Setting the bot's commands and profile happens before polling starts, outside any span.

## How it's wired

[`wiederholen.tracing`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/tracing.py) holds the setup shared by all three processes:

- **`configure_tracing()`** installs a `TracerProvider` exporting over OTLP/HTTP — or does nothing if neither `OTEL_EXPORTER_OTLP_ENDPOINT` nor `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` is set. The resource gets no attributes from code: the service name and the rest come from `OTEL_SERVICE_NAME` and `OTEL_RESOURCE_ATTRIBUTES`. A hardcoded fallback service name was tried and dropped: it hid a process missing its `OTEL_*` variables under another process's name, while without one it shows up as `unknown_service`.
- **`instrument_redis()`** patches the Redis client globally, so every store's commands are traced without changes at the call sites. Calling it again only logs a warning.
- **`default_tracer`** is obtained at import time. Until a provider is installed it produces no-op spans, and it starts recording once `configure_tracing()` installs one.

The `main()` of the bot, the reminder and the web app call `configure_tracing()` and `instrument_redis()`. Nothing calls them at import time, so importing a package — in tests, say — never sets up exporting.

### Root spans per process

**Bot.** [`TracingMiddleware`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/tracing.py) opens a span per update.

> **It must be registered before aiogram's FSM middleware.** In [`wiederholen/bot/__init__.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/__init__.py) the dispatcher is created with `Dispatcher(disable_fsm=True)`, which stops aiogram from registering its FSM middleware itself, and the two are registered by hand on `dispatcher.update`: tracing first, `dispatcher.fsm` second. The FSM middleware reads the chat's state from Redis before the update is routed, and middlewares wrap in registration order — with tracing second, that read would show up as a separate root span instead of part of the update.

**Reminder.** [`reminder.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/reminder.py) opens its spans by hand: `reminder.tick` for each sweep, `reminder.check_chat` for each chat.

**Web.** `create_app()` registers Litestar's `OpenTelemetryPlugin`, which opens a span per request.

Without these, every Redis call would be a root span of its own.

### Repetition engine: emit()

[`wiederholen.school.tutoring.events`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/school/tutoring/events.py) defines the three events as frozen dataclasses, and `emit(event)` adds one to `trace.get_current_span()`, named after the dataclass. Before that, `_to_otel_attributes()` turns the dataclass into span attributes: enum values are replaced by their `.value`, and `None` fields are left out, since neither is a valid attribute value. Events go onto the span rather than being returned, and are dataclasses rather than dict literals (see [ADR 0002](adr/0002-tutoring-events-on-the-current-span.md)).

This makes `tutoring` depend on the OpenTelemetry API — but only the API, which is a safe no-op without a configured provider. `Tutor`'s tests don't need any tracing setup.

The events are internal to `tutoring`: only `RecallMode` is exported, since the bot needs it for its recall flow.

## Adding a span or attribute

- **Get the tracer from `wiederholen.tracing`**: `default_tracer.start_as_current_span(...)`. Don't create a tracer of your own.
- **Name spans `area.action`**, like `reminder.check_chat`, and put attributes in a namespace: `telegram.*`, `reminder.*`, `client.error.*`.
- **Prefer an attribute on the current span** (`trace.get_current_span().set_attribute(...)`) over a new span when you only want to record a fact, as `/api/client-error` does.
- **For something `Tutor` decides, add an event**: a frozen dataclass in `events.py`, emitted with `emit()` where the decision is made.
- **Never record text a learner typed.**
- **Test it** with the `tracer` and `exporter` fixtures (see below), checking the span's attributes or events.

## Testing

- **Nothing is exported from tests.** `tests/plugins/tracing.py::pytest_configure` sets `OTEL_SDK_DISABLED=true` for the whole session. `docker compose run --rm bot pytest` shares the `bot` service's configuration, so without it, a test run with real exporter settings would send spans to the real backend.
- **Span content is checked against an in-memory exporter.** The shared `tracer` and `exporter` fixtures build a recording `TracerProvider` with an `InMemorySpanExporter`, re-enabling the SDK just for that provider. `tests/bot/test_tracing.py` uses them for `TracingMiddleware`, and `tests/school/tutoring/test_tutoring_events.py` for the events, by running `check_answer()` or `next_exercise()` inside `tracer.start_as_current_span(...)` and reading `span.events`.
- **The global provider is never used in tests.** `trace.set_tracer_provider()` works only once per process, and later calls are silently ignored, so tests construct their providers directly. `configure_tracing()` and `instrument_redis()` themselves are tested in `tests/test_tracing.py`.

## Local setup

To send traces from a local run, put the `OTEL_*` variables in a gitignored `compose.override.yaml` next to `compose.yaml` (see [Contributing](https://github.com/pauk-slon/immer-wiederholen/blob/main/CONTRIBUTING.md)). Compose merges `environment` per service, so each of `bot`, `reminder` and `web` needs its own block, with its own `OTEL_SERVICE_NAME`.

A stray `=` in a key, like `OTEL_RESOURCE_ATTRIBUTES=: ...`, isn't an error in Compose: the `=` silently ends up in the value. For `OTEL_RESOURCE_ATTRIBUTES` that shows up as an `invalid key` warning from OpenTelemetry. `docker compose config` shows what the variables actually resolve to.

## Decisions

- [ADR 0002](adr/0002-tutoring-events-on-the-current-span.md): the repetition engine reports events on the current span.
