# 0022. An exercise can have several equal answers

**Status:** Accepted, 2026-10-25. Amended by [0024](0024-primary-answer-per-topic.md). The feature is discussed in [#305](https://github.com/pauk-slon/immer-wiederholen/issues/305).

## Context

An exercise had exactly one answer. Some questions have more than one correct answer, for example `komm` and `komme` in the Imperativ, or `sandte` and `sendete` for `senden`. A learner who typed the other correct form got a mistake.

## Decision

`answer` in `exercises.yaml` is a string or a list of strings. In the code, `Exercise.answer` is always a list. All answers in the list count as correct, and none of them is the main one. After a wrong answer, the bot and the web widget show all of them. The few places that need one word use the first answer. These are `chains_by_answer` and the correct order of `word_bank`. [Course format](../course-format.md#several-correct-answers) describes the rules.

Most exercises have only one answer, so a string stays the short form for them. For this reason, the existing courses need no change. An exercise that the bot or the web app saved with a string answer before this change also loads.

## Alternatives considered

- **`answer` plus `accepted_answers`.** The first proposal in [#305](https://github.com/pauk-slon/immer-wiederholen/issues/305) kept `answer` as the main form and added the other forms in a separate field. Not chosen, because in most cases the forms are equal, and one field is simpler for a course author. A recall's `answer` is a list too.
- **A new list field `answers` instead of `answer`.** Not chosen, because most exercises have only one answer. Each of them would need a list with one item.
- **Only for typed exercises.** Not chosen. Several correct options in a multiple-choice exercise and several orders of a `word_bank` cause no problem.

## Consequences

- The bot and the widget can't say "Correct. Usually: komm", because no form is the main one. The `explanation` says which form is more common.
- The first answer has a special role in `chains_by_answer` and `word_bank`, although the format calls all answers equal.
- A shadow exercise keeps all answers (see [ADR 0005](0005-shadow-exercises-keep-the-answer.md)).
