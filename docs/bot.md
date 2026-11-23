# Telegram bot

This page describes how `wiederholen.bot` works. It covers the commands, how the bot shows an exercise, the chat settings, the reminders and the tracking of inline buttons. [Architecture](architecture.md) shows where the package sits among the others. [Storage and identity](storage.md) describes how its state is stored.

## Commands

Each command has its own module under [`wiederholen/bot/commands/`](https://github.com/pauk-slon/immer-wiederholen/tree/main/wiederholen/bot/commands):

| Command | Module | What it does |
|---|---|---|
| `/start` | `start` | greets the learner. A deep link can set the language and the topic groups of a new chat, a chat that has no FSM data yet. See [ADR 0019](adr/0019-start-payload-sets-only-a-new-language.md) for the language (`t.me/<bot>?start=en`) and [Topic groups from a link](#topic-groups-from-a-link) for the groups |
| `/wiederholen` | `wiederholen` | shows the next exercise, or the current one again if it has no answer yet. The same module handles answers, recalls and the "next" and "study more" buttons |
| `/progress` | `progress` | shows today's counts (due, new, answered), how many words the learner is learning or has mastered and, if there is one, the streak (see [Repetition schedule](repetition-schedule.md)) |
| `/topics` | `topics` | lets the learner choose the topic groups to practice (see [Topic selection](#topic-selection)) |
| `/reminders` | `reminders` | lets the learner choose how long after the last session the bot sends a reminder (see [Reminders](#reminders)) |
| `/language` | `language` | switches between Russian and English |
| `/reset` | `reset` | deletes the learner's schedule and today's answer counts after a confirmation. The streak stays |

`lesson_recall` has no command. It handles the [lesson recall](#lesson-recall) after a lesson.

`fallback` has no command either. Its router comes last and takes every message that no other handler takes: text outside an exercise, an unknown command such as `/help`, a sticker or a photo. The bot replies with what it does and the "next" button. Without this reply, a learner who wrote to the bot after `/start` got no answer, and the bot looked broken. The reply is the same in every state, because the "next" button already leads to the right place, for example to "That's all for today". The bot doesn't start an exercise on such a message, because the learner may have asked a question. The handler removes the buttons of the earlier message like every typed command does. A message during an exercise or a lesson recall still goes to its handler.

[`l10n.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/l10n.py) has the bot's texts in both languages.

## Showing an exercise

`_format_question()` in `commands/wiederholen.py` builds the question message. Under the question, it adds the parts that the exercise has: the `word_bank` chunks, the `description`, the topic's `instruction` and a hint from grammar classes (see [Hints from grammar classes](#hints-from-grammar-classes)). The `word_bank` chunks are shuffled again each time the bot shows the exercise.

A multiple-choice exercise shows its options as a reply keyboard. In a topic with `show_primary_answer_only`, the primary answer is the only correct option. For an exercise with a typed answer, the bot removes the keyboard.

The bot sends the message with `parse_mode="HTML"`, so **every piece of authored text goes through `html.escape()`**. Without it, a `<`, `>` or `&` in a question would break the markup.

If the topic has illustrations, the exercise doesn't have `cue: false` and the question has an illustration, the bot sends the question as a photo with the text as its caption. If the text is longer than Telegram's caption limit of 1024 characters, the bot sends it as plain text. If the lookup fails, the bot logs the error and sends the question as plain text, so a storage problem never stops practice.

### Showing a waiting exercise again

If the learner sends `/wiederholen` while the bot waits for an answer, the bot shows the same exercise again. The "Next exercise" and "Study more" buttons do the same. Otherwise, with lessons of several exercises, a learner could skip all exercises of a lesson and get a streak day without answers (see [#325](https://github.com/pauk-slon/immer-wiederholen/issues/325)). Such a button can come while the bot waits for an answer, for example in a reminder.

The bot shows the next exercise instead in these cases:

- The learner answers a recall.
- The learner deselected the topic of the shown exercise in `/topics` after the bot showed it.

The bot doesn't call `Tutor` to show the exercise again. With `shown_exercise`, the bot keeps the hint from grammar classes in `shown_hint_word` (see [Hints from grammar classes](#hints-from-grammar-classes)) and the lesson counter in `shown_lesson_counter`. So the question looks the same. Only the order of the options and of the `word_bank` chunks can change.

## Answering

After an answer, the bot says whether it was right, removes the options keyboard and sends the `explanation`. After a wrong answer, it shows the correct answers with the mistake marked (see [Marking a mistake](#marking-a-mistake)). In a topic with `show_primary_answer_only`, it shows only the primary answer (see [Course format](course-format.md#several-correct-answers)).

The next step depends on the exercise's recalls (see [Recalls](course-format.md#recalls)). After a wrong answer, a recall starts at once. After a right answer, the learner can choose an optional recall with "Drill". A wrong recall answer gets the mistake marked in the same way, and the learner can try again.

When nothing is left for today, `/wiederholen` and "Next exercise" reply that the day is done. If the learner has a streak, the reply also shows its length (see [Repetition schedule](repetition-schedule.md#streak)). The reply has a "Study more" button. It raises today's limit on new words by 3 (`Tutor.grant_new_word_budget()`, see [Repetition schedule](repetition-schedule.md)) and shows the next exercise. If the learner has answered all available exercises, the limit isn't the reason. In this case the limit stays the same, and the reply says again that the day is done.

### Marking a mistake

After a wrong answer to an exercise or a recall, [`answer_diff.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/answer_diff.py) shows where the answer differs from the correct one (see [#319](https://github.com/pauk-slon/immer-wiederholen/issues/319)). A lesson recall uses the same marks for its correction (see [The states](#the-states)). The module compares the two texts word by word:

- **Similar words.** In a pair of similar words, only the letters that differ are underlined. In declension, one letter carries the case, so the learner must see that letter. Two words are similar if `difflib.SequenceMatcher.ratio()` is more than 0.5.
- **Other words.** A word that has little in common with the learner's word is underlined as a whole. A letter diff of unrelated words would mark letters that match by chance.

| Learner | Correct | Shown |
|---|---|---|
| `an dem` | `an den` | an de<u>n</u> |
| `in dem` | `an den` | <u>an</u> de<u>n</u> |
| `an` | `nach` | <u>nach</u> |
| `gegangt` | `gegangen` | gegang<u>en</u> |
| `Gegangt` | `gegangen` | gegang<u>en</u> |

The comparison ignores what the answer check ignores. The case of letters never counts, so a capital letter from the phone keyboard isn't marked. For a recall, commas anywhere and `.!?` at the start or end of the text don't count either, because `check_recall()` ignores them. In an answer to an exercise, they count, because its check counts them, so an extra period is struck through. A correction in a lesson recall ignores the same characters as a recall, so it doesn't mark a period that the learner left out.

If the exercise shows several answers, the bot marks the answer that is closest to the learner's text, because the learner most likely meant that form.

If the learner only added letters, for example `Kinders` for `Kinder`, the correct answer has nothing to underline. Then the bot shows the learner's answer with the extra letters struck through, and the correct answer after it, for example "Kinder<s>s</s> → Kinder". In all other cases, the bot doesn't show the wrong answer again.

The message is HTML, so `answer_diff.py` escapes the texts. The web widget has no marks, because the markup is specific to Telegram.

## Lessons

The bot gives lessons of 5 exercises (`_LESSON_SIZE`). It gives the size to `Tutor` as `lesson_size`. The web app keeps lessons of one exercise, so it shows no counter and no summary (see [Lessons](repetition-schedule.md#lessons) and [#325](https://github.com/pauk-slon/immer-wiederholen/issues/325)). A day of the streak needs a finished lesson (see [Repetition schedule](repetition-schedule.md#streak)).

In a lesson of several exercises, the learner sees these things:

- **A counter.** The question starts with the position of the exercise in the lesson, for example "3/5".
- **A summary.** The last result of the lesson also shows the number of right answers, and the streak if the lesson added a day. This result is the explanation, or the recall result after a recall. After an optional recall, the explanation and the recall result both have the summary.
- **A "Continue" button.** After the summary, the "Next exercise" button says "Continue" and starts the next lesson. It doesn't show the size of the next lesson. The next lesson can be shorter if less material is left, and if nothing is left, the button leads to the end of the day. A count would promise more than the bot then gives. If nothing is left for today, the reply says that the day is done, as after any other exercise.

A lesson is shorter when fewer exercises are available, for example at the end of the day or with few topics in `/topics`. The counter then shows the real size, for example "1/3". A lesson of one exercise gets no counter and no summary.

## Lesson recall

A lesson recall is a short translation task after a lesson (see [ADR 0031](adr/0031-model-writes-and-checks-a-lesson-recall.md)). [AI-generated content](authoring.md#lesson-recalls) describes the model calls. Every chat gets it if `ANTHROPIC_API_KEY` is set (see [ADR 0033](adr/0033-lesson-recall-for-every-chat-with-a-daily-limit.md)), within a [daily limit](#the-daily-limit). The handlers are in [`commands/lesson_recall.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/commands/lesson_recall.py).

### The start

Only a lesson of 4 or more exercises gets a lesson recall (`_MIN_LESSON_RECALL_SIZE`). A smaller lesson gives too few sentences for the wait of a generation. Small lessons come on the first day, at the end of a day and with few topics in `/topics`. A small lesson works as a lesson without a lesson recall.

The bot takes the size from the counter of the shown exercise ("2/5"). So it decides for the whole lesson at its first exercise. A lesson that gets smaller, for example after `/topics`, gets the optional recall back and no lesson recall.

In a lesson with a lesson recall, the "Continue" button of the lesson summary starts the lesson recall. The summary comes after the last answer, or after the recall result when the last answer needed a recall, so both places have it. The button keeps its text and gets the `LESSON_RECALL` callback instead of `NEXT_EXERCISE`. Such a lesson gets no optional recall after a right answer, because two kinds of recall would confuse the learner. `Tutor` still returns `RecallMode.optional`, and the bot shows the "Next exercise" button instead.

A tap starts the generation. `finished_lesson` has the keys of the exercises of the lesson and of the wrong answers. The bot takes the exercises from the course by these keys. It skips keys that the course no longer has. If the bot can't start a lesson recall, for example from an old button or without keys, the button shows the next exercise. The sentences are in the interface language at the start.

### The daily limit

Each lesson recall costs model calls, so a chat gets 3 lesson recalls in 24 hours (`DAILY_LESSON_RECALLS` in [`lesson_recall_limit.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/lesson_recall_limit.py)). A chat with the `lesson_recall_unlimited` [feature flag](#feature-flags) has no limit.

- **The 24 hours move with time.** The bot counts the lesson recalls that started in the last 24 hours, not in a calendar day. The bot doesn't know the learner's time zone, so a calendar day would end at a random time of the learner's day.
- **Only a generated task counts.** The bot counts a lesson recall after the model wrote the sentences. A failed generation doesn't use up the limit, because the learner got nothing. A task that the chat left during the generation counts, because the call was paid.
- **A lesson after the limit works as a lesson without a lesson recall.** It gets the optional recall back, and "Continue" shows the next exercise. The bot checks the limit at each answer. If the limit ends during a lesson, the rest of the lesson gets no optional recall, and the lesson gets a lesson recall.

The limit is per chat, because the bot keeps it in the FSM data of the chat. `/reset` doesn't change it.

### The states

`LessonRecallState` has three states:

| State | What happens | A message from the learner |
|---|---|---|
| `generating` | the model writes the sentences | gets a busy notice |
| `translating` | the bot shows a sentence with "Skip" | is the translation. A message without text shows the sentence again. A translation that is too long gets a notice and the sentence again |
| `checking` | the model checks the translation | gets a busy notice |

The bot doesn't send a translation of more than 300 characters (`_MAX_ANSWER_LENGTH`) to the model. The bot counts the characters without the spaces at the ends of the text. The longest reference in test runs had 99 characters, so 300 leaves room for a free translation. The limit protects the result, which repeats the corrected translation. A very long translation would make the result longer than a Telegram message can be, and the model's reply could be cut off.

After a wrong translation, the bot shows the correction from the model. The correction keeps what the learner wrote and fixes only the mistakes, so the learner sees how to fix their own sentence. The bot doesn't show the reference too, because the reference and the correction are often the same sentence. If the model gave no correction, or the correction is the same as the answer, the bot shows the reference instead.

The bot marks the changes in the correction in the same way as a mistake in an exercise (see [Marking a mistake](#marking-a-mistake)), so the learner doesn't have to compare the two sentences. There are two exceptions:

- **Removed words.** If the correction only removes words, the bot shows the learner's answer with these words struck through. If the correction also changes other words, the removed words have no mark (see [#381](https://github.com/pauk-slon/immer-wiederholen/issues/381)).
- **A rewritten sentence.** If the correction changes at least three words and more than half of its words, the bot shows it without marks. Marks on most of a sentence don't show where the mistakes are, and the explanation names them. The minimum of three words keeps the marks in a short sentence, where two marks still help.

"Skip" shows the reference. A sentence has no button that leaves the lesson recall, because such a button would look like "Skip". The learner can skip to the end quickly, because "Skip" needs no model call. After the last sentence, the bot clears the exercise state, so the "Next exercise" button on its result starts a new lesson.

To leave a lesson recall early, the learner sends `/wiederholen`. Every button that shows an exercise, for example the button of a reminder, also ends the lesson recall, because it changes the FSM state. Other commands, such as `/progress`, leave the lesson recall as it is.

The result is HTML because of the marks, so the explanation and the reference go through `html.escape()`. `answer_diff.py` escapes the correction itself (see [Showing an exercise](#showing-an-exercise)).

### The data

All keys except `lesson_recall_started_at` are exercise state (see [Chat state](storage.md#chat-state)). The bot removes them at the end of the lesson recall or with the next answer. `lesson_recall_started_at` is lasting chat state, because the daily limit outlives a lesson recall.

| Key | What it holds |
|---|---|
| `lesson_recall_id` | a new id for each start |
| `lesson_recall` | the sentences, the exercises and the language, from `LessonRecall.to_dict()` |
| `lesson_recall_position` | the number of the current sentence |
| `lesson_recall_answer` | the last translation, for "Check again" |
| `lesson_recall_waiting_since` | the start of the current model call |
| `lesson_recall_started_at` | the start times of the lesson recalls of the last 24 hours, for the daily limit |

The handlers don't open `check_out()`, because a lesson recall doesn't change the learning state.

### Late results

After a model call, the handler reads the FSM data again. It continues only if the same `lesson_recall_id` is there, the state is the one that it set before the call, and after a check the sentence is the same. Otherwise a command, a button or a second message moved the chat on during the call, and the bot drops the result. A button tap during a check gets a busy notice.

### Failures

A failed generation shows an error message with "Next exercise". The learner chose "Continue", so the bot lets them go on, with no retry loop. After a failed check, the answer stays in `lesson_recall_answer`, and "Check again" sends it to the model again. The learner can also type a new translation or skip the sentence.

A restart of the bot during a model call loses the call, and the chat stays in `generating` or `checking`. If a message comes more than 60 seconds after the call started, the bot treats the call as lost. 60 seconds is longer than both model timeouts. The bot then shows the same message as after a failed generation or a failed check.

## Chat settings

| Setting | FSM key | Set by | Used by |
|---|---|---|---|
| language | `language` | `/language`, a `/start` deep link in a new chat | every reply, the reminder |
| topic groups | `topic_groups` | `/topics`, a `/start` deep link in a new chat | the choice of what to show, the reminder (see below) |
| reminder interval | `remind_after_hours` | `/reminders` | the reminder (see [The /reminders setting](#the-reminders-setting)) |

The settings are lasting chat state (see [Storage and identity](storage.md#chat-state)). `_LASTING_CHAT_STATE_KEYS` in `commands/wiederholen.py` lists all three settings, the current lesson and the start times of the lesson recalls (see [The daily limit](#the-daily-limit)). When an exercise ends, the bot clears the exercise state but keeps the keys in this tuple. **Add a new setting to this tuple**, or the setting is lost after every exercise. Before the tuple, the code restored a setting by hand after each exercise. One of four call sites missed it, and the setting silently switched off after one exercise. `/reset` doesn't change settings (see [Storage and identity](storage.md#chat-state)).

### Topic selection

`/topics` shows a button per topic group. Each tap selects or deselects a group and saves the selection at once. The bot stores the selection as `topic_groups`, a list of group ids.

[`topic_selection.restrict_to_selected_groups()`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/topic_selection.py) limits the course to the selected groups with `Course.restricted_to()`. The web widget uses the same method. An empty selection means all topics. The function ignores group ids that the course no longer defines. If none of the selected groups exists any more, the learner gets all topics, not none.

The bot applies the selection where it picks something to show. These places are `/wiederholen`, the "next" and "study more" buttons, and the reminder, so no learner gets a reminder about groups that they deselected. The bot intentionally doesn't apply the selection in two places:

- **`/progress`.** It shows the learner's progress in all topics, not only today's focus.
- **Answer checks.** The bot checks an exercise that it already showed against the full course, so a chain into an unselected group still schedules progress there.

The daily limit on new words counts all topics, selected or not.

### Topic groups from a link

The landing site links to the bot from each grammar page, so that the learner continues with the topics of the page (see [#345](https://github.com/pauk-slon/immer-wiederholen/issues/345) and [ADR 0029](adr/0029-start-payload-selects-topic-groups.md)). The payload of the link is the language, then group ids, separated by `-`. For example, `t.me/<bot>?start=ru-verb_government-prepositions` selects two groups.

`/start` applies the payload only to a new chat, as with the language. It saves the groups as `topic_groups`, so `/topics` shows them and the learner can change them. The bot skips a group id that the course doesn't have. If the course has none of the groups, the learner gets a usual start in the language of the link. A payload without a known language at the start gives a usual start.

After groups from a link, the greeting also shows the selected groups and points to `/topics`. Without these lines, a learner could think that the bot has no other exercises.

## Reminders

A separate process, [`python -m wiederholen.bot.reminder`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/reminder.py), sends a message to learners who stopped answering and have something to practice. It is a separate process, not a task inside the bot (see [ADR 0010](adr/0010-reminders-as-a-separate-process.md)). Every 15 minutes it runs `tick()`. `tick()` checks each Telegram chat in `StudentIdentityStore` (`iter_identifiers("telegram")`). For each chat, `_remind_chat()` decides whether to send a reminder and sends it if needed.

For one chat, these steps happen in order:

1. Read the chat's FSM data. Stop if the learner has blocked the bot (see [Blocked chats](#blocked-chats)) or turned reminders off.
2. Limit the course to the selected topic groups.
3. Open the student record with `check_out()` and ask `Tutor.should_remind(remind_after)`.
4. Remove the buttons from the chat's previous message with buttons (see [Pending inline buttons](#pending-inline-buttons)). Send the reminder. If the learner has a streak, the reminder also says how long the streak is and in how many hours it ends. The hours are rounded up, so the last hour shows as 1 hour, not 0. The longest `/reminders` interval is 24 hours. So if the last answer finished a lesson, a streak has at least 12 hours left when the reminder comes. After an answer in an unfinished lesson, the streak can have less time left, because it counts from the last finished lesson.
5. If Telegram accepts the message, call `Tutor.record_reminder_sent()`. Only this step changes the student record, so the record is saved only in this case.

If one chat fails, the reminder logs the error and continues with the next chat.

### When a reminder is due

`Tutor.should_remind(remind_after)` makes the decision, so the rule stays with the rest of the schedule. It returns true for a usual reminder or for a streak reminder. Both need these conditions:

- **The learner has answered at least once.** A learner who pressed `/start` and never answered never gets a reminder.
- **There's something to practice.** A review is due, or new material is available. Here the daily limit on new words doesn't count. A learner at the limit who has overdue reviews should still get a reminder. An earlier version checked only for new material and missed such learners.

A **usual reminder** also needs these conditions:

- **The learner stopped answering.** The last answer to a main exercise was at least `remind_after` ago. Recall answers and other actions don't count.
- **No reminder since the last answer.** The bot sends one usual reminder per period of inactivity.

A **streak reminder** is for a learner with a streak of at least 2 days. It also needs these conditions:

- **The time is right.** It is the hour after the 24-hour mark since the last finished lesson. So the reminder comes at the time of day of the last session and about 12 hours before the streak ends.
- **No recent reminder.** The last reminder came at least 6 hours before that mark, or there was none. So two reminders never come close together.

Usually the streak reminder is a second reminder. It comes after a usual reminder with a short interval (see [ADR 0025](adr/0025-second-reminder-for-a-streak.md)). With the default interval of 24 hours, the usual reminder comes after the mark, so there's no streak reminder. The streak reminder comes first if the learner answered in an unfinished lesson after the last finished lesson. Then the usual reminder counts from that answer and comes later (see [ADR 0027](adr/0027-streaks-count-finished-lessons.md)).

`should_remind()` changes nothing. The reminder calls `record_reminder_sent()` only after Telegram accepted the message, so a failed send never counts as delivered.

### The /reminders setting

`/reminders` offers 4, 8, 12 or 24 hours after the last answer, or off. The default is 24 hours. The bot stores the choice as `remind_after_hours`. The value `0` means off, which is different from "never chosen". "Never chosen" means the default. If the stored value is no longer offered, [`reminder_settings.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/reminder_settings.py) uses the default. The interval counts from the last answer and doesn't follow a fixed schedule (see [ADR 0011](adr/0011-remind-after-the-last-session.md)).

The setting is an interval since the last session, not "every N hours" or "N times a day". It gives at most two reminders per period of inactivity, so reminders don't accumulate overnight. An active learner can get several reminders a day, one after each session. The bot doesn't handle time zones. The learner's phone can mute notifications at night.

### Blocked chats

The Bot API can't tell whether a learner has blocked the bot. Telegram reports it in only two ways. One is a `my_chat_member` update, with status `kicked` in a private chat and `member` again after an unblock. The other is a 403 error (`TelegramForbiddenError`) on the next message.

[`chat_membership.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/chat_membership.py) handles the update. It stores `bot_blocked: True` in the chat's FSM data and removes it after an unblock. aiogram subscribes to `my_chat_member` updates automatically when a handler for them exists. The reminder skips chats with the flag before it opens the student record or calls Telegram. A 403 on send also sets the flag. This covers learners who blocked the bot before this handler existed, and learners whose update was lost.

The flag isn't in `_LASTING_CHAT_STATE_KEYS`, so the end of an exercise would remove it. But a learner who has blocked the bot doesn't answer exercises. If the flag is lost anyway, the worst case is one refused message, and that message sets the flag again.

## Pending inline buttons

A tap on an inline button ("Next exercise", "Drill", "Study more" and others) removes that button, because the callback handler edits its own message. A typed command doesn't remove buttons, because Telegram never tells the bot which earlier message a command replaces. Without extra work, old buttons would stay on their messages forever.

[`pending_buttons.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/pending_buttons.py) tracks one message id per chat in FSM data, `last_buttoned_message_id`. A chat has at most one active set of buttons at a time. The module has three functions:

- **`remember_buttoned_message(state, message)`.** Call it right after you send a message with an inline keyboard.
- **`forget_buttoned_message(state)`.** Call it when a callback handler removed its own buttons and attached no new ones.
- **`clear_stale_buttons(bot, chat_id, state)`.** It removes the buttons from the remembered message, if there is one, and forgets the message. It ignores a `TelegramBadRequest`, which means that the message was already edited, deleted or is too old.

Every command that the learner types calls `clear_stale_buttons()` first. These commands are `/start`, `/wiederholen`, `/progress`, `/topics`, `/reminders`, `/language` and `/reset`. The reminder calls it right before it sends a message. `clear_stale_buttons()` takes a bot and a chat id, not a `Message`, because the reminder has no incoming message.

When you edit the text of a message, pass `reply_markup=` explicitly, with a new keyboard or `None`. If you edit only the text, the message keeps its old keyboard.

## Feature flags

[`feature_flags.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/feature_flags.py) changes a feature for specific chats, based on the `BOT_FEATURE_FLAGS` variable. [Configuration](configuration.md#lesson-recalls) describes its format.

At startup, `bootstrap.load_feature_flags()` parses the variable once into a `dict[str, frozenset[int]]`. `main()` passes it to `start_polling()` as `feature_flags`, so every handler that declares a `feature_flags` parameter gets it. A handler checks a chat with `has_feature(feature_flags or {}, LESSON_RECALL_UNLIMITED_FLAG, chat_id)`. The one flag is `lesson_recall_unlimited`, which removes the [daily limit](#the-daily-limit) of the lesson recall. `check_lesson_recall_config()` checks at startup what it needs (see [Configuration](configuration.md#lesson-recalls)). The parameter defaults to `None`, so tests that don't need flags don't have to pass it.

The flags have no storage and no admin command. To change a flag, edit the variable and restart the bot. This is enough for a few chats, such as the author's and test chats. The flags stay in the bot layer, and `wiederholen.school` never sees a chat id or a flag name.

## Hints from grammar classes

[Course format](course-format.md#hints-from-grammar-classes) describes what the learner sees and how to tag exercises. `Tutor.get_hint(exercise)` chooses the hint:

1. Collect the other words of the same topic whose `grammar_classes` overlap with this exercise's classes.
2. Keep the words that the learner knows well. Such a word has a repetition interval above one day, so the learner has answered it correctly at least once after its first answer. An interval of `0` can mean "answered wrong" or "answered once", and `1` is one success, so neither counts.
3. Return the word with the longest interval, because the learner remembers it best. Choose at random among words with the same interval. Return `None` if no word qualifies.

`get_hint()` returns only the word. The bot renders it with `Locale.grammar_class_hint`. The hint intentionally doesn't include the other word's answer. For a class like `an+Akk`, that answer would also be the answer to this question. `get_hint()` only reads the record.

The web widget doesn't show these hints yet.

## Testing

Handler tests send updates through the real dispatcher, with a real Redis for FSM data and student records (see [Storage and identity](storage.md#testing)). They use fixtures from [`tests/plugins/aiogram.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/tests/plugins/aiogram.py) (`feed_message`, `feed_callback_query`) to send raw updates to the dispatcher. The tests mock the Telegram calls. `send_message` returns a synthetic `Message` with a `message_id` that starts at 1000 and increases, so tests of button tracking can check which message the bot remembered. Every other method returns `True`.

The reminder's tests call `tick()` directly, with no incoming update, so [`tests/bot/test_reminder.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/tests/bot/test_reminder.py) mocks Telegram in the same way by itself.

## Decisions

- [Reminders run as a separate process](adr/0010-reminders-as-a-separate-process.md) (ADR 0010)
- [Reminders count from the last session](adr/0011-remind-after-the-last-session.md) (ADR 0011)
- [A streak of 2 days or more gets a second reminder](adr/0025-second-reminder-for-a-streak.md) (ADR 0025)
- [Streaks count finished lessons, not answers](adr/0027-streaks-count-finished-lessons.md) (ADR 0027)
