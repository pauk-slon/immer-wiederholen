# 0031. A model checks translations that practice verb government

**Status:** Accepted, 2026-11-19 ([#361](https://github.com/pauk-slon/immer-wiederholen/pull/361)). The problem and the experiment are described in [#352](https://github.com/pauk-slon/immer-wiederholen/issues/352).

## Context

The topics of verb government (`verb_preposition`, `verb_preposition_case`, `verb_case`) ask for one word in a gap, the preposition or the article. A learner who knows `warten auf + Akkusativ` in a gap can still fail to use it in a sentence of their own. A translation from Russian or English tests this. But a phrase has many correct translations, and a list of accepted answers can't hold them all. The check that the course has now compares the answer with a list (see [Course format](../course-format.md#exercisesyaml)).

Until now, a model never decided whether an answer is correct. The `/ai` mode writes exercises around a fixed answer ([ADR 0005](0005-shadow-exercises-keep-the-answer.md)), and the answer check stays exact.

The experiment in #352 tested the check, not the phrases, because a review by the author can fix the phrases. 10 pairs got one phrase each and 61 labeled learner answers. Each answer had a wrong preposition, a wrong case, another verb, a mistake outside the construction, a free translation or an edge case. Claude Haiku 5.5 and gemma-4-26b gave all 61 verdicts as labeled. gpt-oss-120b and mistral-small-3.1 rejected 1 and 2 correct answers. No model accepted a wrong construction. Haiku took 0.9 s at the median, the Workers AI models 1.7 to 8.4 s.

## Decision

A new topic practices translations for the pairs of verb government. It works as follows:

- **The exercise.** The question is a phrase in Russian or English that a course author writes ahead of time. It follows the rules of the `*_meaning` topics. The situation points to one construction, and no clause, infinitive or compound (`worauf`, `darum`) gives a correct translation around it. Each phrase is an exercise of its own, with the verb as `word`.
- **The hint names only the verb,** such as `warten` or `sich freuen`. So the exercise tests the preposition and the case. Two constructions of one verb (`sich freuen auf` and `sich freuen über`) share the hint, and the situation decides.
- **The answers are reference translations.** An answer that matches one of them, as the current check compares, is correct without a model. After a wrong answer, the learner sees the first reference.
- **A model checks every other answer.** The model is Claude Haiku 5.5. It gets the phrase, the verb, the target construction, the references and the answer. It returns a verdict and a short comment for the learner.
- **The verdict depends only on the construction.** The answer is correct if it has the verb from the hint in any form, the reflexive pronoun in the right case if the verb has one, the target preposition (a contraction such as `am` or `aufs` counts), and the target case after it. Other mistakes go into the comment, but don't change the verdict.
- **Edge rules.** These answers are wrong:
    - no `sich`, or `sich` in the wrong case (`ich freue mir`),
    - no separable prefix (`hängt von der Größe` without `ab`),
    - a pronominal adverb (`darum`, `worauf`) in place of the thing that the phrase names,
    - another verb, even a correct one (`sich fürchten vor` for the hint `Angst haben`).

    A typo or a wrong form of the verb itself (`interesiert`, `gefreuen`) is correct, and the comment names it.
- **The explanation has two parts.** The author writes the rule of the construction once, as `explanation`, such as `warten auf + Akkusativ`. The model comments only on the learner's answer.
- **A failed check doesn't count.** If the model call fails or its reply can't be read, the learner sees an error message, and the answer counts neither as correct nor as wrong. The learner can send the answer again. A wrong verdict in place of an error would delay the pair for a mistake that the learner didn't make.
- **The bot only, at first.** The web app keeps its current topics until the check has run in the bot.

## Alternatives considered

- **Generate the phrases during practice.** Not chosen. A generated phrase can't be reviewed. In the first draft of the phrases for the experiment, many phrases had a correct translation without the construction, such as `Vergiss den Schlüssel nicht` or a `dass` clause. A review ahead of time removes such phrases.
- **Only the list of references, without a model.** Not chosen. A free translation that is correct, such as a changed word order or another subject, would count as wrong, and the learner would learn to copy the reference.
- **A hint with the preposition, such as `warten + auf`.** Not chosen, because the exercise would then test only the case.
- **Accept a synonym of the verb.** Not chosen, because the pair is about the verb from the hint, and the schedule records the answer for this verb.
- **A free model on Workers AI.** gemma-4-26b was as accurate as Haiku, but 9 times slower, while the learner waits for the verdict. It stays an option if the cost of Haiku becomes a problem. The other free models rejected correct answers, once with an invented reason.
- **A comment by the model only, with the rule in it.** Not chosen. Both models repeated the rule in every comment, and the author can write the rule better once.

## Consequences

- For the first time, a model decides a verdict that changes the schedule. A wrong verdict is possible, and the learner can't dispute it.
- The text that the learner types goes to Anthropic. It still never goes into the traces ([Tracing](../tracing.md)).
- The check costs about $0.0002 for an answer that doesn't match a reference.
- Without an Anthropic key, the bot can't offer the topic, so the deployment must hide it.
- The edge rules are in the prompt, and the experiment labeled the answers by these rules. So it tested mostly how the model follows them. Real answers of learners can show new cases.
