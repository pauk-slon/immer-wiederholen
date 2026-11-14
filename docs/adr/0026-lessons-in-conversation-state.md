# 0026. Lessons are conversation state and refer to exercises by a content hash

**Status:** Accepted, 2026-11-14 ([#328](https://github.com/pauk-slon/immer-wiederholen/pull/328)). Amended by [0027](0027-streaks-count-finished-lessons.md).

## Context

[#325](https://github.com/pauk-slon/immer-wiederholen/issues/325) groups exercises into lessons. A lesson is a short group of exercises that `Tutor` chooses from the learner's schedule. The learner answers them one after another, and a new lesson starts only after the current one. A lesson must be stored between requests, and it must refer to the exercises that it contains.

Today the shown exercise is conversation state, the state that each frontend keeps for itself (see [Storage and identity](../storage.md#chat-state)). The bot keeps it in the chat's FSM data as `shown_exercise`, and the web app keeps it in `WebSessionStore`. The student record holds only learning state (see [ADR 0008](0008-student-record-separate-from-chat-state.md)).

In the real course, a question isn't unique. 79 questions repeat across topics, for example a bare verb in `partizip_ii` and in `praeteritum`. 5 questions repeat within one pair, with different answers.

## Decision

A lesson is conversation state. Each frontend keeps its own lesson next to the exercise that it shows. The bot keeps it in the FSM data as lasting chat state, and the web app keeps it in `WebSessionStore` under its own key, by learner and topics. `Tutor` gets the lesson as a plain dict and changes it in place, as it does with the student record.

A lesson refers to an exercise by `Exercise.content_key`, a SHA-256 hash of all fields of the exercise. When `Tutor` takes the next exercise from a lesson, it skips a key that the course doesn't have. A lesson is valid only on the day when `Tutor` started it.

The bot saves the lesson only after AI generation succeeds, together with `shown_exercise`. If generation fails, the next request takes the same exercise from the lesson again.

## Alternatives considered

- **The lesson in the student record.** Not chosen. The bot and the web app would share one lesson. A Telegram chat keeps the buttons of an exercise after the learner answers it on the web, and `check_answer()` isn't idempotent, so the same exercise could be answered twice. The web app restricts the course by its own topics, so a lesson would be rebuilt at each switch between the frontends. The schedule, the streak and the daily limit stay shared, because they are in the student record.
- **Whole exercises in the lesson,** as `shown_exercise` is today. Not chosen, because after a course update the learner sees outdated texts, and a removed exercise can't be detected.
- **`word`, `topic` and `question` as the reference.** Not chosen, because 5 such triples repeat in the real course.
- **`Exercise.cue_key`, the hash of the question.** Not chosen, because a question repeats across topics. The key of an illustration also has another purpose (see [ADR 0017](0017-cues-keyed-by-question-hash.md)).
- **`word`, `topic`, `question` and the primary answer.** This is readable in storage, and a fix to an explanation keeps the reference. Not chosen, because its uniqueness isn't guaranteed.
- **A lesson that continues on the next day.** Not chosen, because its pairs come back as due reviews anyway.

## Consequences

- One rule covers three cases. An exercise that was edited or removed, an exercise outside the topics of `/topics`, and an exercise outside the topics of a web widget are all skipped. `/topics` doesn't need to reset the lesson.
- Any edit of an exercise, or a new field in `Exercise`, changes its key. A stored lesson then skips the exercise once. For a short lesson that lives for one day, this is cheap.
- The same pair can be in the lesson of the bot and in the lesson of the web app. After an answer in one frontend, the other one can ask the pair again before it is due. This already happens with `shown_exercise`.
- A lesson whose remaining keys are all missing from the course is replaced without `LessonFinished`.
