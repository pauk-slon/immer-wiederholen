# Telegram bot

This page describes how `wiederholen.bot` works. It covers the commands, how the bot shows an exercise, the chat settings, the reminders and the tracking of inline buttons. [Architecture](architecture.md) shows where the package sits among the others. [Storage and identity](storage.md) describes how its state is stored.

## Commands

Each command has its own module under [`wiederholen/bot/commands/`](https://github.com/pauk-slon/immer-wiederholen/tree/main/wiederholen/bot/commands):

| Command | Module | What it does |
|---|---|---|
| `/start` | `start` | greets the learner. A deep link with a language (`t.me/<bot>?start=en`) sets the language of a new chat, a chat that has no FSM data yet (see [ADR 0019](adr/0019-start-payload-sets-only-a-new-language.md)) |
| `/wiederholen` | `wiederholen` | shows the next exercise. The same module handles answers, recalls and the "next" and "study more" buttons |
| `/progress` | `progress` | shows today's counts (due, new, answered), how many words the learner is learning or has mastered and, if there is one, the streak (see [Repetition schedule](repetition-schedule.md)) |
| `/topics` | `topics` | lets the learner choose the topic groups to practice (see [Topic selection](#topic-selection)) |
| `/reminders` | `reminders` | lets the learner choose how long after the last session the bot sends a reminder (see [Reminders](#reminders)) |
| `/language` | `language` | switches between Russian and English |
| `/reset` | `reset` | deletes the learner's schedule and today's answer counts after a confirmation. The streak stays |
| `/ai` | `ai` | switches the chat to exercises that an LLM rewrites, for topics with `ai_generation`. Only chats with the `ai_exercises` [feature flag](#feature-flags) have it (see [AI-generated content](authoring.md#shadow-exercises)) |

[`l10n.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/l10n.py) has the bot's texts in both languages.

## Showing an exercise

`_format_question()` in `commands/wiederholen.py` builds the question message. Under the question (`❓`), it adds these parts if the exercise has them:

- the `word_bank` chunks in parentheses, shuffled again each time the bot shows the exercise
- the `description` (`💭`)
- the topic's `instruction` (`ℹ️`)
- a hint from grammar classes (`🔍`), hidden in a spoiler that the learner taps to open (see [Hints from grammar classes](#hints-from-grammar-classes))

The bot marks an AI-generated question with `🤖`. A multiple-choice exercise shows its options as a reply keyboard. In a topic with `show_primary_answer_only`, the primary answer is the only correct option. For an exercise with a typed answer, the bot removes the keyboard.

The bot sends the message with `parse_mode="HTML"`, so **every piece of authored text goes through `html.escape()`**. Without it, a `<`, `>` or `&` in a question would break the markup.

If the topic has illustrations and the question has one, the bot sends the question as a photo with the text as its caption. If the text is longer than Telegram's caption limit of 1024 characters, the bot sends it as plain text. If the lookup fails, the bot logs the error and sends the question as plain text, so a storage problem never stops practice.

## Answering

1. The learner answers with a tap on an option or with typed text. The bot says whether the answer was right and shows the correct answers if it wasn't. In a topic with `show_primary_answer_only`, the bot shows only the primary answer (see [Course format](course-format.md#several-correct-answers)). Then the bot removes the options keyboard and sends the `explanation`.
2. The next step depends on the exercise's recalls (see [Recalls](course-format.md#recalls)):
   - **Wrong answer, the exercise has recalls.** A recall starts at once, and the learner must type the sentence.
   - **Right answer, the exercise has recalls.** The explanation comes with two buttons, "Drill" ("Закрепить") for an optional recall and "Next exercise" ("Следующее задание").
   - **No recalls.** The explanation comes with only a "Next exercise" button.
3. After a right recall answer, the bot says "correct" and shows a "Next exercise" button. After a wrong one, the bot shows the correct sentence and underlines the parts that differ from the learner's answer. It also shows "Try again" ("Попробовать ещё раз") and "Next exercise".

When nothing is left for today, `/wiederholen` and "Next exercise" reply that the day is done. If the learner has a streak, the reply also shows its length (see [Repetition schedule](repetition-schedule.md#streak)). The reply has a "Study more" ("Позаниматься ещё") button. A tap raises today's limit on new words by 3 (`Tutor.grant_new_word_budget()`, see [Repetition schedule](repetition-schedule.md)) and shows the next exercise. If the learner has answered all available exercises, the limit isn't the reason. In this case the limit stays the same, and the reply says again that the day is done.

## Chat settings

| Setting | FSM key | Set by | Used by |
|---|---|---|---|
| language | `language` | `/language`, a `/start` deep link in a new chat | every reply, the reminder |
| topic groups | `topic_groups` | `/topics` | the choice of what to show, the reminder (see below) |
| reminder interval | `remind_after_hours` | `/reminders` | the reminder (see [The /reminders setting](#the-reminders-setting)) |
| AI mode | `ai_mode` | `/ai` | the choice whether to rewrite a question |

`_CHAT_SETTINGS_KEYS` in `commands/wiederholen.py` lists all four settings. When an exercise ends, the bot clears the chat's state but keeps the keys in this tuple. **Add a new chat-level setting to this tuple**, or the setting is lost after every exercise. Before the tuple, the code restored `ai_mode` by hand after each exercise. One of four call sites missed it, and AI mode silently switched off after one exercise. `/reset` doesn't change settings (see [Storage and identity](storage.md#chat-state)).

### Topic selection

`/topics` shows one inline button per topic group (`✅` or `⬜`) and a "Done" button. Each tap selects or deselects a group and saves the selection at once. "Done" replaces the menu with a summary and a "Next exercise" button. The bot stores the selection as `topic_groups`, a list of group ids.

[`topic_selection.restrict_to_selected_groups()`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/topic_selection.py) limits the course to the selected groups with `Course.restricted_to()`. The web widget uses the same method. An empty selection means all topics. The function ignores group ids that the course no longer defines. If none of the selected groups exists any more, the learner gets all topics, not none.

The bot applies the selection where it picks something to show. These places are `/wiederholen`, the "next" and "study more" buttons, and the reminder, so no learner gets a reminder about groups that they deselected. The bot intentionally doesn't apply the selection in two places:

- **`/progress`.** It shows the learner's progress in all topics, not only today's focus.
- **Answer checks.** The bot checks an exercise that it already showed against the full course, so a chain into an unselected group still schedules progress there.

The daily limit on new words counts all topics, selected or not.

## Reminders

A separate process, [`python -m wiederholen.bot.reminder`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/reminder.py), sends a message to learners who stopped answering and have something to practice. It is a separate process, not a task inside the bot (see [ADR 0010](adr/0010-reminders-as-a-separate-process.md)). Every 15 minutes it runs `tick()`. `tick()` checks each Telegram chat in `StudentIdentityStore` (`iter_identifiers("telegram")`). For each chat, `_remind_chat()` decides whether to send a reminder and sends it if needed.

For one chat, these steps happen in order:

1. Read the chat's FSM data. Stop if the learner has blocked the bot (see [Blocked chats](#blocked-chats)) or turned reminders off.
2. Limit the course to the selected topic groups.
3. Open the student record with `check_out()` and ask `Tutor.should_remind(remind_after)`.
4. Remove the buttons from the chat's previous message with buttons (see [Pending inline buttons](#pending-inline-buttons)). Send the reminder with a "Next exercise" button. If the learner has a streak, the reminder also says how long the streak is and in how many hours it ends. The hours are rounded up, so the last hour shows as 1 hour, not 0. The longest `/reminders` interval is 24 hours, so a streak always has at least 12 hours left when the reminder comes.
5. If Telegram accepts the message, call `Tutor.record_reminder_sent()`. Only this step changes the student record, so the record is saved only in this case.

If one chat fails, the reminder logs the error and continues with the next chat.

### When a reminder is due

`Tutor.should_remind(remind_after)` makes the decision, so the rule stays with the rest of the schedule. It returns true only if all of these conditions are true:

- **The learner has answered at least once.** A learner who pressed `/start` and never answered never gets a reminder.
- **There's something to practice.** A review is due, or new material is available. Here the daily limit on new words doesn't count. A learner at the limit who has overdue reviews should still get a reminder. An earlier version checked only for new material and missed such learners.
- **The learner stopped answering.** The last answer to a main exercise was at least `remind_after` ago. Recall answers and other actions don't count.
- **No reminder since then, with one exception.** The bot sends one reminder per period of inactivity. A learner with a streak of at least 2 days can get a second reminder. It comes in the hour after the 24-hour mark since the last answer, so it comes at the time of day of the last session and about 12 hours before the streak ends. The first reminder must have come at least 6 hours before that mark, so two reminders never come close together. With the default interval of 24 hours, the first reminder comes after the mark, so there's no second one (see [ADR 0025](adr/0025-second-reminder-for-a-streak.md)).

`should_remind()` changes nothing. The reminder calls `record_reminder_sent()` only after Telegram accepted the message, so a failed send never counts as delivered.

### The /reminders setting

`/reminders` offers 4, 8, 12 or 24 hours after the last answer, or off, with one button each. The default is 24 hours. A tap saves the choice and confirms it. The bot stores the choice as `remind_after_hours`. The value `0` means off, which is different from "never chosen". "Never chosen" means the default. If the stored value is no longer offered, [`reminder_settings.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/reminder_settings.py) uses the default. Unlike `/topics`, there's no "Done" step, because the setting needs only one tap. The interval counts from the last answer and doesn't follow a fixed schedule (see [ADR 0011](adr/0011-remind-after-the-last-session.md)).

The setting is an interval since the last session, not "every N hours" or "N times a day". It gives at most two reminders per period of inactivity, so reminders don't accumulate overnight. An active learner can get several reminders a day, one after each session. The bot doesn't handle time zones. The learner's phone can mute notifications at night.

### Blocked chats

The Bot API can't tell whether a learner has blocked the bot. Telegram reports it in only two ways. One is a `my_chat_member` update, with status `kicked` in a private chat and `member` again after an unblock. The other is a 403 error (`TelegramForbiddenError`) on the next message.

[`chat_membership.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/chat_membership.py) handles the update. It stores `bot_blocked: True` in the chat's FSM data and removes it after an unblock. aiogram subscribes to `my_chat_member` updates automatically when a handler for them exists. The reminder skips chats with the flag before it opens the student record or calls Telegram. A 403 on send also sets the flag. This covers learners who blocked the bot before this handler existed, and learners whose update was lost.

The flag isn't in `_CHAT_SETTINGS_KEYS`, so the end of an exercise would remove it. But a learner who has blocked the bot doesn't answer exercises. If the flag is lost anyway, the worst case is one refused message, and that message sets the flag again.

## Pending inline buttons

A tap on an inline button ("Next exercise", "Drill", "Study more" and others) removes that button, because the callback handler edits its own message. A typed command doesn't remove buttons, because Telegram never tells the bot which earlier message a command replaces. Without extra work, old buttons would stay on their messages forever.

[`pending_buttons.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/pending_buttons.py) tracks one message id per chat in FSM data, `last_buttoned_message_id`. A chat has at most one active set of buttons at a time. The module has three functions:

- **`remember_buttoned_message(state, message)`.** Call it right after you send a message with an inline keyboard.
- **`forget_buttoned_message(state)`.** Call it when a callback handler removed its own buttons and attached no new ones.
- **`clear_stale_buttons(bot, chat_id, state)`.** It removes the buttons from the remembered message, if there is one, and forgets the message. It ignores a `TelegramBadRequest`, which means that the message was already edited, deleted or is too old.

Every command that the learner types calls `clear_stale_buttons()` first. These commands are `/wiederholen`, `/progress`, `/topics`, `/reminders`, `/language`, `/reset` and `/ai`. `/start` is the one typed command that doesn't call it. The reminder calls it right before it sends a message. `clear_stale_buttons()` takes a bot and a chat id, not a `Message`, because the reminder has no incoming message.

When you edit the text of a message, pass `reply_markup=` explicitly, with a new keyboard or `None`. If you edit only the text, the message keeps its old keyboard.

## Feature flags

[`feature_flags.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/feature_flags.py) enables a feature for specific chats, based on the `BOT_FEATURE_FLAGS` variable. [Configuration](configuration.md#ai-generated-questions) describes its format.

At startup, `bootstrap.load_feature_flags()` parses the variable once into a `dict[str, frozenset[int]]`. `main()` passes it to `start_polling()` as `feature_flags`, so every handler that declares a `feature_flags` parameter gets it. A handler checks a chat with `has_feature(feature_flags or {}, "ai_exercises", chat_id)`. The parameter defaults to `None`, so tests that don't need flags don't have to pass it.

The flags have no storage and no admin command. To change a flag, edit the variable and restart the bot. This is enough for a few test chats. The flags stay in the bot layer, and `wiederholen.school` never sees a chat id or a flag name.

## Hints from grammar classes

[Course format](course-format.md#hints-from-grammar-classes) describes what the learner sees and how to tag exercises. `Tutor.get_hint(exercise)` chooses the hint:

1. Collect the other words of the same topic whose `grammar_classes` overlap with this exercise's classes.
2. Keep the words that the learner knows well. Such a word has a repetition interval above one day, so the learner has answered it correctly at least once after its first answer. An interval of `0` can mean "answered wrong" or "answered once", and `1` is one success, so neither counts.
3. Return the word with the longest interval, because the learner remembers it best. Choose at random among words with the same interval. Return `None` if no word qualifies.

`get_hint()` returns only the word. The bot renders it with `Locale.grammar_class_hint` ("Same as for {word}"). The hint intentionally doesn't include the other word's answer. For a class like `an+Akk`, that answer would also be the answer to this question. `get_hint()` only reads the record. The bot calls it after `_apply_ai_mode()` decides which exercise to show. `grammar_classes` doesn't change when AI mode rewrites an exercise.

The web widget doesn't show these hints yet.

## Testing

Handler tests send updates through the real dispatcher, with a real Redis for FSM data and student records (see [Storage and identity](storage.md#testing)). They use fixtures from [`tests/plugins/aiogram.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/tests/plugins/aiogram.py) (`feed_message`, `feed_callback_query`) to send raw updates to the dispatcher. The tests mock the Telegram calls. `send_message` returns a synthetic `Message` with a `message_id` that starts at 1000 and increases, so tests of button tracking can check which message the bot remembered. Every other method returns `True`.

The reminder's tests call `tick()` directly, with no incoming update, so [`tests/bot/test_reminder.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/tests/bot/test_reminder.py) mocks Telegram in the same way by itself.

## Decisions

- [Reminders run as a separate process](adr/0010-reminders-as-a-separate-process.md) (ADR 0010)
- [Reminders count from the last session](adr/0011-remind-after-the-last-session.md) (ADR 0011)
- [A streak of 2 days or more gets a second reminder](adr/0025-second-reminder-for-a-streak.md) (ADR 0025)
