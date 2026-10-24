# Storage and identity

This page describes where the state of each learner is stored, how handlers read and write it, and how a login leads to a learner. [Architecture](architecture.md#processes-and-state) gives an overview of all stores. [Configuration](configuration.md#redis) lists their environment variables.

In the code, a learner is a *student* (`StudentID`, `StudentRecord`, `StudentRecordBook`).

## Student records

A **student record** holds the learner's repetition schedule and progress. It is a plain JSON-compatible `dict` that `Tutor` reads and changes (see [Repetition schedule](repetition-schedule.md)). The record is the one piece of learner state that all frontends share, so a learner who practices in Telegram and then logs in on the web continues from the same point.

[`StudentRecordBook`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/school/student_record_book.py) stores records by `StudentID`. It has two public members:

- **`check_out(student_id)`.** An async context manager. It loads the record, gives it to the caller to change in place, and saves it when the block ends.
- **Iteration.** `async for student_id in student_record_book` yields the id of each learner with a stored record. Like the iteration of a `dict`, it yields only keys. To read a record, use `check_out()`. Today only the tests use iteration. The reminder finds learners through their Telegram logins instead (see [Student identity](#student-identity)).

Every handler that uses a record opens exactly one `check_out()` per request. It does all its work inside the block, including the replies:

```python
student_id = await student_identity_store.resolve_or_create_student_id(
    "telegram", str(message.chat.id)
)
async with student_record_book.check_out(student_id) as student_record:
    tutor = Tutor(course, student_record)
    # exercise: the one shown, read from the chat's FSM data
    mark = tutor.check_answer(exercise, message.text)
    await message.answer(...)
```

The method is called `check_out`, not `open`. `book.open(id)` would read as if it opens the book itself. A library checkout borrows one item and returns it, and the block does the same with a record.

### Saved only when changed

Right after it loads the record, `check_out()` makes a deep copy of it. When the block ends, `check_out()` saves the record only if it differs from that copy. This one rule works for every caller:

- A handler that always changes the record, such as one that records an answer, always saves.
- A handler that only reads, such as `/progress`, never writes.
- A handler that changes the record on one branch only saves only on that branch. An example is the reminder, which records a reminder only after Telegram accepted it.

The comparison runs in a `finally` block, so a change made before an error is still saved. For example, if `check_answer()` succeeded and then the reply failed, the answer isn't lost.

### Concurrent requests: last write wins

`check_out()` doesn't lock anything. aiogram handles updates concurrently by default (`handle_as_tasks=True`). If two updates from one learner arrive at the same time, for example after two quick taps, both load the same version of the record. The update that saves last overwrites the changes of the other. Today nothing protects against this (see [#249](https://github.com/pauk-slon/immer-wiederholen/issues/249)).

### Redis implementation

`RedisStudentRecordBook` stores one JSON value per learner under `student_record:{student_id}`. An empty record has no key at all, so iteration doesn't show a learner with nothing recorded.

Only the Redis implementations close a connection. The abstract stores have no such step. `RedisStudentRecordBook` and `RedisStudentIdentityStore` are async context managers (`async with RedisStudentRecordBook.from_url(url) as book:`). They have no public `close()` that a caller could forget. `async with` limits the lifetime of a store, because Python readers expect this protocol from an object that holds a resource. Only the tests use stores this way. The bot and the reminder never close their stores, and the connection closes when the process exits.

`Tutor` never uses `StudentRecordBook`. It gets a plain `dict` from the frontend that calls it, and this keeps `tutoring` free of I/O.

## Chat state

The other state of a Telegram chat is in aiogram's FSM storage. This is a plain [`RedisStorage`](https://docs.aiogram.dev/en/latest/dispatcher/finite_state_machine/storages.html), used as aiogram ships it. It has two kinds of data:

- **Chat settings.** These are `language`, `ai_mode`, `topic_groups` and `remind_after_hours`, and the `bot_blocked` flag that the bot sets when the learner blocks it (see [Blocked chats](bot.md#blocked-chats)).
- **The current conversation.** This is the FSM state (`answering`, `recalling`), the exercise and recall that the learner is answering (`shown_exercise`, `shown_recall`), and the message with active inline buttons (`last_buttoned_message_id`).

When an exercise ends, the bot clears the conversation but keeps the settings. `_CHAT_SETTINGS_KEYS` in `commands/wiederholen.py` lists the settings. Add a new chat-level setting to it, or the setting is lost after every exercise.

None of this data is part of the student record, because it is about one Telegram chat and not about what the learner knows. For this reason `/reset`, which deletes the record, doesn't change it. The web app has its own store for the same purpose (`WebSessionStore`, see [Web frontend](web-frontend.md)).

`wiederholen.bot` creates its `dispatcher` with aiogram's default in-memory storage, so an import of the package, for example in tests, needs no Redis. At startup, `bootstrap.load_bot_course_and_storage()` builds the real stores. It returns the bot, the course, the `RedisStorage`, the `StudentRecordBook` and the `StudentIdentityStore`. The bot and the reminder both call it. The reminder has no routers, but it still reads the FSM data of each chat for its language and settings.

## Student identity

A learner can use the project in more than one way, for example in a Telegram chat or in a logged-in browser. Each way must lead to the same `StudentID`. [`StudentIdentityStore`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/school/student_identity_store.py) maps a login to it. The id isn't derived from the chat, and there's no separate account id (see [ADR 0003](adr/0003-separate-accounts-from-logins.md)).

The store keeps two concepts apart:

- An **account** is the learner and what they have learned. It is a `StudentID`, an opaque random string (`secrets.token_urlsafe(32)`). `StudentRecordBook` uses it as the key.
- A **login** is one way to prove that you are that learner. It is a `provider` (`"telegram"` or `"browser"`) with that provider's own `identifier`. The identifier is a Telegram chat id, or a browser token that the web app makes when someone logs in with Telegram.

| Method | What it does |
|---|---|
| `resolve_or_create_student_id(provider, identifier)` | returns the learner for this login. For an unknown login, it creates a new learner and links the login to it. The bot calls it for every update, and the web app calls it after a Telegram login. This is how both frontends get the same learner |
| `resolve_student_id(provider, identifier)` | the same lookup, but it returns `None` for an unknown login. It is for callers that then use something else, such as a request with an old browser cookie |
| `link_identity(student_id, provider, identifier)` | links a login to an existing learner. It raises `IdentityAlreadyLinkedError` if the login already belongs to a different learner. A second link to the same learner does nothing |
| `iter_identifiers(provider)` | yields each `(identifier, student_id)` for one provider. The reminder uses it to find all Telegram chats |

`RedisStudentIdentityStore` stores one key per login, `identity:{provider}:{identifier}`, with the `StudentID` as the value. It writes with `SET … NX`. If two first requests for the same new login arrive at the same time, the result is one learner, not two.

Anonymous web visitors aren't in this store. They have no login, and if every visitor counted as a learner, the size of the store would mean nothing. Their ids are random tokens in a cookie (`WebStudentID`, see [Web frontend](web-frontend.md)).

The parameter is called `identifier`, not `id`, because `id` would shadow the builtin. Other names were too long or came from other protocols.

## Testing

Tests use a real Redis (Valkey), not an in-memory fake. Valkey is fast enough for a test suite of this size, and it catches behavior that a fake would miss.

- **A dedicated database.** Before any test runs, `tests/plugins/aiogram.py::pytest_configure` sets all four store URLs to one database. By default this is database 15, from the `--redis-db-override` option in `pyproject.toml`. `docker compose run --rm bot pytest` uses the configuration of the `bot` service, and the fixtures flush their database before every test. Without this option, a test run would delete the data of the local bot.
- **Separate stores in CI.** CI passes `--redis-db-override=""` and gives each store its own database on a temporary Valkey. A test that reads from the wrong store then fails in CI. With one shared database, it would pass.
- **Each fixture clears its own database.** Every store fixture (`redis_storage` for FSM, `student_record_book`, `student_identity_store`, `web_session_store`) flushes its own database before every test. It doesn't assume that the stores share one database.
- **Shared objects are registered once.** The `student_record_book` fixture registers itself as permanent aiogram workflow data (`dispatcher["student_record_book"] = ...`), as `main()` does at startup, so tests don't pass it to every `feed_message()` call. The course differs between tests, so tests pass it with each call.
- **Function-scoped fixtures.** pytest-asyncio gives every test its own event loop, and a Redis connection can't outlive the loop that created it.

## Decisions

- [Separate learners from the ways they log in](adr/0003-separate-accounts-from-logins.md) (ADR 0003)
- [Save a student record only when it changes](adr/0007-save-records-only-when-changed.md) (ADR 0007)
- [Keep the student record separate from chat state](adr/0008-student-record-separate-from-chat-state.md) (ADR 0008)
- [One environment variable per store](adr/0009-one-environment-variable-per-store.md) (ADR 0009)
