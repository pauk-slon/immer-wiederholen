# immer-wiederholen

Telegram bot for practicing German with multiple choice questions (aiogram, Python). Exercises and topic relations are loaded at startup from the directory set by `COURSE_PATH` env var (default: `data`) — `{COURSE_PATH}/exercises.yaml` and `{COURSE_PATH}/topics.yaml`. Bot commands: `/start`, `/wiederholen` (show a exercise with answer options), `/progress` (today's remaining/new-today/answered-today counts plus a learning/mastered breakdown by word), `/language` (toggle ru/en), `/reminders` (how long after the last session to send a reminder, or turn reminders off — see `docs/bot.md`), `/topics` (choose which topic groups exercises come from, see `docs/bot.md`), `/reset` (wipe the repetition schedule and today's answer stats after an inline confirm/cancel prompt).

The course format (`exercises.yaml`, `topics.yaml`, `bot.yaml`, every exercise field and topic setting) is documented for course authors in `docs/course-format.md` — read it before changing `wiederholen.school.curriculum`'s fields or loading, and update it (plus `demo/`, which `tests/school/test_demo_course.py` checks still uses every field and setting) along with any format change. `demo/` is the default local course (`compose.yaml` sets `COURSE_PATH: ${COURSE_PATH:-demo}`); the real content lives in a separate private repo, bind-mounted to the gitignored `data/` with `COURSE_PATH: data` in `compose.override.yaml`. The code's own default stays `data`, which is what production relies on.

Every environment variable, the processes, and the optional integrations (Anthropic, R2/Workers AI, OpenTelemetry, feature flags) are documented for operators in `docs/configuration.md` — update it along with any new or renamed env var.

## Key modules

The package map, the dependency rules between `wiederholen.school`, `wiederholen.bot`, `wiederholen.web` and `wiederholen.tracing`, the processes, and where each piece of state lives are in `docs/architecture.md` — read it before adding a module or making one package import another. The rules that matter most: `school` never imports a frontend or reads env vars (the cue generator's `__main__` excepted); `tutoring` does no I/O; `bot` and `web` never import each other. Every `wiederholen.bot` handler resolves the `StudentID` it addresses `StudentRecordBook` with via `StudentIdentityStore` (see `docs/storage.md`), never from the chat directly.

## Repetition schedule

Spaced-repetition scheduling — `Tutor`/`StudentRecord`, `SelectablePairs` word/topic selection, repeat-avoidance, the daily new-word cap, chains/gates in `topics.yaml`, and `/progress`'s six numbers — is documented in full in `docs/repetition-schedule.md`. Read it before touching `wiederholen.school.tutoring.session`/`selection`/`student_record` or `wiederholen.school.curriculum.Course`'s chain/gate loading. The rules that matter most:

- The schedule is per `(word, topic)` pair; the daily new-word limit is per *word*.
- A first or wrong answer sets the interval to 0 and makes the pair due again today; don't make it 1.
- `_expedite_dependent()` only creates entries for pairs that have none — never move an existing entry (mutual chains would loop).
- `Tutor` never touches a raw schedule entry: read with `get_repetition_interval()`, write with `schedule_pair()`. `StudentRecord` stays course-agnostic.
- `is_new` and the previous interval come from `record_mark()`'s return value, never a separate lookup after it.

## Persistence and student identity

`StudentRecordBook` (the per-student record `Tutor` works on), aiogram's FSM storage (everything else per Telegram chat), and `StudentIdentityStore` (login → `StudentID`) are documented in `docs/storage.md`, including the test setup against real Redis — read it before touching any store or adding per-chat or per-student state. The invariants that matter most:

- Every handler opens exactly one `async with student_record_book.check_out(student_id) as student_record:` per request and does its replies inside it; `check_out()` saves only if the record changed, in a `finally`, so there's no explicit save anywhere.
- Every bot handler gets its `student_id` from `student_identity_store.resolve_or_create_student_id("telegram", str(chat_id))` (callback handlers: `str(callback.from_user.id)`, the same value in a private chat).
- The student record holds only learning state; chat settings and conversation state stay in FSM data. A new chat-level setting belongs in `_CHAT_SETTINGS_KEYS`.
- `Tutor` never touches a store — it gets a plain `dict`.
- `check_out()` isn't atomic across concurrent updates for the same student: last write wins (#249). Don't rely on two handlers for one student seeing each other's changes.

## Tracing and tutoring events

What's traced (span names and attributes per process, `Tutor`'s span events), how it's wired, and how tests check span content are in `docs/tracing.md` — read it before adding a span, an attribute or a tutoring event. The rules that matter most:

- `TracingMiddleware` is registered on `dispatcher.update` *before* `dispatcher.fsm` (the dispatcher is built with `disable_fsm=True` for this); swapping them makes the FSM's Redis read an orphan root span.
- Never record free text a learner typed — only commands and the bot's own callback-data constants.
- `Tutor` reports events by calling `wiederholen.school.tutoring.events.emit()` with a frozen dataclass at the point they happen; they're not returned to callers. `tutoring` may use the OpenTelemetry *API* only, never the SDK.
- New spans come from `wiederholen.tracing.default_tracer`, named `area.action`, with namespaced attributes (`telegram.*`, `reminder.*`, `client.error.*`); outgoing HTTP calls (Telegram, Anthropic, R2, Workers AI) aren't instrumented.
- `configure_tracing()`/`instrument_redis()` are called only from the three `main()`s, never at import time. Tests must not use the global provider: use the `tracer`/`exporter` fixtures from `tests/plugins/tracing.py`.

## Telegram bot

Commands, how a question is rendered, chat settings (`/topics`, `/reminders`, `/language`, `/ai`), the reminder worker, blocked chats, pending inline buttons, feature flags and grammar-class hints are documented in `docs/bot.md` — read it before touching `wiederholen.bot`. The rules that matter most:

- Every message sent with an inline keyboard is followed by `remember_buttoned_message()`; a callback handler that removes its own buttons and attaches none calls `forget_buttoned_message()`; every typed command calls `clear_stale_buttons()` first. When editing a message's text, pass `reply_markup=` explicitly.
- `_format_question()` sends HTML: every piece of authored text goes through `html.escape()`.
- A new chat-level setting goes into `_CHAT_SETTINGS_KEYS`, or it's lost after every exercise.
- The reminder decision stays in `Tutor.should_remind()` (pure); `record_reminder_sent()` only after Telegram accepted the message.
- Topic selection narrows what's *shown* (`/wiederholen`, next/study-more buttons, reminders), never `/progress` or answer checking.
- `bot_blocked` is set from both `my_chat_member` and a 403 on send; the reminder skips such chats before touching the record.
- Feature flags stay in the bot layer; `wiederholen.school` never sees a chat id or flag name.

## AI-generated content

Shadow exercises (the `/ai` mode, `wiederholen.school.authoring.shadow_exercises`) and cues (illustrations, `wiederholen.school.authoring.cues`, `wiederholen.school.cue_store`, the generator at `python -m wiederholen.school.authoring.cues`) are documented in `docs/authoring.md` — read it before touching either. The rules that matter most:

- A shadow keeps `word`, `topic` and `answer` (and `word_bank`, `grammar_classes`) from the picked exercise; the model generates `question`, `distractors`, `explanation`, `recalls`, and `description` when the original has one. Never let it choose the answer.
- `AIGenerationError` surfaces as an error message, never a silent fallback to the authored exercise. `_apply_ai_mode()` is the single decision point; per-exercise eligibility is `ai_mode and exercise.topic in course.ai_generatable_topics`.
- `Exercise.cue_key` (SHA-256 of `question`) is the only place a cue's key is derived. Cue lookups in the bot are best-effort: any exception falls back to a text question.
- `authoring` depends only on `curriculum`; `tutoring` never imports it. The cue generator's `__main__` is the one module under `school` allowed to read env vars.

## Web frontend

`wiederholen.web` (Litestar) — the embeddable widget, the standalone app, session storage, Telegram login, and `widget.js`'s deck/card UI — is documented in full in `docs/web-frontend.md`. Read it before touching anything under `wiederholen/web/`. The rules that matter most:

- Responses never carry an exercise's or recall's answer; `/check` and `/recall/check` look it up in `WebSessionStore`.
- `WebSessionStore` is keyed by student *and* topics, so every endpoint sends `topics`, even those that don't restrict the course with it.
- `check_answer()` isn't idempotent: when the widget adds a card, the previous card's controls are removed, never just disabled visually.
- A failed answer isn't retried with the same request (a 409 from an expired session would repeat); recovery is loading a new exercise.
- Embed and app are one component that differs only by attributes; don't fork it.

## Telegram login

How the web app's "Log in with Telegram" works — the signature check, the shared cookie (`browser:<token>` vs an anonymous `web:` id), `return_to` and `_safe_redirect_target()`, the widget's `login`/`telegram-bot` attributes — is in the "Telegram login" section of `docs/web-frontend.md`. The rules that matter most:

- The cookie never holds a `StudentID`: a logged-in browser holds a `"browser"` login token resolved through `StudentIdentityStore.resolve_student_id()`; a miss falls back to a fresh anonymous id, never to creating a learner.
- Every login mints a new token and `link_identity()`s it; never reuse the token the request already carries.
- `return_to` isn't signed by Telegram: pop it before `validate_telegram_login()`, and only follow it through `_safe_redirect_target()`.

All commands run inside the Docker container — `docker compose run --rm bot <command>` (`pytest`, `ruff format .`, `ruff check . --fix`, `ty check .`, `uv add <package>`). Testing and pull request conventions are in `CONTRIBUTING.md`.
