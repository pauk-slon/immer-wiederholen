# Storage and identity

Where per-learner state is kept, how handlers read and write it, and how a login is resolved to a learner. The overview of all stores is in [Architecture](architecture.md#processes-and-state); their environment variables are in [Configuration](configuration.md#redis).

In code, a learner is a *student*: `StudentID`, `StudentRecord`, `StudentRecordBook`.

## Student records

A **student record** is the learner's repetition schedule and progress: a plain JSON-compatible `dict` that `Tutor` reads and changes (see [Repetition schedule](repetition-schedule.md)). It's the one piece of per-learner state every frontend shares, so a learner who practices in Telegram and then logs in on the web continues where they left off.

[`StudentRecordBook`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/school/student_record_book.py) stores records by `StudentID`. It has two public members:

- **`check_out(student_id)`**, an async context manager that loads the record, hands it out for changing in place, and saves it when the block ends.
- **Iteration** — `async for student_id in student_record_book` yields the id of every learner with a stored record. Like iterating a `dict`, it yields keys only; read a record with `check_out()`.

Every handler that touches a record opens exactly one `check_out()` per request and does its work — including sending replies — inside the block:

```python
student_id = await student_identity_store.resolve_or_create_student_id(
    "telegram", str(message.chat.id)
)
async with student_record_book.check_out(student_id) as student_record:
    tutor = Tutor(course, student_record)
    mark = tutor.check_answer(exercise, message.text)
    await message.answer(...)
```

### Saved only when changed

`check_out()` takes a deep copy of the record right after loading it and, when the block ends, saves only if the record differs from that copy. This one rule covers every caller:

- a handler that always changes the record (recording an answer) always saves;
- a handler that only reads (`/progress`) never writes;
- a handler that changes it on one branch only (the reminder, which records a reminder only after it was sent) saves only then.

The comparison runs in a `finally` block, so a change made before an error — `check_answer()` succeeded, then sending the reply failed — is still saved rather than lost.

### Redis implementation

`RedisStudentRecordBook` keeps one JSON value per learner under `student_record:{student_id}`. An empty record is stored as no key at all, so a learner with nothing recorded doesn't show up when iterating.

Closing the connection is specific to this implementation, not part of `StudentRecordBook`: `RedisStudentRecordBook` is an async context manager (`async with RedisStudentRecordBook.from_url(url) as book:`), and there's no public `close()`. Only the tests scope a store this way; the bot and the reminder never close theirs and let the process exit release the connection.

`Tutor` never touches `StudentRecordBook`: it receives a plain `dict` from whichever frontend calls it. That's what keeps `tutoring` free of I/O.

## Chat state

Everything else about a Telegram chat lives in aiogram's FSM storage, a plain [`RedisStorage`](https://docs.aiogram.dev/en/latest/dispatcher/finite_state_machine/storages.html) used as aiogram ships it:

- **chat settings**: `language`, `ai_mode`, `topic_groups`, `remind_after_hours` (`_CHAT_SETTINGS_KEYS`, kept when an exercise ends — a new chat-level setting belongs in that tuple), plus the `bot_blocked` flag, set when the learner blocks the bot (see "Blocked chats" in [`CLAUDE.md`](https://github.com/pauk-slon/immer-wiederholen/blob/main/CLAUDE.md));
- **the conversation in progress**: the FSM state (`answering`, `recalling`), the exercise and recall being answered (`shown_exercise`, `shown_recall`), and the message whose inline buttons are still live (`last_buttoned_message_id`).

`/reset` wipes only the student record; none of this.

None of this goes into the student record: it's about one Telegram chat, not about what the learner knows, and the web app has its own equivalent (`WebSessionStore`, see [Web frontend](web-frontend.md)).

`wiederholen.bot` creates its `dispatcher` with aiogram's default in-memory storage, so importing the package — e.g. in tests — needs no Redis. The real stores are built at startup by `bootstrap.load_bot_course_and_storage()`, which returns the bot, the course, the `RedisStorage`, the `StudentRecordBook` and the `StudentIdentityStore`. Both the bot and the reminder call it: the reminder has no routers, but still reads each chat's FSM data for its language and settings.

## Student identity

A learner can be reached in more than one way — a Telegram chat, a logged-in browser — and each must lead to the same `StudentID`. [`StudentIdentityStore`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/school/student_identity_store.py) maps a login to it.

It keeps two concepts apart:

- an **account** — the learner and everything they've learned — is a `StudentID`, an opaque string `StudentRecordBook` is addressed by;
- a **login** is one way of proving you're that learner: a `provider` (`"telegram"` or `"browser"`) plus that provider's own `identifier` (a Telegram chat id, a browser token).

| Method | What it does |
|---|---|
| `resolve_or_create_student_id(provider, identifier)` | the learner for this login; for an unknown login, creates a new learner and links it. Every bot handler calls this |
| `resolve_student_id(provider, identifier)` | the same lookup, but `None` for an unknown login — for callers where that means "fall back to something else", like a stale browser cookie |
| `link_identity(student_id, provider, identifier)` | attaches a login to an existing learner. Raises `IdentityAlreadyLinkedError` if the login already belongs to a different learner; linking it to the same one again is a no-op |
| `iter_identifiers(provider)` | every `(identifier, student_id)` linked for one provider — the reminder uses it to find all Telegram chats |

New `StudentID`s are random (`secrets.token_urlsafe(32)`).

`RedisStudentIdentityStore` stores one key per login, `identity:{provider}:{identifier}`, holding the `StudentID`. It writes with `SET … NX`, so two first-time requests for the same new login racing each other end up with one learner, not two.

Anonymous web visitors aren't in this store at all: they have no login, and counting every page view as a learner would make the store's size meaningless. Their ids are random tokens kept in a cookie instead (`WebStudentID`, see [Web frontend](web-frontend.md)).

## Testing

Tests run against a real Redis (Valkey), not an in-memory fake: it's fast enough at this suite's size and catches behavior a fake wouldn't.

- **A dedicated database.** `tests/plugins/aiogram.py::pytest_configure` points all four store URLs at one database, 15 by default (the `--redis-db-override` option set in `pyproject.toml`), before any test runs. `docker compose run --rm bot pytest` shares the `bot` service's configuration, so without this the tests would write into the local bot's databases.
- **CI keeps the stores apart.** CI passes `--redis-db-override=""` and gives each store its own database on its throwaway Valkey, so a test that reads from the wrong store fails there instead of passing because everything shares one database.
- **Each fixture clears its own database.** `redis_storage` (FSM) and `student_record_book` flush their own databases before every test rather than assuming they share one.
- **Shared infrastructure is registered once.** The `student_record_book` fixture registers itself as permanent aiogram workflow data (`dispatcher["student_record_book"] = ...`), as `main()` does at startup, so tests don't pass it to every `feed_message()` call. The course differs between tests and is passed per call.
- **Function-scoped fixtures.** pytest-asyncio gives every test its own event loop, and a Redis connection can't outlive the loop it was created in.

## Design notes

- **`check_out`, not `open`.** `book.open(id)` reads as opening the book itself. Like a library checkout, `check_out` means borrowing one item and returning it, which is what the block does.
- **No public `close()`.** A store's lifetime is scoped with `async with`, the protocol Python readers already expect from anything holding a resource, so there's no close call to forget.
- **One store per kind of state, one environment variable each.** The stores share one Redis today, but separate URLs let any of them move to another server later. The student record and identity stores belong to `school` and are shared by every frontend; the session stores belong to one frontend each.
- **No separate account id type.** `StudentID` already is the account; an `AccountID` would be a second name for the same value.
- **Why a resolution step at all.** The bot used to derive a learner's id from the chat id directly. That tied "who is this learner" to "which Telegram chat is this" and left no way for a second login to reach the same learner.
- **Naming.** `identifier`, not `id` (shadows the builtin), `subject` (borrows OpenID Connect vocabulary for a protocol this isn't) or `provider_user_id` (long, once the store gives the context). The store was called `CredentialStore` until it became clear it holds no credential — only the result of one having been checked.
