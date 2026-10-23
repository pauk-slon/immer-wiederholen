# Tracing

What the bot, the reminder and the web app record as OpenTelemetry traces, and how it's wired. Turning tracing on is covered in [Configuration](configuration.md#tracing): it's off unless an OTLP endpoint is set.

## What gets traced

Every unit of work gets one root span; everything it does — Redis calls, events from the repetition engine — hangs under it.

| Span | Process | Attributes |
|---|---|---|
| `telegram.message` | bot | `telegram.chat_id`; `telegram.command` if the text is a command |
| `telegram.callback_query` | bot | `telegram.chat_id`, `telegram.callback_data` |
| `telegram.my_chat_member` | bot | `telegram.chat_id`, `telegram.chat_member.status` (`kicked` when the learner blocks the bot, `member` when they unblock it) |
| `telegram.update` | bot | none — any other kind of update |
| `reminder.tick` | reminder | none — one sweep over all chats |
| `reminder.check_chat` | reminder | `telegram.chat_id`, `reminder.sent`, `reminder.bot_blocked`; nested in `reminder.tick` |
| an HTTP server span per request | web | the usual HTTP attributes, from Litestar's OpenTelemetry plugin |
| a span per Redis command | all three | from `opentelemetry-instrumentation-redis` |

The web widget reports its own failures to `POST /api/client-error`: the step that failed and, if there was one, the HTTP status. They become `client.error.step` and `client.error.status` attributes on that report's own request span, so browser-side errors can be queried next to everything else.

Answers typed by learners are never recorded. A message span carries the command only when the text starts with `/`, and callback data is always one of the bot's own fixed button ids.

An exception raised inside a span is recorded on it automatically. In the reminder, a failing chat is recorded on its `reminder.check_chat` span before the sweep catches the error, logs it and moves on to the next chat.

### Events from the repetition engine

`Tutor` adds span events to whatever span is current — the update's span in the bot, the request's span in the web app:

| Event | When | Attributes |
|---|---|---|
| `ExerciseAnswered` | every `check_answer()` | `word`, `topic`, `is_correct`, `is_new`, `recall_mode` (`none`, `optional`, `required`), `prev_repetition_interval` (absent on a pair's first answer), `next_repetition_interval` |
| `TopicUnlocked` | a linked topic is scheduled for a word (see [Course format](course-format.md#linking-topics)) | `source_topic`, `dependent_topic`, `via` (`chain` or `gate`) |
| `NoExerciseAvailable` | `next_exercise()` finds nothing to show | `reason`: `nothing_available`, or `daily_cap_reached` when only new words are left and today's limit is used up |

## How it's wired

[`wiederholen.tracing`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/tracing.py) holds the setup shared by all three processes:

- **`configure_tracing()`** installs a `TracerProvider` exporting over OTLP/HTTP — or does nothing if neither `OTEL_EXPORTER_OTLP_ENDPOINT` nor `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` is set. The resource gets no attributes from code: the service name and the rest come from `OTEL_SERVICE_NAME` and `OTEL_RESOURCE_ATTRIBUTES`.
- **`instrument_redis()`** patches the Redis client globally, so every store's commands are traced without changes at the call sites. Calling it again only logs a warning.
- **`default_tracer`** is obtained at import time. Until a provider is installed it produces no-op spans, and it starts recording once `configure_tracing()` installs one.

The `main()` of the bot, the reminder and the web app call `configure_tracing()` and `instrument_redis()`. Nothing calls them at import time, so importing a package — in tests, say — never sets up exporting.

### Bot: TracingMiddleware

[`TracingMiddleware`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/tracing.py) opens the update's span. Where it's registered matters: in [`wiederholen/bot/__init__.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/__init__.py), on `dispatcher.update`, **before** aiogram's FSM middleware.

aiogram's FSM middleware reads the chat's state from Redis before the update is routed. Middlewares wrap in registration order, so if the tracing middleware came second, that Redis read would show up in the tracing backend as a separate root span instead of part of the update. That's why the dispatcher is created with `Dispatcher(disable_fsm=True)` — which stops aiogram from registering its FSM middleware itself — and the two are registered by hand: tracing first, `dispatcher.fsm` second.

### Reminder and web

The reminder opens its spans by hand in [`reminder.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/reminder.py): `reminder.tick` for each sweep, `reminder.check_chat` for each chat. The web app registers Litestar's `OpenTelemetryPlugin` in `create_app()`. Without these, every Redis call they make would be a root span of its own.

### Repetition engine: emit()

[`wiederholen.school.tutoring.events`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/school/tutoring/events.py) defines the three events as frozen dataclasses, and `emit(event)` adds one to `trace.get_current_span()`, named after the dataclass. Before that, `_to_otel_attributes()` turns the dataclass into span attributes: enum values are replaced by their `.value`, and `None` fields are left out, since neither is a valid attribute value.

This makes `tutoring` depend on the OpenTelemetry API — but only the API, which is a safe no-op without a configured provider. `Tutor`'s tests don't need any tracing setup.

The events are internal to `tutoring`: only `RecallMode` is exported, since the bot needs it for its recall flow.

## Testing

- **Nothing is exported from tests.** `tests/plugins/tracing.py::pytest_configure` sets `OTEL_SDK_DISABLED=true` for the whole session. `docker compose run --rm bot pytest` shares the `bot` service's configuration, so without it, a test run with real exporter settings in `compose.override.yaml` would send spans to the real backend.
- **Span content is checked against an in-memory exporter.** The shared `tracer` and `exporter` fixtures build a recording `TracerProvider` with an `InMemorySpanExporter`, re-enabling the SDK just for that provider. `tests/bot/test_tracing.py` uses them for `TracingMiddleware`, and `tests/school/tutoring/test_tutoring_events.py` for the events, by running `check_answer()` or `next_exercise()` inside `tracer.start_as_current_span(...)` and reading `span.events`.
- **The global provider is never used in tests.** `trace.set_tracer_provider()` works only once per process, and later calls are silently ignored, so tests construct their providers directly. `configure_tracing()` and `instrument_redis()` themselves are tested in `tests/test_tracing.py`.

## Local setup

`compose.override.yaml` is the place for local tracing settings. Compose merges `environment` per service, so each of `bot`, `reminder` and `web` needs its own block, with its own `OTEL_SERVICE_NAME`.

A stray `=` in a key, like `OTEL_RESOURCE_ATTRIBUTES=: ...`, isn't an error in Compose: the `=` silently ends up in the value. For `OTEL_RESOURCE_ATTRIBUTES` that shows up as an `invalid key` warning from OpenTelemetry. `docker compose config` shows what the variables actually resolve to.

## Design notes

- **Events go straight onto the current span.** An earlier design had `check_answer()` and `next_exercise()` return lists of events, which the bot then turned into span events at every call site. Tracing was the only consumer of those lists, so passing them through return values was ceremony; now `Tutor` reports them where they happen.
- **Events are dataclasses, not dict literals.** What counts as an event and what it contains is domain knowledge — e.g. `ExerciseAnswered.is_new` and `next_repetition_interval` mirror values `check_answer()` computes anyway — so each event's shape is declared once, next to the code that fires it.
- **No service name in code.** A hardcoded fallback was tried and dropped: it hid a real misconfiguration, a process without `OTEL_*` variables reporting under another process's name. Without a fallback, such a process shows up as `unknown_service`.
- **No endpoint, no provider.** Without an endpoint, the exporter would default to `localhost:4318` and keep retrying a collector that isn't there, filling the logs.
