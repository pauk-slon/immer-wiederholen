# Telegram bot

How `wiederholen.bot` works: the commands, how an exercise is shown, the per-chat settings, reminders, and the bookkeeping around inline buttons. Where the package sits among the others is in [Architecture](architecture.md); how its state is stored is in [Storage and identity](storage.md).

## Commands

Each command lives in its own module under [`wiederholen/bot/commands/`](https://github.com/pauk-slon/immer-wiederholen/tree/main/wiederholen/bot/commands):

| Command | Module | What it does |
|---|---|---|
| `/start` | `start` | greets the learner. A deep link with a language (`t.me/<bot>?start=en`) sets the chat's language |
| `/wiederholen` | `wiederholen` | shows the next exercise; the same module handles answers, recalls and the "next" and "study more" buttons |
| `/progress` | `progress` | today's counts (due, new, answered) and how many words are being learned or mastered (see [Repetition schedule](repetition-schedule.md)) |
| `/topics` | `topics` | which topic groups to practice, see [Topic selection](#topic-selection) |
| `/reminders` | `reminders` | how long after the last session to send a reminder, see [Reminders](#reminders) |
| `/language` | `language` | switches between Russian and English |
| `/reset` | `reset` | wipes the learner's schedule after a confirmation |
| `/ai` | `ai` | switches the chat to questions rewritten by an LLM, for topics with `ai_generation`; only for chats with the `ai_exercises` [feature flag](#feature-flags). see [AI-generated content](authoring.md#shadow-exercises) |

The bot's texts in both languages are in [`l10n.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/l10n.py).

## Showing an exercise

`_format_question()` in `commands/wiederholen.py` builds the question message. Under the question (`❓`) it adds, when present:

- the shuffled `word_bank` chunks in parentheses, reshuffled on every showing;
- the `description` (`💭`);
- the topic's `instruction` (`ℹ️`);
- a hint from grammar classes (`🔍`), hidden behind a tap-to-reveal spoiler, see [Hints from grammar classes](#hints-from-grammar-classes).

An AI-generated question is marked with `🤖`. A multiple-choice exercise gets its options as a reply keyboard; a typed one removes the keyboard.

The message is sent with `parse_mode="HTML"`, so **every piece of authored text is passed through `html.escape()`** — otherwise a `<`, `>` or `&` in a question would break the markup.

If the topic has illustrations and one exists for the question, the question is sent as a photo with the text as its caption — unless the text is longer than Telegram's 1024-character caption limit. A failed lookup is logged and the question is sent as plain text, so a storage problem never blocks practice.

## Answering

1. The learner answers — taps an option or types. The bot says whether it was right (showing the correct answer if not), removes the options keyboard, and sends the `explanation`.
2. What comes next depends on the exercise's recalls (see [Recalls](course-format.md#recalls)):
   - **wrong answer, exercise has recalls**: a recall starts right away — the learner must write out the sentence;
   - **right answer, exercise has recalls**: the explanation comes with two buttons, "Drill" ("Закрепить") for an optional recall and "Next exercise" ("Следующее задание");
   - **no recalls**: just "Next exercise".
3. A recall answer gets "correct" and a "Next exercise" button, or the correct sentence with the parts that differ from the learner's answer underlined, and "Try again" ("Попробовать ещё раз") or "Next exercise".

When nothing is left for today, `/wiederholen` and "Next exercise" reply that the day is done, with a "Study more" ("Позаниматься ещё") button. A tap raises today's limit on new words by 3 (`Tutor.grant_new_word_budget()`, see [Repetition schedule](repetition-schedule.md)) and shows the next exercise. If the limit wasn't what stopped the learner — they've simply done everything — the limit stays as it is and the reply is "the day is done" again.

## Chat settings

| Setting | FSM key | Set by | Used by |
|---|---|---|---|
| language | `language` | `/language`, a `/start` deep link | every reply, the reminder |
| topic groups | `topic_groups` | `/topics` | choosing what to show, the reminder — see below |
| reminder interval | `remind_after_hours` | `/reminders` | the reminder, see [The /reminders setting](#the-reminders-setting) |
| AI mode | `ai_mode` | `/ai` | choosing whether to rewrite a question |

All four are listed in `_CHAT_SETTINGS_KEYS` in `commands/wiederholen.py`, which keeps them when an exercise ends and the rest of the chat's state is cleared. **A new chat-level setting must be added there**, or it's lost after every exercise. The tuple replaced restoring `ai_mode` by hand after each exercise, which was missed at one of four call sites and made AI mode silently switch off after a single exercise. `/reset` doesn't touch settings; see [Storage and identity](storage.md#chat-state).

### Topic selection

`/topics` shows one inline button per topic group (`✅` or `⬜`) and a "Done" button. Each tap toggles a group and saves immediately; "Done" replaces the menu with a summary and a "Next exercise" button. The selection is stored as `topic_groups`, a list of group ids.

[`topic_selection.restrict_to_selected_groups()`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/topic_selection.py) narrows the course to the selected groups with `Course.restricted_to()`, the same narrowing the web widget uses. An empty selection means all topics. Group ids the course no longer defines are ignored, so if none of the selected groups exists any more, the learner gets all topics rather than none.

It's applied where the bot picks something to show: `/wiederholen`, the "next" and "study more" buttons, and the reminder (so nobody is reminded about groups they deselected). It's deliberately not applied to:

- **`/progress`**, which shows everything the learner has learned, not just today's focus;
- **checking an answer**: an exercise already shown is checked against the full course, so a chain into an unselected group still schedules progress there.

The daily limit on new words counts all topics, selected or not.

## Reminders

A separate process, [`python -m wiederholen.bot.reminder`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/reminder.py), messages learners who have gone quiet while they have something to practice. Every 15 minutes it runs `tick()`: for each Telegram chat linked in `StudentIdentityStore` (`iter_identifiers("telegram")`), `_remind_chat()` decides and maybe sends. It's a separate process rather than a task inside the bot (see [ADR 0010](adr/0010-reminders-as-a-separate-process.md)).

For one chat, in order:

1. Read the chat's FSM data. Stop if the learner has blocked the bot (see [Blocked chats](#blocked-chats)) or turned reminders off.
2. Narrow the course to the selected topic groups.
3. Check out the student record and ask `Tutor.should_remind(remind_after)`.
4. Remove the buttons from the chat's previous buttoned message (see [Pending inline buttons](#pending-inline-buttons)) and send the reminder with a "Next exercise" button.
5. On success, `Tutor.record_reminder_sent()`. The student record is saved only on this path, because only this path changes it.

An error in one chat is logged and the sweep moves on.

### When a reminder is due

`Tutor.should_remind(remind_after)` decides, so the rule lives with the rest of the schedule. It's true only when all of these hold:

- **the learner has answered at least once**: someone who pressed `/start` and never answered is never reminded;
- **there's something to practice**: a review is due, or new material is available. The daily limit on new words is ignored here — a learner at the limit with overdue reviews should still be reminded (an earlier version checked only for new material and missed them);
- **the learner has gone quiet**: the last answer to a main exercise was at least `remind_after` ago. Recall answers and other interactions don't count;
- **no reminder since then**: at most one reminder per period of inactivity, never a repeated nag.

`should_remind()` changes nothing. `record_reminder_sent()` is called only after Telegram accepted the message, so a failed send is never counted as delivered.

### The /reminders setting

`/reminders` offers 4, 8, 12 or 24 hours after the last answer (24 by default), or off, as one button each; a tap saves and confirms. The choice is stored as `remind_after_hours`, with `0` meaning off — distinct from "never chosen", which means the default. A stored value that's no longer offered falls back to the default ([`reminder_settings.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/reminder_settings.py)). Unlike `/topics`, there's no "Done" step: one choice, one tap. The interval counts from the last answer rather than following a schedule (see [ADR 0011](adr/0011-remind-after-the-last-session.md)).

It's an interval since the last session, not "every N hours" or "N times a day": still one reminder per period of inactivity, so nothing piles up overnight, while an active learner may get several a day, one after each session. There's no time zone handling; muting at night is left to the phone.

### Blocked chats

The Bot API can't tell whether a learner has blocked the bot. Telegram only says so with a `my_chat_member` update (status `kicked` in a private chat, `member` again on unblock) or with a 403 (`TelegramForbiddenError`) on the next message.

[`chat_membership.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/chat_membership.py) handles the update and stores `bot_blocked: True` in the chat's FSM data, removing it on unblock. aiogram subscribes to `my_chat_member` updates automatically once a handler for them exists. The reminder skips chats with the flag before touching the student record or Telegram, and a 403 when sending sets the flag too — which covers learners who blocked the bot before this was handled, or whose update was missed.

The flag isn't in `_CHAT_SETTINGS_KEYS`, so ending an exercise would drop it — but a learner who has blocked the bot isn't answering one. If it's ever lost anyway, the worst case is one refused message that sets it again.

## Pending inline buttons

Tapping an inline button ("Next exercise", "Drill", "Study more", …) removes that button: the callback handler edits its own message. Typing a command instead doesn't — Telegram never tells the bot which earlier message a command replaces — so without extra work, old buttons would stay attached forever.

[`pending_buttons.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/pending_buttons.py) tracks one message id per chat in FSM data, `last_buttoned_message_id` — a chat has at most one live set of buttons at a time:

- **`remember_buttoned_message(state, message)`** — call it right after sending a message with an inline keyboard.
- **`forget_buttoned_message(state)`** — call it when a callback handler has removed its own buttons and attached nothing new.
- **`clear_stale_buttons(bot, chat_id, state)`** — removes the buttons from the remembered message, if any, and forgets it. A `TelegramBadRequest` (the message was already edited, deleted or is too old) is ignored.

Every command that the learner types — `/wiederholen`, `/progress`, `/topics`, `/reminders`, `/language`, `/reset`, `/ai` — calls `clear_stale_buttons()` first; `/start` is the one typed command that doesn't. The reminder calls it right before sending. `clear_stale_buttons()` takes a bot and a chat id rather than a `Message`, because the reminder has no incoming message.

When editing a message's text, pass `reply_markup=` explicitly — a new keyboard or `None`: editing the text alone keeps the old keyboard.

## Feature flags

[`feature_flags.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/feature_flags.py) turns a feature on for specific chats, from the `BOT_FEATURE_FLAGS` variable (format in [Configuration](configuration.md#ai-generated-questions)). It was built to try AI-generated questions on a test user without any billing.

`bootstrap.load_feature_flags()` parses the variable once at startup into `dict[str, frozenset[int]]`, and `main()` passes it to `start_polling()` as `feature_flags`, so any handler that declares a `feature_flags` parameter gets it. A handler checks a chat with `has_feature(feature_flags or {}, "ai_exercises", chat_id)`; the parameter defaults to `None` so tests that don't care needn't pass it.

There's no storage and no admin command: changing a flag means editing the variable and restarting. That's fine for a handful of test chats. The flags stay in the bot layer: `wiederholen.school` never sees a chat id or a flag name.

## Hints from grammar classes

What the learner sees and how to tag exercises is in [Course format](course-format.md#hints-from-grammar-classes). The choice is made by `Tutor.get_hint(exercise)`:

1. Collect other words of the same topic whose `grammar_classes` overlap this exercise's.
2. Keep those the learner knows well: a repetition interval above one day, which means the word has been confirmed at least once after its first answer. An interval of `0` can't tell "answered wrong" from "answered once", and `1` is a single success, so neither counts.
3. Return the word with the longest interval — the best-remembered anchor — choosing randomly among ties; `None` if nothing qualifies.

It returns just the word: the bot renders it with `Locale.grammar_class_hint` ("Same as for {word}"), deliberately without the other word's answer, which for a class like `an+Akk` would give this answer away. `get_hint()` only reads the record. It's called after AI mode has resolved the exercise to show; `grammar_classes` survives the AI rewrite unchanged.

The web widget doesn't show these hints yet.

## Testing

Handler tests run updates through the real dispatcher against a real Redis — FSM data and student records included, see [Storage and identity](storage.md#testing). They feed raw updates to the dispatcher with fixtures from [`tests/plugins/aiogram.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/tests/plugins/aiogram.py) (`feed_message`, `feed_callback_query`). Telegram calls are mocked: `send_message` returns a synthetic `Message` with an increasing `message_id` starting at 1000, so tests of button tracking can check which message was remembered; every other method returns `True`.

The reminder's tests call `tick()` directly, with no incoming update, so [`tests/bot/test_reminder.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/tests/bot/test_reminder.py) mocks Telegram the same way on its own.

## Decisions

- [ADR 0010](adr/0010-reminders-as-a-separate-process.md): reminders run as a separate process.
- [ADR 0011](adr/0011-remind-after-the-last-session.md): reminders count from the last session.
