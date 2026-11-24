# 0036. Practice after a lesson is the learner's choice

**Status:** Accepted, 2026-11-24 ([#397](https://github.com/pauk-slon/immer-wiederholen/pull/397)).

## Context

After a lesson of the bot, a lesson recall can follow ([ADR 0031](0031-model-writes-and-checks-a-lesson-recall.md), [ADR 0033](0033-lesson-recall-for-every-chat-with-a-daily-limit.md)). The summary of the lesson had one button, "Continue". In a lesson with a lesson recall, this button started the lesson recall. In other lessons, it started the next lesson.

So the button didn't say what it does, and the learner couldn't decline the lesson recall. A learner who expected the next lesson got a translation task. To leave it, the learner had to skip each sentence or know `/wiederholen`.

The button had a neutral text because the interface had no names for a lesson and a lesson recall. Without names, a button can only say "go on", and a summary can only say "done".

## Decision

The interface uses these words:

| Code | Russian | English |
|---|---|---|
| exercise | задание | exercise |
| lesson | урок | lesson |
| lesson recall | практика | practice |

A recall of a single exercise gets no noun. The verb on its button is enough. The list is a comment in `l10n.py`, next to the texts.

When the bot can give a lesson recall, the summary of the lesson has two buttons. One starts the practice, and the other starts the next lesson. The practice button has a row of its own, because its text is too long to share a row on a phone. The same applies to the other places where a lesson ends, such as the result of a recall after the last answer.

The texts of the summaries, the buttons and the line before the first sentence use the words of the table.

## Alternatives considered

- **Keep one button, with an honest text.** The lesson recall stays a part of every lesson that can have one. Not chosen. The learner still can't decline it, and a learner who has no time for it leaves the chat with an unfinished task.
- **"Translation" instead of "practice".** The word says what the learner will do. Not chosen. "Practice" says why, and it stays right if the task changes its form, for example to sentences that the learner writes.
- **"Session", "round" or "set" instead of "lesson".** They are more exact for a review of known material. Not chosen. Learners of other apps already know a lesson as a short set of exercises with a result. The bot also uses "занятие" for a session in the reminder settings.

## Consequences

- Fewer lesson recalls start, so the model costs less. The update span of an answer gets `lesson_recall.offered` when the summary offers the practice. The number of `lesson_recall.generate` spans divided by the number of offers shows how many learners choose it.
- The "next lesson" button can lead to the reply that nothing is left for today. The bot would need a check of what comes next that doesn't change the lesson, and `Tutor` has no such check yet.
- A new text that names a lesson or a lesson recall uses the words of the table.
