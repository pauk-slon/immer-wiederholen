# 0034. A wrong first answer to a pair doesn't require a recall

**Status:** Accepted, 2026-11-23 ([#391](https://github.com/pauk-slon/immer-wiederholen/pull/391)).

## Context

An exercise can have recalls (see [Course format](../course-format.md#recalls)). Until now, every wrong answer to such an exercise required a recall. The learner had to type the whole sentence before the next exercise.

A wrong first answer to a pair isn't forgetting. The learner meets the exercise for the first time and often guesses. The feedback and the explanation are what teaches here. A recall right after them repeats a fresh trace in working memory, so it adds little to long-term memory. The pair comes back later the same day anyway, because a wrong answer sets its interval to 0. That delayed repetition is the stronger one.

New learners meet mostly new pairs. In the traces of 60 days, 21 of the 27 required recalls of the new learners came after a wrong first answer. One learner got two required recalls in the first lesson, left it before its end and blocked the bot. The data is too small to show that required recalls make learners leave. But for a new learner they are the largest effort at the moment that matters most.

A wrong answer to a pair that the learner answered before is different. It shows forgetting or a confusion with a similar form, and typing the correct sentence at once helps to replace the wrong trace.

## Decision

`Tutor.check_answer()` makes the recall optional after a wrong first answer to a pair, for every learner. A pair is new if its schedule entry has no `introduced_at`. After a wrong answer to a pair with `introduced_at`, the recall stays required.

An optional recall after a wrong answer doesn't halve the interval. The interval stays 0, so the pair comes back the same day. `last_exercise` keeps `is_answer_correct` for this.

## Alternatives considered

- **No required recall until the first finished lesson.** Not chosen. New pairs stay frequent in the next days, so the problem only moves to the second lesson. It also needs a state "new learner" that the rule doesn't otherwise need.
- **No recall at all after a wrong first answer.** Not chosen. Some learners want to type the sentence at once, and the optional recall keeps this choice.
- **Keep every recall after a wrong answer required.** Not chosen, for the reasons in the context.

## Consequences

- The rule is in `wiederholen.school.tutoring`, so the bot and the web app follow it the same way.
- `ExerciseAnswered` can now have `recall_mode` `optional` with `is_correct` false. To compare the result, look at how often the next answer to a new pair after a wrong first answer is right, before and after this change. If it drops a lot, the immediate recall had value, and this decision needs a review.
- In a bot lesson with a lesson recall, the bot drops every optional recall (see [Bot](../bot.md#lesson-recall)). So a wrong first answer there gets no recall at all. The lesson recall at the end uses the wrong answers of the lesson instead.
