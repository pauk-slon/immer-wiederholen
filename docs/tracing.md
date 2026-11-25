# Observability

The bot, the reminder and the web app record OpenTelemetry traces. This page describes what they record, what they don't record, and how to add more. The project has no metrics. Logs go to the container's output through Python's `logging`.

Tracing is off until you set an OTLP endpoint. [Configuration](configuration.md#tracing) describes how to enable it.

## What gets traced

Each unit of work has one root span. Redis calls inside it become child spans, and `Tutor` events become span events.

| Span | Process | Attributes |
|---|---|---|
| `telegram.message` | bot | `telegram.chat_id`, `telegram.handled`, `telegram.language`, and `telegram.command` (the first word, such as `/wiederholen`) if the text starts with `/`. For `/start`, also `telegram.start.new_chat`. If a link set up a new chat, also `telegram.start.language`, and `telegram.start.topic_groups` if the link selected groups (see below). `lesson_recall.finished` after the last translation of a lesson recall. `lesson_recall.too_long` for a translation over the length limit (see [Lesson recall](bot.md#the-states)). `lesson_recall.limit_reached` after the last answer of a lesson that gets no lesson recall because of the daily limit. `lesson_recall.offered` when the bot offers the practice at the end of a lesson. `telegram.fallback` if no other handler took the message (see [Other messages](bot.md#other-messages)) |
| `telegram.callback_query` | bot | `telegram.callback_data`, `telegram.handled`, and `telegram.chat_id` and `telegram.language` unless the button belongs to an old message that Telegram no longer returns. `lesson_recall.skipped` for "Skip" in a lesson recall, and `lesson_recall.finished` if it skipped the last sentence |
| `telegram.my_chat_member` | bot | `telegram.chat_id`, `telegram.handled`, `telegram.language`, `telegram.chat_member.status` (`kicked` when the learner blocks the bot, `member` when they unblock it) |
| `telegram.update` | bot | `telegram.handled` only (any other kind of update) |
| `lesson_recall.generate` | bot (child of `telegram.callback_query`) | `lesson_recall.exercises`, `lesson_recall.wrong_exercises`, `lesson_recall.topics` (the topic of each exercise of the lesson), and `lesson_recall.sentences` with `lesson_recall.left_out_topics` (the topics of the exercises that no sentence uses) or `lesson_recall.failure`. Also the tokens of the model call (see below) |
| `lesson_recall.check` | bot (child of `telegram.message`, or of `telegram.callback_query` for "Check again") | `lesson_recall.topics` (the topics of the exercises that the sentence uses), and `lesson_recall.verdict` (`correct` or `wrong`) or `lesson_recall.failure`. For a wrong translation, `lesson_recall.corrected` is `true` if the bot showed the correction and `false` if it showed the reference. Also the tokens of the model call |
| `reminder.tick` | reminder | none (one sweep over all chats) |
| `reminder.check_chat` | reminder (child of `reminder.tick`) | `telegram.chat_id`, `reminder.sent` (the reminder went out), `reminder.bot_blocked` (the learner had blocked the bot, or Telegram refused the message for that reason) |
| an HTTP server span per request | web | the standard HTTP attributes from Litestar's OpenTelemetry plugin, and `client.error.step` and `client.error.status` for `POST /api/client-error` |
| a span per Redis command | all three | from `opentelemetry-instrumentation-redis` |

The web widget reports its own failures to `POST /api/client-error`. It sends the step that failed and the HTTP status, if there was a response, so you can query browser-side errors next to the server's traces.

The traces never contain text that a learner typed. A message span records only the command. Callback data is always a value that the bot made itself. It is a button id, sometimes with a topic group id or a reminder interval after it (`__topic_group__:verbs`, `__remind_after__:8`). The traces can contain text from the course. `ExerciseSelected` records the question text.

When code inside a span raises an exception, OpenTelemetry records it on that span. In the reminder, an error in one chat is recorded on that chat's `reminder.check_chat` span. The sweep then logs the error and continues with the next chat.

`telegram.start.topic_groups` has only group ids that the course has. The bot never records the payload itself, because a learner can type any text after `/start`. With `telegram.start.new_chat`, `telegram.start.topic_groups` shows how many new chats came from a page with groups. `telegram.start.language` is the language from the link. A link can carry a language without groups, so this attribute shows every new chat that came from a link, with or without groups.

`telegram.language` is the chat's language, `ru` or `en`. A chat that never stored a language gets the default. It lets you compare the learners of the two languages, for example in lesson recalls. `TracingMiddleware` reads it from the FSM data after the handler, so after `/language` the span has the new language. This is one more Redis read for each update. A failed read doesn't fail the update, because the handler has already replied. The span then has no language.

The two `lesson_recall.*` spans never contain a sentence, a translation or an explanation. `lesson_recall.failure` is the message of `AIGenerationError`, a fixed text from the code.

The model call adds `lesson_recall.input_tokens`, `lesson_recall.output_tokens`, `lesson_recall.cache_read_input_tokens` and `lesson_recall.cache_creation_input_tokens` to the current span. So the span shows what a lesson recall costs and whether the prompt cache works. A call that fails before a reply has no token counts.

`lesson_recall.finished` and `lesson_recall.generate` show how many learners stay to the end of a lesson recall. Divide the number of updates with `lesson_recall.finished` by the number of `lesson_recall.generate` spans without `lesson_recall.failure`.

`lesson_recall.offered` and `lesson_recall.generate` show how many learners choose the practice ([ADR 0036](adr/0036-practice-after-a-lesson-is-a-choice.md)). Divide the number of `lesson_recall.generate` spans by the number of updates with `lesson_recall.offered`. A learner can see the offer more than once in one lesson, on the result of each try of a recall at the end of the lesson, so the ratio is a lower bound.

`lesson_recall.limit_reached` shows how often learners reach the daily limit. If many learners reach it, the limit is too low for them.

`lesson_recall.too_long` shows how often learners write more than the length limit allows. If it happens often, the limit is too low or the sentences are too long.

`lesson_recall.left_out_topics` and `lesson_recall.topics` show which topics the model leaves out of a lesson recall. For a topic, divide the number of `lesson_recall.generate` spans with it in `lesson_recall.left_out_topics` by the number with it in `lesson_recall.topics`. If the guide's rules for a topic are too hard to follow, this ratio is high.

`lesson_recall.topics` and `lesson_recall.verdict` on `lesson_recall.check` show the wrong translations by topic. If a topic gets many more wrong verdicts than the others, the guide may be too strict for it or the task may not show its form.

`lesson_recall.corrected` shows how often a wrong translation gets the reference instead of a correction. If this happens often, the guide's rule for the correction doesn't work well.

`telegram.handled` is `false` when no handler matched the update. For a button press, this means that the learner got no reply. A message from the learner always has a handler, because the fallback takes it if no other handler does. Service messages and some other kinds, such as a location, still get `false`. Some updates need no reply, but they also get `false`. An edited message is one example. It gets a `telegram.message` span too, so the span name doesn't separate the two cases. A handler that raises an exception leaves the attribute unset.

`telegram.fallback` marks the messages that only the fallback took (see [Other messages](bot.md#other-messages)). It shows how often learners write to the bot outside an exercise, and with the following spans of the chat, what they do next.

### Events from the repetition engine

`Tutor`, the repetition engine, adds span events to the current span. In the bot this is the update's span. In the web app it is the request's span.

| Event | When | Attributes |
|---|---|---|
| `ExerciseSelected` | `next_exercise()` takes an exercise from the lesson | `word`, `topic`, `question` (the question text from the course), `is_new` (the learner never answered this pair) |
| `ExerciseAnswered` | every `check_answer()` | `word`, `topic`, `is_correct`, `is_new`, `recall_mode` (`none`, `optional`, `required`), `prev_repetition_interval` (not set on a pair's first answer), `next_repetition_interval` |
| `TopicUnlocked` | `Tutor` schedules a linked topic for a word (see [Course format](course-format.md#linking-topics)) | `source_topic`, `dependent_topic`, `via` (`chain` or `gate`) |
| `NoExerciseAvailable` | `next_exercise()` finds nothing to show | `reason` (`daily_cap_reached` when only new words are left and today's limit is used up, otherwise `nothing_available`) |
| `StreakExtended` | a finished lesson adds a day to the streak or starts a new one (see [Repetition schedule](repetition-schedule.md#streak)) | `days`, the new length. It is 1 for a new streak |
| `StreakBroken` | the first finished lesson after a break of more than 36 hours | `days`, the length of the lost streak |
| `LessonStarted` | `next_exercise()` starts a new lesson (see [Repetition schedule](repetition-schedule.md#lessons)) | `size`, the number of exercises in the lesson |
| `LessonFinished` | the answer to the last exercise of a lesson | `size`, the number of exercises in the lesson, and `correct`, the number of correct answers in it. `size` is smaller than in `LessonStarted` if the lesson skipped exercises that the course no longer has |
| `RecallRequested` | `request_recall()` picks a recall, also after "Try again" (see [Course format](course-format.md#recalls)) | `word`, `topic`, `question` (the text of the recall), `recall_mode` (the mode of the answer's `ExerciseAnswered`), `attempt` (1 for the first recall after an answer, 2 or more after "Try again"). `recall_mode` and `attempt` are not set if the learner answered another exercise in the other frontend after the recall (see [Repetition schedule](repetition-schedule.md#recalls)) |
| `RecallAnswered` | every `check_recall()` | `word`, `topic`, `question`, `is_correct`, `recall_mode`, `attempt`. `recall_mode` and `attempt` are not set in the same case |

`ExerciseSelected` records the exercise that `Tutor` took from the lesson. To find where a learner stopped, look for their last `ExerciseSelected` without an `ExerciseAnswered` after it.



The recall events give two measures:

- **How often learners tap "Drill" after a right answer.** Divide the number of `RecallRequested` events where `recall_mode` is `optional` and `attempt` is 1 by the number of `ExerciseAnswered` events where `recall_mode` is `optional`.
- **The share of right recall answers at the first attempt.** Take the `RecallAnswered` events where `attempt` is 1, and find the share of them where `is_correct` is true.

### What isn't traced

- **Outgoing HTTP calls.** The instrumentation covers only Redis and incoming web requests. Calls to the Telegram Bot API, Anthropic, R2 and Workers AI have no spans of their own. The time spent in them appears as a gap inside the parent span. Only the lesson recall's calls to Anthropic are inside a span of their own, `lesson_recall.generate` or `lesson_recall.check`.
- **The cue generator.** It doesn't call `configure_tracing()`.
- **Bot startup.** The bot sets its commands and profile before polling starts, outside any span.

## How tracing is set up

[`wiederholen.tracing`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/tracing.py) holds the setup that all three processes share:

- **`configure_tracing()`** installs a `TracerProvider` that exports over OTLP/HTTP. If neither `OTEL_EXPORTER_OTLP_ENDPOINT` nor `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` is set, it does nothing. The code adds only `service.version`, from the `APP_VERSION` variable that the published image sets. The service name and the other attributes come from `OTEL_SERVICE_NAME` and `OTEL_RESOURCE_ATTRIBUTES`.
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

[`wiederholen.school.tutoring.events`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/school/tutoring/events.py) defines the events as frozen dataclasses. `emit(event)` adds an event to `trace.get_current_span()` and names it after the dataclass. First, `_to_otel_attributes()` converts the dataclass fields to span attributes. It replaces enum values with their `.value` and omits `None` fields, because neither is a valid attribute value.

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
