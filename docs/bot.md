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

`fallback` has no command either. It replies to a message that no other handler takes (see [Other messages](#other-messages)).

[`l10n.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/l10n.py) has the bot's texts in both languages.

### Other messages

A message without a reply makes the bot look broken, for example to a new learner who writes right after `/start`. So the router of `fallback` comes last and takes a message that no other handler takes, if it is text, a sticker, a photo, a video, a voice message, an audio file or a document. This includes text outside an exercise and an unknown command such as `/help`. During an exercise, this includes such messages that aren't an answer (see [What counts as an answer](#what-counts-as-an-answer)). During a recall, the bot shows the recall again instead. During a lesson recall, every message except a command goes to its handlers. Service messages, for example about a pinned message, get no reply, because the learner didn't write anything.

The bot replies with what it does and the "next" button. The reply is the same in every state, because the "next" button shows what fits the state: an exercise, or the message that nothing is due today. The bot doesn't start an exercise on such a message, because the learner may have asked a question. The handler removes the buttons of the earlier message like every typed command does.

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

After an answer, the bot sends one message with the result. The message starts with a mark for a right or a wrong answer. After a wrong answer, the correct answers with the mistake marked follow (see [Marking a mistake](#marking-a-mistake)). In a topic with `show_primary_answer_only`, the bot shows only the primary answer (see [Course format](course-format.md#several-correct-answers)). Then the message has the `explanation` and the buttons. The message is HTML, so the explanation goes through `html.escape()`. One message, not a verdict and then an explanation, because two messages for one answer are noise, and each one can make a notification.

The two marks differ in shape, not only in color, because no word says the verdict. A learner who doesn't see colors must still tell them apart.

The next step depends on the exercise's recalls (see [Recalls](course-format.md#recalls)). After a wrong answer to a pair that the learner answered before, a recall starts at once. After a right answer, or a wrong first answer to a pair, the learner can choose an optional recall with "Drill" ([ADR 0034](adr/0034-no-required-recall-on-a-new-pair.md)). A wrong recall answer gets the mistake marked in the same way, and the learner can try again.

A recall that the learner asked for, with "Drill" or "Try again", has a "Skip" button. The learner can't see the sentence before the tap, so they must be able to change their mind. Only the first attempt of a required recall has no "Skip". "Skip" works as the "next" button after a wrong recall answer. It shows the next exercise. `recall_is_skippable` in the FSM data keeps the choice, so the bot can show the recall again with the same button.

When nothing is left for today, `/wiederholen` and "Next exercise" reply that the day is done. If the learner has a streak, the reply also shows its length (see [Repetition schedule](repetition-schedule.md#streak)). The reply has a "Study more" button. It raises today's limit on new words by 3 (`Tutor.grant_new_word_budget()`, see [Repetition schedule](repetition-schedule.md)) and shows the next exercise. If the learner has answered all available exercises, the limit isn't the reason. In this case the limit stays the same, and the reply says again that the day is done.

### Removing the options keyboard

After an answer to a multiple-choice exercise, the bot must remove the options keyboard. Only a new message can remove a reply keyboard, and such a message can't have inline buttons, not even after an edit. So `_remove_reply_keyboard()` first sends a short message with `ReplyKeyboardRemove` and without a notification. Then it deletes this message at once. The keyboard stays removed, and the result comes as one message with its buttons.

If the Bot API refuses the deletion or the call fails, for example because of a flood limit or a network error, the bot logs a warning and continues. At this point the answer is already recorded, so the learner must get the result. The only cost is one extra short message in the chat. A test in a real chat showed that the keyboard stays removed after the deletion, on a phone and on a desktop client.

The bot doesn't use other ways ([#393](https://github.com/pauk-slon/immer-wiederholen/pull/393)):

- **Add the buttons to the message that removed the keyboard.** `editMessageReplyMarkup` refuses it with "message can't be edited".
- **Don't remove the keyboard.** `one_time_keyboard` hides the keyboard after a tap, but not after a typed answer, so the keyboard stays open under the explanation. A hidden keyboard can also be opened again, and a tap on an old option during an optional recall would count as an answer.
- **Show the options as inline buttons.** Then there is no keyboard to remove. But the answer would come from a callback instead of a message of the learner, which is a larger change of the conversation (see [#320](https://github.com/pauk-slon/immer-wiederholen/issues/320)).

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

### What counts as an answer

An answer to an exercise or a recall is text that doesn't start with `/`. A sticker, a photo or an unknown command such as `/help` isn't an answer, because the learner didn't try to answer. As a wrong answer, it would set the interval of the pair to 0. During an exercise, such a message goes to the [fallback](#other-messages), and its "next" button shows the same exercise again.

During a recall, the bot shows the recall again and doesn't use the fallback. The fallback's button shows the next exercise, so it would skip the recall, and after the last answer of a lesson also the lesson recall that comes after it. To leave a recall on purpose, the learner taps "Skip" if the recall has it, or sends `/wiederholen`.

## Lessons

The bot gives lessons of 5 exercises (`_LESSON_SIZE`). It gives the size to `Tutor` as `lesson_size`. The web app keeps lessons of one exercise, so it shows no counter and no summary (see [Lessons](repetition-schedule.md#lessons) and [#325](https://github.com/pauk-slon/immer-wiederholen/issues/325)). A day of the streak needs a finished lesson (see [Repetition schedule](repetition-schedule.md#streak)).

In a lesson of several exercises, the learner sees these things:

- **A counter.** The question starts with the position of the exercise in the lesson, for example "3/5".
- **A summary.** The summary shows the number of right answers, and the streak if the lesson added a day. It is a message of its own, right after the result of the last answer, so it isn't lost at the end of a long explanation. The buttons of the result move to the summary. If a recall or a lesson recall follows the last answer, the summary has no buttons, and the recall result doesn't repeat it. So the learner sees the summary once.
- **A next lesson button.** On the summary, the "Next exercise" button names the next lesson. It doesn't show the size of the next lesson. The next lesson can be shorter if less material is left, and if nothing is left, the button leads to the end of the day. A count would promise more than the bot then gives. If nothing is left for today, the reply says that the day is done, as after any other exercise.

A lesson is shorter when fewer exercises are available, for example at the end of the day or with few topics in `/topics`. The counter then shows the real size, for example "1/3". A lesson of one exercise gets no counter and no summary.

## Lesson recall

A lesson recall is a short translation task after a lesson (see [ADR 0031](adr/0031-model-writes-and-checks-a-lesson-recall.md)). [AI-generated content](authoring.md#lesson-recalls) describes the model calls. Every chat gets it if `ANTHROPIC_API_KEY` is set (see [ADR 0033](adr/0033-lesson-recall-for-every-chat-with-a-daily-limit.md)), within a [daily limit](#the-daily-limit). The handlers are in [`commands/lesson_recall.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/commands/lesson_recall.py).

### The start

Only a lesson of 3 or more exercises gets a lesson recall (`_MIN_LESSON_RECALL_SIZE`). A lesson of 2 gives one or two short sentences, which aren't worth the wait of a generation. 3 exercises are enough for the one to three sentences that a guide usually asks for. A course whose guide wants more sentences needs a larger minimum. Small lessons come on the first day, at the end of a day and with few topics in `/topics`. A small lesson works as a lesson without a lesson recall.

The bot takes the size from the counter of the shown exercise ("2/5"). So it decides for the whole lesson at its first exercise. A lesson that gets smaller, for example after `/topics`, gets the recalls after answers back and no lesson recall.

The lesson recall is a part of the lesson, not a choice. The interface calls it "practice" (see the list of words in `l10n.py`). Such a lesson gets no recall after an answer, neither optional nor required. The lesson recall practices the mistakes of the lesson, and a wrong answer makes the pair due again today anyway. The bot ignores the `RecallMode` that `Tutor` returns and shows the "Next exercise" button.

The lesson recall is required, because a learner who declined it lost the practice of the lesson's mistakes, and few learners chose it. An optional lesson recall had two problems, and a required one avoids them. The task could come as a surprise, so the summary of the lesson now comes first. The learner couldn't get out, so the task is one to three sentences, "Skip" needs no model call, and `/wiederholen` leaves the lesson recall at once. Earlier, the learner chose it with a button of its own ([#397](https://github.com/pauk-slon/immer-wiederholen/pull/397)). A setting for this in `bot.yaml` can come with a second course that wants another method.

After the last answer, the bot sends the result and the lesson summary without buttons, as before a required recall. Then it starts the generation at once. The bot sends no message before the first sentence. The summary separates the lesson recall from the lesson, and the "typing" status shows the wait. The sentences are in the interface language at the start.

`handle_answer()` starts the generation after `check_out()`, because the model call takes seconds. `commands.lesson_recall` imports `commands.wiederholen`, so the dispatcher gives `start_lesson_recall()` to `handle_answer()` as a parameter. `finished_lesson` has the keys of the exercises of the lesson and of the wrong answers. The bot takes the exercises from the course by these keys. It skips keys that the course no longer has. If no key is left, the bot shows the message of a failed generation.

A practice button from before this change still works. It starts the lesson recall if the chat still gets one, and otherwise shows the next exercise, because the learner wants to go on.

### The daily limit

Each lesson recall costs model calls, so a chat gets 3 lesson recalls in 24 hours (`DAILY_LESSON_RECALLS` in [`lesson_recall_limit.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/lesson_recall_limit.py)). A chat with the `lesson_recall_unlimited` [feature flag](#feature-flags) has no limit.

- **The 24 hours move with time.** The bot counts the lesson recalls that started in the last 24 hours, not in a calendar day. The bot doesn't know the learner's time zone, so a calendar day would end at a random time of the learner's day.
- **Only a generated task counts.** The bot counts a lesson recall after the model wrote the sentences. A failed generation doesn't use up the limit, because the learner got nothing. A task that the chat left during the generation counts, because the call was paid.
- **A lesson after the limit works as a lesson without a lesson recall.** It gets the recalls after answers back, and no lesson recall starts. The bot checks the limit at each answer. If the limit ends during a lesson, the rest of the lesson gets no recall after an answer, and the lesson gets a lesson recall.
- **The summary says when the next lesson recall is available.** Without this line, the lesson recall wouldn't come, and the learner wouldn't know why. The time is when the last 24 hours have fewer than 3 lesson recalls. Usually the oldest lesson recall stops counting then. But a chat can have more than 3 in 24 hours, for example if it had the unlimited flag before. The time is in minutes under two hours and in hours otherwise. It is rounded up, so the learner never comes too early. Every such summary has the line, not only the first one. The learner can come back hours later, and the time changes.

The limit is per chat, because the bot keeps it in the FSM data of the chat. `/reset` doesn't change it.

### The states

`LessonRecallState` has four states:

| State | What happens | A message from the learner |
|---|---|---|
| `generating` | the model writes the sentences | gets a busy notice |
| `translating` | the bot shows a sentence with "Skip" | is the translation. A message without text shows the sentence again. A translation that is too long gets a notice and the sentence again |
| `checking` | the model checks the translation | gets a busy notice |
| `reading` | a result with an explanation or a correction waits for a tap | gets the next sentence. The learner hasn't seen it, so the message isn't its translation |

The bot doesn't send a translation of more than 300 characters (`_MAX_ANSWER_LENGTH`) to the model. The bot counts the characters without the spaces at the ends of the text. The longest reference in test runs had 99 characters, so 300 leaves room for a free translation. The limit protects the result, which repeats the corrected translation. A very long translation would make the result longer than a Telegram message can be, and the model's reply could be cut off.

The result starts with the same marks as the result of an exercise. If the result has only the mark of a right translation, the bot shows the next sentence at once. If the result has an explanation or a correction, the next sentence comes only after a tap on the result. Without the pause, the next sentence would push the text out of view before the learner reads it. The rule depends on the text, not on the verdict, because the model can also explain a right translation.

After a wrong translation, the bot shows the correction from the model. The correction keeps what the learner wrote and fixes only the mistakes, so the learner sees how to fix their own sentence. The bot doesn't show the reference too, because the reference and the correction are often the same sentence. If the model gave no correction, or the correction is the same as the answer, the bot shows the reference instead.

The bot marks the changes in the correction in the same way as a mistake in an exercise (see [Marking a mistake](#marking-a-mistake)), so the learner doesn't have to compare the two sentences. There are two exceptions:

- **Removed words.** If the correction only removes words, the bot shows the learner's answer with these words struck through. If the correction also changes other words, the removed words have no mark (see [#381](https://github.com/pauk-slon/immer-wiederholen/issues/381)).
- **A rewritten sentence.** If the correction changes at least three words and more than half of its words, the bot shows it without marks. Marks on most of a sentence don't show where the mistakes are, and the explanation names them. The minimum of three words keeps the marks in a short sentence, where two marks still help.

"Skip" shows the reference and then the next sentence at once. A sentence has no button that leaves the lesson recall, because such a button would look like "Skip". The learner can skip to the end quickly, because "Skip" needs no model call. After the last sentence, the bot sends a summary with the number of right translations. Its text differs from the summary of a lesson, so the learner can tell the two apart. A skipped sentence counts as not right. Then the bot clears the exercise state, so the button on the summary starts a new lesson. The button has the same text as the button that starts a new lesson after the summary of a lesson, because it does the same thing.

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
| `lesson_recall_correct` | the number of right translations, for the summary |
| `lesson_recall_waiting_since` | the start of the current model call |
| `lesson_recall_started_at` | the start times of the lesson recalls of the last 24 hours, for the daily limit |

The handlers don't open `check_out()`, because a lesson recall doesn't change the learning state.

### Late results

After a model call, the handler reads the FSM data again. It continues only if the same `lesson_recall_id` is there, the state is the one that it set before the call, and after a check the sentence is the same. Otherwise a command, a button or a second message moved the chat on during the call, and the bot drops the result. A button tap during a check gets a busy notice.

### Failures

A failed generation shows an error message with "Next exercise". The learner can't get the lesson recall now, so the bot lets them go on, with no retry loop. The lesson had no recall after its answers, so after a failed generation the learner doesn't practice the lesson's mistakes at once. The pairs with a wrong answer are still due again today, and failures are rare, so the bot doesn't offer a recall instead. After a failed check, the answer stays in `lesson_recall_answer`, and "Check again" sends it to the model again. The learner can also type a new translation or skip the sentence.

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

## Button styles

An inline button can have a `style`: `primary`, `success` or `danger`. The style marks the role of the button, and the Telegram app decides how it looks. A button gets a style only if it has that role, so most buttons have none. If every button had a style, a style would say nothing. Older Telegram apps ignore the field. Use the constants of [`button_styles.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/bot/button_styles.py).

- **`RECOMMENDED`** marks the step that we recommend, only where the learner has a choice. A message has at most one such button. A single button gets no style. The button that ends a selection, such as "Done" in `/topics`, is the recommended step. So is "Check again" after a failed check of a translation in a lesson recall. The buttons of the selection itself have no style. An optional step, such as "Drill" or "Try again" of a recall, is never the recommended step. The bot asks for a recall once and then recommends to go on, so that it isn't too pushy. A learner who wants to repeat can.
- **`DESTRUCTIVE`** marks an action that can't be undone. In a confirmation, the button that cancels comes first, and the `DESTRUCTIVE` button comes after it. So a learner who taps the first button out of habit doesn't do the action.
- **`success`** would mark an action that confirms a good result. No button has this role now.

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
