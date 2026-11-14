# Repetition schedule

This page describes how `wiederholen.school.tutoring` decides what a learner practices and when. It covers the schedule, the growth of intervals, the choice of the next exercise, lessons, the daily limit on new words, the scheduling of linked topics, the numbers of `/progress` and the streak. [Course format](course-format.md#linking-topics) describes how to declare links in `topics.yaml`.

The repetition engine consists of three classes in [`tutoring/`](https://github.com/pauk-slon/immer-wiederholen/tree/main/wiederholen/school/tutoring):

- **`Tutor`** (`session.py`) makes the decisions with `next_exercise()`, `check_answer()`, `request_recall()`, `check_recall()`, `should_remind()`, `progress()`, `streak()` and `get_hint()`. The frontend creates it for each request as `Tutor(course, student_record, lesson=lesson)`.
- **`StudentRecord`** (`student_record.py`) reads and writes the learner's record. The record is a plain dict that the frontend loaded from storage (see [Storage and identity](storage.md#student-records)). `StudentRecord` knows nothing about the course.
- **`Lesson`** (`lesson.py`) reads and writes the learner's current lesson. The lesson is also a plain dict, but it is the frontend's conversation state, not part of the record (see [Lessons](#lessons)).

`SelectablePairs` (`selection.py`) chooses the word and the topic for `next_exercise()`. [Conventions](#conventions) lists the rules for changes to these classes.

## The schedule

**Days are UTC days.** "Today", "due today", the daily limit and `/progress` all change at midnight UTC. For a learner in UTC+9, this is 9 in the morning.

The schedule is per **pair** of word and topic. For example, `singen` in `partizip_ii` and `singen` in `partizip_ii_meaning` have separate schedules. Several exercises of one pair share the entry of the pair.

```json
{
  "word_schedule": {
    "singen": {
      "partizip_ii": {"repetition_interval": 4, "due_date": "2026-10-28", "introduced_at": "2026-10-20"}
    }
  }
}
```

| Field | Meaning |
|---|---|
| `repetition_interval` | the number of days until the pair is due again after a correct answer. It grows with each correct answer |
| `due_date` | the day when the pair is due next |
| `introduced_at` | the day of the first answer to the pair. The field is absent until then. It is set once and never changes |

A pair can have an entry without `introduced_at`. This happens when a link schedules a topic for a word before the learner has seen it (see [Linked topics](#linked-topics)).

The record also has these keys:

| Key | Meaning |
|---|---|
| `last_exercise` | the last answered exercise, with its question, word, topic, time and the recall shown for it. `Tutor` uses it to avoid repeats and to decide on reminders |
| `today_answers` | today's count of answers and correct answers |
| `new_word_budget` | the extra new words that "Study more" added today |
| `last_reminded_at` | the time of the last reminder |
| `last_lesson_finished_at` | the time of the last finished lesson (see [Streak](#streak)) |
| `streak` | the number of days in the current streak and the time of the finished lesson that added the last day (see [Streak](#streak)) |

`today_answers` and `new_word_budget` store their date, and their count is valid only on that day, so no cleanup is needed the next morning.

## Intervals

After each answer to a main exercise, `check_answer()` sets the new interval of the pair:

- **Correct answer.** The interval doubles, with a minimum of 1 and a maximum of 60 days (`MAX_REPETITION_INTERVAL_DAYS`).
- **Wrong answer.** The interval goes back to 0.
- **First answer, right or wrong.** The interval is 0.

A pair with only correct answers goes `0 → 1 → 2 → 4 → 8 → …`. A wrong answer at any point starts the pair again from 0.

The pair is due again on these days:

- **After a first answer or a wrong answer.** The pair is due today. Otherwise a new learner, or a learner right after `/reset`, would have no material left partway through the first day, because every correct first answer would move its pair to tomorrow.
- **After other answers.** The pair is due in `repetition_interval` days.

Lateness doesn't matter. If the learner answers a pair correctly days after it was due, the interval doubles from its recorded value, as if the answer was on time.

The first answer sets 0, not 1, so the next correct answer is the one that reaches 1. This way the engine doubles an interval only if the learner was actually tested at it. A start at 1 would move pairs two days ahead after their first day and leave the next day with nothing due.

## Picking the next exercise

`next_exercise()` picks a **word**, then one of its **topics**, then one of the exercises of that pair at random. The word comes first for two reasons. A pair with many exercises doesn't appear more often than a pair with one exercise. A word with several due topics doesn't push out other words.

### What can be picked

A pair is a candidate in two cases:

- **Due.** The pair has an entry with a `due_date` of today or earlier.
- **New and available.** The pair has no entry yet, and its topic isn't gated (see [Linked topics](#linked-topics)).

The words of the candidates fall into three tiers:

| Tier | Words | New-word limit |
|---|---|---|
| **free** | introduced through any topic | not counted |
| **queued** | not introduced, but with an entry from a link | counted, taken first |
| **fresh** | without any entry | counted, fill the rest |

A word is free after the learner answers any of its topics. For example, if the learner is learning `warten` in one topic, the untouched other topics of `warten` appear without using the new-word limit. The same is true for a topic of such a word that a link just unlocked.

`SelectablePairs.select_word()` takes as many queued words as today's remaining limit allows. It fills the rest with a random sample of fresh words. Then it picks with equal chance among the free words and the taken words. The sample of fresh words is limited *before* the pick, so a course with hundreds of untouched words doesn't lower the chance of a few due words.

`select_topic()` then prefers a topic of the chosen word that is **due for review**, which means that the learner answered it before and it is due today. If there is no such topic, it picks among the new topics of the word. These include linked topics that are scheduled for today but not answered yet. A review has a deadline, and new material doesn't.

### Lessons

`Tutor` gives exercises in lessons. A lesson is a short group of exercises that `Tutor` chooses together from the schedule. The learner answers them one after another. A new lesson starts only when the current lesson has no exercises left. `LESSON_SIZE` sets the number of exercises, and the frontend can give another size as `lesson_size`. For now, the size is 1. Only bot chats with the `lessons` flag get lessons of 5 exercises (see [Telegram bot](bot.md#lessons) and [#325](https://github.com/pauk-slon/immer-wiederholen/issues/325)).

`next_exercise()` takes the next exercise from the lesson. If the lesson has no exercises left, or if it started on an earlier day, `next_exercise()` starts a new lesson first:

- It repeats the pick of one exercise that [Picking the next exercise](#picking-the-next-exercise) describes. Each chosen exercise counts as the last answer for the next pick, so the [exclusions](#avoiding-repeats) space the exercises of one word.
- A pair is taken at most once.
- A new word uses today's limit as soon as it is taken, so a lesson never has more new words than the limit allows.
- The lesson can be shorter than the size, if less material is available. If nothing is available, there's no lesson, and `next_exercise()` returns `None`.

A lesson stores `Exercise.content_key` values, a SHA-256 hash of all fields of each exercise. `next_exercise()` skips a key that the course doesn't have. Such an exercise was edited or removed, or the learner no longer selects its topic. `next_exercise()` removes all such keys before it takes the next one, and the lesson size becomes smaller by their number. So the size counts only the exercises that the learner gets, and "3/5" and the summary stay correct. A lesson gives exercises only on the day when it started. Its pairs that the learner didn't answer come back as due reviews.

The answer to the last exercise of a lesson finishes it, also if the lesson started on an earlier day. `check_answer()` reports this once per lesson. Then its `Mark` has `finished_lesson`, with the size of the lesson, the number of correct answers and whether the lesson added a day to the [streak](#streak). Every finished lesson counts for the streak. `lesson_progress()` returns the position of the exercise that `next_exercise()` gave last, and the size of its lesson. The bot shows them as "3/5". A lesson isn't part of the student record. Each frontend keeps its own lesson next to the exercise that it shows (see [Storage and identity](storage.md#chat-state) and [ADR 0026](adr/0026-lessons-in-conversation-state.md)).

```json
{"date": "2026-11-14", "size": 5, "exercise_keys": ["3f9a…", "b21c…"], "correct": 2}
```

| Field | Meaning |
|---|---|
| `date` | the day when the lesson started |
| `size` | the number of exercises in the lesson |
| `exercise_keys` | the keys of the exercises that the lesson hasn't given yet |
| `correct` | the number of correct answers in the lesson. It is absent before the first one |
| `finished` | `true` after the answer to the last exercise. It is absent before |

### The daily limit on new words

A learner gets at most 7 new **words** a day (`NEW_WORDS_PER_DAY`). In the code, today's remaining limit is the `budget` that `select_word()` gets. A "Study more" grant is `NEW_WORD_BUDGET_GRANT`. When the limit is used up, `Tutor` emits the `daily_cap_reached` event.

**Reviews have no limit.** A learner who comes back after a week gets all overdue reviews at once. Only new words are limited.

The limit counts words, not pairs. If the learner starts `sprechen` in two topics on one day, this is one new word.

A word counts as new today if it has at least one introduced topic and all its introduced topics were introduced today. A word that the learner started days ago doesn't count, even if another of its topics gets its first answer today. A word with only a queued entry and no answer doesn't count either. Without the first condition, such a word would count, because "all its introduced dates are today" is true for an empty set.

When the limit is the only reason that no more material is shown, the bot's "Study more" button calls `Tutor.grant_new_word_budget()`. This adds 3 words to today's limit (`NEW_WORD_BUDGET_GRANT`). Grants add up, because a learner who taps the button again explicitly wants more. A tap does nothing if the limit isn't reached. Telegram keeps old buttons active, and a tap on yesterday's button shouldn't raise today's limit. `/reset` doesn't change today's grants, because they expire the next day.

### Avoiding repeats

After a first answer, a pair is due again the same day. Without extra rules, the same word could come back at once. `next_exercise()` uses three exclusions:

1. The word of the last answer isn't picked.
2. If the same word is picked anyway, its last topic isn't picked.
3. Among the exercises of the pair, the last question isn't picked.

It drops an exclusion if the exclusion would leave nothing to pick.

### When there's nothing to show

`next_exercise()` returns `None` in two cases. It reports each case as a `NoExerciseAvailable` span event (see [Observability](tracing.md#events-from-the-repetition-engine)):

- **`nothing_available`.** Nothing is due, and nothing new is available. The learner has answered all exercises, or the rest are locked behind gates.
- **`daily_cap_reached`.** Only new words are left, and the limit is used up.

In both cases the bot says that the day is done and shows "Study more".

## Linked topics

After every answer, right or wrong, `check_answer()` calls `_expedite_chained_topics()`. It finds these pairs:

- For each topic in `chains` and `gates` of the answered topic, the pair *(same word, that topic)*.
- For each topic in `chains_by_answer`, the pair *(the exercise's primary answer, that topic)*. The other answers don't take part in links.

`_expedite_dependent()` gives such a pair an entry that is due today, with interval 0. It does this only if the pair has no entry yet and the course has an exercise for it. A pair that already has an entry keeps it. After a linked topic has its own schedule, a link doesn't change it. Otherwise topics that link to each other would reset each other's due dates forever (see [ADR 0004](adr/0004-links-only-schedule-unstarted-pairs.md)). `Tutor` reports each scheduled pair as a `TopicUnlocked` event.

The pairs of a gated topic without an entry aren't "new and available", so they can't be picked until a link gives them an entry. After that, they are due like any other pair. Locked pairs don't change `/progress`, because they have no entry to count.

`Course` merges `chains` and `gates` into `word_chained_topics`. It keeps `chains_by_answer` as `answer_chained_topics`. Gates are not derived from chains (see [ADR 0012](adr/0012-gates-declared-explicitly.md)). A `gates` entry under another topic can still gate an answer-chained topic. Gating looks only at the topic, not at how its pair was scheduled.

### Restricted courses

`Course.restricted_to(topics)` limits the exercises to some topics, such as the `topics` of the web widget or the bot's `/topics` selection. It keeps the links as they are. A link into an excluded topic finds no exercise and does nothing. The same record works with any restriction, and the progress in an excluded topic stays as it was.

## Recalls

`request_recall(exercise)` picks one of the exercise's recalls at random. It avoids the recall that the learner saw last for this exercise and stores the chosen recall in `last_exercise`. The next answer replaces `last_exercise`, so nothing needs a reset between exercises.

An **optional** recall, after a correct answer, halves the interval of the pair, with a minimum of 1. This happens only the first time that the learner asks for a recall after that answer, and the due date changes to match. A required recall after a wrong answer changes nothing, because the interval is already 0.

`check_recall()` only compares the answer. Recall answers don't change the schedule and don't count as activity for reminders.

## Progress

`progress()` reports six numbers for `/progress` and changes nothing:

| Number | Meaning |
|---|---|
| `remaining_today` | pairs due today, which are reviews and linked topics scheduled for today |
| `new_today` | words started today, counted the same way as for the daily limit |
| `answered_today`, `correct_today` | today's answers to main exercises and the number of right ones. These count attempts, not pairs |
| `learning` | words with any schedule entry that aren't mastered yet |
| `mastered` | words with all topics at the 60-day interval |

`learning` and `mastered` count words, not pairs, because a learner thinks "I'm learning `sprechen`", not about its topics separately. A word is mastered only when all its topics are mastered. If the learner knows a verb's Partizip II well but has barely started its preposition, the verb isn't mastered.

`remaining_today` counts only pairs that are actually due, not new material. The number of new pairs in a day can't be known in advance, because one new word can lead to more pairs through links. For the same reason, `/progress` shows no total of untouched pairs. Such a total would be misleading, because most of those pairs won't be due for weeks.

## Streak

The streak is the number of days that a learner practices without a break. `Tutor.streak()` returns it as a `Streak` with `days` and `breaks_at`, or `None` if there's no streak now. It changes nothing.

- **Practice.** A finished [lesson](#lessons) counts. Its answers can be right or wrong. A lesson that is shorter than the lesson size also counts. An answer that doesn't finish a lesson changes nothing. Recall answers don't count. For now, a lesson has one exercise, so every answer finishes a lesson.
- **Break.** The streak breaks when more than 36 hours (`STREAK_BREAKS_AFTER`) pass without a finished lesson. `breaks_at` is the time of the last finished lesson (`last_lesson_finished_at`) plus 36 hours. After that time, `streak()` returns `None`, and the next finished lesson starts a new streak of 1 day.
- **Days.** The record stores the number of days and the time of the finished lesson that added the last day (`counted_at`). A lesson adds a day if it is finished at least 18 hours (`STREAK_DAY_AFTER`) after `counted_at`. Then its time becomes the new `counted_at`. Other lessons change nothing.

The bot doesn't know the learner's time zone, so it can't count calendar days (see [ADR 0021](adr/0021-streaks-from-intervals-between-answers.md) and [ADR 0027](adr/0027-streaks-count-finished-lessons.md)). In the table, a session is a finished lesson. The 18 hours give these results:

| Practice | Result |
|---|---|
| every day at about the same time | 1 day a day |
| twice a day, for example 8:00 and 20:00 | 1 day a day, because 20:00 is only 12 hours after 8:00 |
| every day a little earlier, for example 9:00, 8:00, 7:00 | 1 day a day, while the time moves by less than 6 hours a day |
| a switch from evenings to mornings, for example 20:00, then 9:00 every day | 1 day less, because 9:00 is only 13 hours after 20:00. The day isn't added later |
| two sessions on one day at least 18 hours apart, for example 5:00 and 23:30 | 1 day too many |
| a session every 35 hours | the streak continues, although some calendar days have no practice. This works like a built-in streak freeze |
| 0:30, then 23:30 on the next day | the streak breaks, because the sessions are 47 hours apart |

`check_answer()` reads the time of the previous finished lesson before `record_mark()` replaces `last_exercise`. For a record without `last_lesson_finished_at`, this time comes from `last_exercise`, so `check_answer()` reads it first. When the answer finishes a lesson, `check_answer()` stores its time in `last_lesson_finished_at` and updates the streak.

A record from before [ADR 0027](adr/0027-streaks-count-finished-lessons.md) has no `last_lesson_finished_at`. `Tutor` then uses the time of the last answer from `last_exercise`. Before ADR 0027, every answer was practice, so this is the same time.

A record from before streaks has `last_exercise` but no `streak`. It has no streak until the next finished lesson, and `Tutor` reports no break for it.

The bot shows the streak in `/progress`, when the day is done and in the reminder (see [Telegram bot](bot.md)). Without a streak, these messages have no streak line. The web widget doesn't show the streak yet, but its answers count too, because the streak is in the student record.

`Tutor` reports `StreakExtended` when a finished lesson adds a day, with `days` 1 for a new streak. The first finished lesson after a break also reports `StreakBroken` with the length of the lost streak (see [Observability](tracing.md#events-from-the-repetition-engine)).

## Resetting

`/reset` calls `StudentRecord.reset_progress(student_record)`. It deletes the schedule and today's answer counts. Without the reset of the counts, `/progress` would still show today's answers right after a reset.

It keeps the rest of the record, which is today's "Study more" grants, `last_exercise`, `last_reminded_at`, `last_lesson_finished_at` and `streak`. A reset changes the schedule, not the practice habit, so the streak continues. Because `last_exercise` stays, the reminder still measures inactivity from the last answer before the reset, so a learner can get a reminder soon after a reset (see [#258](https://github.com/pauk-slon/immer-wiederholen/issues/258)).

The current lesson isn't part of the record, so `/reset` doesn't change it either (see [Lessons](#lessons)). The learner finishes the lesson, and its pairs are answered as new pairs.

## Example: a learner's first day

The [demo course](https://github.com/pauk-slon/immer-wiederholen/tree/main/demo) has these links. `partizip_ii` chains to `perfekt_wortstellung` and gates `partizip_ii_meaning`. A learner's first day goes like this:

1. **Start.** Nothing is scheduled. The candidates are all new pairs that aren't gated. These are `singen` and `trinken` in `partizip_ii` and `perfekt_wortstellung`, `warten` in `verb_preposition`, and `auf` in `preposition_meaning`. `partizip_ii_meaning` is gated, so it isn't a candidate. All four words are fresh and fit the limit of 7. Suppose the engine picks `singen` in `partizip_ii`.
2. **Wrong answer.** `singen`/`partizip_ii` gets interval 0, is due today and is introduced today. The exercise has recalls, so a recall is required. The links run. `singen`/`perfekt_wortstellung` and `singen`/`partizip_ii_meaning` get entries that are due today, so the second pair is now unlocked. `singen` counts as 1 new word.
3. **Next exercise.** The engine excludes `singen` as the last word, so another word appears, for example `warten`. The answer schedules `auf`/`preposition_meaning` for today through `chains_by_answer`.
4. **`singen` again.** It is a free word now. Its `partizip_ii` is due for review, so the engine prefers this topic to the two newly scheduled topics. A correct answer doubles 0 to 1, so the pair is due tomorrow.
5. **Later today.** `perfekt_wortstellung` and `partizip_ii_meaning` of `singen` appear as new topics of a free word and don't use the limit. Each gets interval 0 and is due again today after its first answer.
6. **Tomorrow.** `singen`/`partizip_ii` is due for review, together with the pairs from yesterday that were still due at the end of the day.

## Conventions

- **"Today" is set once.** `Tutor.__init__` sets it in UTC and passes it to `StudentRecord`. Every date comparison uses it, so there is one place to change if days ever follow the learner's time zone. Times, such as the time of an answer or the reminder's inactivity window, use the current time directly.
- **`Tutor` never handles a raw schedule entry.** It reads with `StudentRecord.get_repetition_interval(word, topic)` and writes with `StudentRecord.schedule_pair(word, topic, *, repetition_interval, due_interval=None)`. `due_interval` is a number of days from today and defaults to the interval. `Tutor` passes it only for "due again today". `schedule_pair()` changes the two fields in place, so an `introduced_at` that was set just before stays.
- **`record_mark()` records an answer in one call.** It replaces `last_exercise`, updates `today_answers` and sets `introduced_at` on a new pair. It returns whether the pair was new and its previous interval. It reads the previous interval before it creates the entry, so the value is `None` for a pair without an entry and `0` for a pair with an unanswered entry. `check_answer()` takes `is_new` from this return value. A separate check afterwards would be wrong, because the answer is already recorded then.
- **`StudentRecord` doesn't know the course.** A record can have words and topics that the course no longer has, so `Tutor` filters the results of `StudentRecord` against the pairs of the course.
- **Malformed entries are ignored.** pydantic validates the entries, and an entry that doesn't fit is treated as absent.
- **`SelectablePairs` doesn't use the record.** It splits the candidates into `due_introduced`, `due_not_introduced` and `not_scheduled`. `select_word()` and `select_topic()` get the few values that they need as parameters, such as the introduced words, today's remaining limit and the last pair.

## Decisions

- [The repetition engine reports events on the current span](adr/0002-tutoring-events-on-the-current-span.md) (ADR 0002)
- [Topic links only schedule pairs that haven't started](adr/0004-links-only-schedule-unstarted-pairs.md) (ADR 0004)
- [Gates are declared explicitly](adr/0012-gates-declared-explicitly.md) (ADR 0012)
- [Streaks count intervals between answers, not calendar days](adr/0021-streaks-from-intervals-between-answers.md) (ADR 0021)
- [Streaks count finished lessons, not answers](adr/0027-streaks-count-finished-lessons.md) (ADR 0027)
- [Lessons are conversation state and refer to exercises by a content hash](adr/0026-lessons-in-conversation-state.md) (ADR 0026)
