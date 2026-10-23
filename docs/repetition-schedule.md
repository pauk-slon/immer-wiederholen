# Repetition schedule

How `wiederholen.school.tutoring` decides what a learner practices and when: the schedule it keeps, how intervals grow, how the next exercise is picked, the daily limit on new words, how linked topics are scheduled, and what `/progress` reports. How links are declared in `topics.yaml` is in [Course format](course-format.md#linking-topics).

The engine is two classes in [`tutoring/`](https://github.com/pauk-slon/immer-wiederholen/tree/main/wiederholen/school/tutoring):

- **`Tutor`** (`session.py`) makes the decisions: `next_exercise()`, `check_answer()`, `request_recall()`, `check_recall()`, `should_remind()`, `progress()`, `get_hint()`. It's built per request as `Tutor(course, student_record)`.
- **`StudentRecord`** (`student_record.py`) reads and writes the learner's record — a plain dict the frontend loaded from storage (see [Storage and identity](storage.md#student-records)). It knows nothing about the course.

`SelectablePairs` (`selection.py`) holds the word and topic choice for `next_exercise()`. The conventions for editing these classes are in [Conventions](#conventions).

## The schedule

**Days are UTC days.** "Today", "due today", the daily limit and `/progress` all switch over at midnight UTC — for a learner in UTC+9, at 9 in the morning.

The schedule is kept per **pair** of word and topic: `singen` in `partizip_ii` and `singen` in `partizip_ii_meaning` are repeated independently. Several exercises of one pair share its entry.

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
| `repetition_interval` | days until the pair is due again after a correct answer; grows with each one |
| `due_date` | the day the pair is next due |
| `introduced_at` | the day the pair was first answered; absent until then. Set once, never changed |

A pair can have an entry without `introduced_at`: a linked topic scheduled for a word before the learner has seen it (see [Linked topics](#linked-topics)).

The rest of the record:

| Key | Meaning |
|---|---|
| `last_exercise` | the last answered exercise: question, word, topic, when, and the recall shown for it — used to avoid repeats and to decide on reminders |
| `today_answers` | today's count of answers and correct answers |
| `new_word_budget` | extra new words granted today with "Study more" |
| `last_reminded_at` | when the last reminder was sent |

`today_answers` and `new_word_budget` carry their date and count only on that day, so nothing needs cleaning up the next morning.

## Intervals

After each answer to a main exercise, `check_answer()` sets the pair's new interval:

- **correct**: the interval doubles, at least 1, at most 60 days (`MAX_REPETITION_INTERVAL_DAYS`);
- **wrong**: back to 0;
- **first answer**, right or wrong: 0.

So a pair answered correctly every time goes `0 → 1 → 2 → 4 → 8 → …`, and a wrong answer at any point starts it over from 0.

When the pair is next due:

- **after a first answer or a wrong one**: today. A new learner — or one right after `/reset` — would otherwise run out of material partway through the first day, since every correct first answer would push its pair to tomorrow.
- **otherwise**: in `repetition_interval` days.

Lateness doesn't matter: a pair answered correctly days after it was due doubles from its recorded interval as if it had been answered on time.

The first answer lands on 0, not 1, so that the next correct answer is the one that reaches 1 — a pair is only ever doubled from an interval it was actually tested at. Doubling from a placeholder 1 sent pairs two days out after their first day and left the next day with nothing due.

## Picking the next exercise

`next_exercise()` picks a **word**, then one of its **topics**, then one of that pair's exercises at random. Picking the word first keeps a pair with many exercises from showing up more often than one with a single exercise, and a word with several due topics from crowding out others.

### What can be picked

The candidates are every pair that is:

- **due**: has an entry with `due_date` today or earlier;
- **new and available**: has no entry yet, and its topic isn't gated (see [Linked topics](#linked-topics)).

Their words fall into three tiers:

| Tier | Words | New-word limit |
|---|---|---|
| **free** | already introduced through any topic | not counted |
| **queued** | not introduced, but with an entry already — a linked topic scheduled for them | counted, taken first |
| **fresh** | never touched | counted, fill what's left |

A word is free once any of its topics has been answered. So if `warten` is being learned in one topic, its untouched other topics come up without spending the new-word limit, and so does a topic just unlocked by a link.

`SelectablePairs.select_word()` takes as many queued words as today's remaining limit allows, then fills the rest with a random sample of fresh words, and picks uniformly among the free words and those taken. Fresh words are sampled down to the limit *before* the pick: a course with hundreds of untouched words doesn't dilute the chance of a handful of due ones.

`select_topic()` then prefers a topic of the chosen word that's **due for review** (answered before and due today); only if there's none does it pick among the word's new topics — including linked topics scheduled for today but not answered yet. A review has a deadline, new material doesn't.

### The daily limit on new words

At most 7 new **words** a day (`NEW_WORDS_PER_DAY`). In code, today's remaining limit is the `budget` passed to `select_word()`, a "Study more" grant is `NEW_WORD_BUDGET_GRANT`, and running out shows up as the `daily_cap_reached` event.

**Reviews have no limit.** A learner back after a week away gets every overdue review at once; only new words are held back.
 Words, not pairs: starting `sprechen` in two topics on one day is one new word.

A word counts as new today if it has been introduced and every one of its introduced topics was introduced today. A word started days ago whose other topic gets its first answer today doesn't count. A word with only a queued entry and nothing answered doesn't count either.

When the limit is what's left between the learner and more material, the bot's "Study more" button calls `Tutor.grant_new_word_budget()`, which adds 3 words to today's limit (`NEW_WORD_BUDGET_GRANT`). Grants stack: it's an opt-in for someone who explicitly wants more. A tap when the limit isn't reached does nothing — Telegram keeps old buttons tappable, and a tap on yesterday's button shouldn't raise today's limit. `/reset` leaves today's grants alone; they expire the next day anyway.

### Avoiding repeats

A pair answered for the first time is due again the same day, so without care the same word could come straight back. Three exclusions, each dropped if it would leave nothing to pick:

1. the last answer's word isn't picked;
2. if the same word is picked anyway, its last topic isn't;
3. among the pair's exercises, the last question isn't.

### When there's nothing to show

`next_exercise()` returns `None` in two cases, reported as a `NoExerciseAvailable` span event (see [Tracing](tracing.md#events-from-the-repetition-engine)):

- **`nothing_available`**: nothing is due and nothing new is available — everything's done, or what's left is locked behind gates;
- **`daily_cap_reached`**: only new words are left, and the limit is used up.

Either way the bot says the day is done and offers "Study more".

## Linked topics

`check_answer()` calls `_expedite_chained_topics()` after every answer, right or wrong:

- for each topic in `chains` and `gates` of the answered topic, the pair *(same word, that topic)*;
- for each topic in `chains_by_answer`, the pair *(the exercise's answer, that topic)*.

`_expedite_dependent()` gives such a pair an entry due today, with interval 0 — but only if the pair has no entry yet and the course has an exercise for it. A pair that already has an entry keeps it: once a linked topic has its own schedule, a link doesn't override it. Each scheduled pair is reported as a `TopicUnlocked` event.

A gated topic's pairs without an entry are excluded from "new and available", so they can't be picked until a link gives them one. After that they're due like any other pair. Locked pairs don't affect `/progress`: they have no entry to count.

`Course` merges `chains` and `gates` into `word_chained_topics` and keeps `chains_by_answer` as `answer_chained_topics`. An answer-chained topic can still be gated, through a `gates` entry under another topic: gating looks only at the topic, not at how its pair was scheduled.

### Restricted courses

`Course.restricted_to(topics)` narrows the exercises to some topics — the web widget's `topics`, the bot's `/topics` selection — and keeps the links as they are. A link into an excluded topic finds no exercise and does nothing. The same record works with any view: progress in an excluded topic stays where it was.

## Recalls

`request_recall(exercise)` picks one of the exercise's recalls at random, avoiding the one shown last for it, and stores it in `last_exercise`. The next answer replaces `last_exercise`, so nothing needs resetting between exercises.

Asking for an **optional** recall — after a correct answer — halves the pair's interval (at least 1) the first time it's asked for that answer, and its due date moves to match. A required recall after a wrong answer changes nothing; the interval is already 0.

`check_recall()` only compares: recall answers don't touch the schedule and don't count as activity for reminders.

## Progress

`progress()` reports six numbers for `/progress`, and changes nothing:

| Number | Meaning |
|---|---|
| `remaining_today` | pairs due today — reviews, plus linked topics scheduled for today |
| `new_today` | words started today, counted the same way as the daily limit |
| `answered_today`, `correct_today` | answers to main exercises today, and how many were right — attempts, not pairs |
| `learning` | words with any schedule entry, not yet mastered |
| `mastered` | words whose every topic has reached the 60-day interval |

`learning` and `mastered` count words, not pairs: a learner thinks "I'm learning `sprechen`", not about its topics separately. A word is mastered only when all its topics are — knowing a verb's Partizip II well doesn't make the verb mastered while its preposition is barely started.

`remaining_today` counts only what's genuinely due, not new material: how many new pairs a day brings can't be known in advance, since one new word can lead to more pairs through links.

## Resetting

`StudentRecord.reset_progress(student_record)`, called by `/reset`, deletes the schedule and today's answer counts. Without the counts, `/progress` would still show today's answers right after a reset.

It keeps the rest of the record: today's "Study more" grants, `last_exercise` and `last_reminded_at`. Because `last_exercise` survives, the reminder still measures inactivity from the last answer before the reset, so a learner can be reminded soon after resetting; see [#258](https://github.com/pauk-slon/immer-wiederholen/issues/258).

## Example: a learner's first day

On the [demo course](https://github.com/pauk-slon/immer-wiederholen/tree/main/demo), where `partizip_ii` chains to `perfekt_wortstellung` and gates `partizip_ii_meaning`:

1. **Start.** Nothing is scheduled. The candidates are every new, ungated pair — `singen` and `trinken` in `partizip_ii` and `perfekt_wortstellung`, `warten` in `verb_preposition`, `auf` in `preposition_meaning`. `partizip_ii_meaning` is gated, so it isn't a candidate. All four words are fresh and fit the limit of 7. Say `singen` in `partizip_ii` is picked.
2. **Wrong answer.** `singen`/`partizip_ii` gets interval 0, due today, introduced today. The exercise has recalls, so a recall is required. The links run: `singen`/`perfekt_wortstellung` and `singen`/`partizip_ii_meaning` get entries due today — the second one is now unlocked. `singen` counts as 1 new word.
3. **Next exercise.** `singen` is excluded as the last word, so another word comes up, say `warten`. Answering it schedules `auf`/`preposition_meaning` for today through `chains_by_answer`.
4. **`singen` again.** It's a free word now. Its `partizip_ii` is due for review, so that topic is preferred over its two newly scheduled ones. A correct answer doubles 0 to 1: due tomorrow.
5. **Later today**, `singen`'s `perfekt_wortstellung` and `partizip_ii_meaning` come up as new topics of a free word, without spending the limit. Each gets interval 0 and is due again today after its first answer.
6. **Tomorrow**, `singen`/`partizip_ii` is due for review, along with any of yesterday's pairs that ended the day due.

## Conventions

- **"Today" is resolved once**, in `Tutor.__init__`, in UTC, and passed to `StudentRecord`. Every date comparison uses it — one place to change if days should ever follow a learner's time zone. Times rather than dates — when an answer was given, the reminder's inactivity window — use the current time directly.
- **`Tutor` never handles a raw schedule entry.** It reads `StudentRecord.get_repetition_interval(word, topic)` and writes `StudentRecord.schedule_pair(word, topic, *, repetition_interval, due_interval=None)`. `due_interval` is days from today and defaults to the interval; it's passed only for "due again today". `schedule_pair()` updates the two fields in place, so `introduced_at` set moments earlier survives.
- **`record_mark()`** records an answer in one call: it replaces `last_exercise`, updates `today_answers`, stamps `introduced_at` on a new pair, and returns whether the pair was new and its previous interval. The previous interval is read before the entry is created, so it's `None` for a pair that had no entry and `0` for one that had an unanswered entry.
- **`StudentRecord` doesn't know the course.** `Tutor` filters its results against the course's pairs, since a record can hold words and topics the course no longer has.
- **Malformed entries are ignored**: entries are validated with pydantic, and anything that doesn't fit is treated as if it weren't there.
- **`SelectablePairs` doesn't touch the record.** It splits the candidates into `due_introduced`, `due_not_introduced` and `not_scheduled`; `select_word()` and `select_topic()` get the few values they need — introduced words, today's remaining limit, the last pair — as parameters.

## Design notes

- **No fixed ratio of reviews to new material.** An earlier `REVIEW_WEIGHT` mixed them by a fixed weight, which a large pool of untouched words could swamp. Sampling new words down to the daily limit before the pick replaced it.
- **No borrowing from tomorrow.** A fallback that showed early reviews when nothing was due was tried twice and dropped both times as overcomplicated. Making first answers due again the same day solved the first-day shortage more simply.
- **Links don't move existing entries.** An earlier version pulled a linked topic's due date to today on every answer. For topics that chain to each other (`partizip_ii` ⇄ `praeteritum`), each answer reset the other's due date, and learners got stuck answering the same pair of topics for one word.
- **`is_new` comes from `record_mark()`.** It already checks whether `introduced_at` is set, at the only moment it's safe to ask — just before it sets it. A separate check afterwards would see the answer already recorded.
- **A new-word counter can't be vacuously true.** "All of the word's introduced dates are today" holds for a word with no introduced topics at all, so the check requires at least one; a bug let queued words count as started.
- **`/progress` has no total.** A count of every untouched pair in the course once showed a learner with about 40 words in progress "290 exercises" — not a number anyone can act on.
