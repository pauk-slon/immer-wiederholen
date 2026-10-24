# 0005. Shadow exercises keep the answer

**Status:** Accepted, 2026-08-14 ([#166](https://github.com/pauk-slon/immer-wiederholen/pull/166)). It builds on [#163](https://github.com/pauk-slon/immer-wiederholen/pull/163) and [#164](https://github.com/pauk-slon/immer-wiederholen/pull/164).

## Context

The `/ai` mode replaces the exercise that `Tutor` picked with a "shadow" that Claude writes (see [AI-generated content](../authoring.md#shadow-exercises)). `Tutor` picked a specific exercise for a specific word, topic and answer. The shadow should test the same thing.

The first version ([#163](https://github.com/pauk-slon/immer-wiederholen/pull/163)) rewrote only the question and the explanation and kept all other fields, so the shadow was correct by construction. From the start, each topic had to enable generation explicitly (`ai_generation` in `topics.yaml`). Generation was meant for topics where the answer doesn't depend on the exact wording.

[#164](https://github.com/pauk-slon/immer-wiederholen/pull/164) then generated whole exercises, with the answer, as an intentional experiment. The question was whether a short prompt with the authoring guide would give good enough results by itself. The plan was to decide afterwards whether to limit generation again, to add a verification step, or both. The model could choose any answer that was correct for its own sentence. For pairs with more than one correct answer, this silently changed what the learner practiced.

## Decision

The shadow keeps `word`, `topic` and `answer` from the picked exercise. Around that fixed answer, the model writes the question, the distractors, the explanation, the recalls and, if the original has one, the description ([#166](https://github.com/pauk-slon/immer-wiederholen/pull/166)).

## Alternatives considered

- **Let the model choose the answer** (the experiment of #164). This gives more varied exercises. But the shadow could test something other than what `Tutor` picked.
- **Rewrite only the wording** (the version of #163). This is correct by construction. #164 moved away from it to find out how much a short prompt can generate well. No later pull request records a decision to go back.
- **Add a verification step.** #164 mentioned it as an option. It wasn't built.

## Consequences

- `answer` is correct by construction, and the schedule treats a shadow like the original.
- Distractors and recalls still depend on correct grammar from the model.
- Each topic still has to enable generation explicitly. Even with a fixed answer, some exercises can't be rewritten safely. These are questions with a bare form, word-order exercises and topics where the subject decides the answer.
