# 0024. A topic can show only the primary answer

**Status:** Accepted, 2026-10-29 ([#313](https://github.com/pauk-slon/immer-wiederholen/pull/313)). The feature is discussed in [#312](https://github.com/pauk-slon/immer-wiederholen/issues/312). Amends [ADR 0022](0022-several-equal-answers.md).

## Context

[ADR 0022](0022-several-equal-answers.md) made all answers of an exercise equal. After a wrong answer, the bot and the web widget show all of them. But some answers are only accepted, not taught. In the `plural` topic, the question is `die Stadt` and the answer is `Städte`. A learner often types `die Städte`. This is correct, and the course can accept it with `answer: [Städte, die Städte]`. But then each mistake in this topic shows `Städte / die Städte`, and the second form only adds noise. Spelling variants such as `wärst` and `wärest` have the same problem. The `explanation` already names the less common form.

ADR 0022 also lists a consequence. The first answer has a special role in `chains_by_answer` and `word_bank`, although the format calls all answers equal.

## Decision

The first item of `answer` is the **primary answer**. It is the form that the exercise teaches. In the code, it is `Exercise.primary_answer`, and `chains_by_answer` and `word_bank` use it.

A new topic setting `show_primary_answer_only` in `topics.yaml` controls what a frontend shows. With `true`, the bot and the web widget show only the primary answer after a wrong answer, and a multiple-choice exercise has only the primary answer as an option. The answer check doesn't change. It still accepts every answer. Without the setting, all answers are shown and are options, as before.

`Course.shown_answers()` is the one place that applies the setting. `Exercise` doesn't know the topic settings, so the bot and the web app get the shown answers from `Course`.

## Alternatives considered

- **Remove the article before the check** (`strip_article: die`). Not chosen. It puts German grammar into the engine, and it solves only this one case. With the setting, the course says which forms count, and the engine stays language-neutral.
- **A separate `accepted_answers` field.** ADR 0022 rejected this, because in most cases the forms are equal and one field is simpler. The decision about what to show depends on the topic, not on the exercise, so a topic setting fits better. `instruction` is set per topic for the same reason.
- **`show_answers: first | all`.** Not chosen. An enum needs a check against typos, and there is no third value. If a third value is necessary later, the few topics that use the setting are easy to change.

## Consequences

- The primary answer has a name, and the special role of the first answer is now part of the format.
- In a multiple-choice exercise with the setting, the learner can't tap a correct option that the bot never shows as an answer.
- A shadow exercise keeps `answer` unchanged (see [ADR 0005](0005-shadow-exercises-keep-the-answer.md)), and the topic settings apply to it too.
- A recall already showed only its first answer after a wrong answer, so an exercise in such a topic and its recall now behave the same.
