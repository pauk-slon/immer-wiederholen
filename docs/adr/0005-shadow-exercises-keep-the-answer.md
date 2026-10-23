# 0005. Shadow exercises keep the answer

**Status:** Accepted, 2026-08-14 ([#166](https://github.com/pauk-slon/immer-wiederholen/pull/166)); builds on [#163](https://github.com/pauk-slon/immer-wiederholen/pull/163) and [#164](https://github.com/pauk-slon/immer-wiederholen/pull/164)

## Context

The `/ai` mode replaces the exercise the scheduler picked with a "shadow" written by an LLM (see [AI-generated content](../authoring.md#shadow-exercises)). The scheduler picked a specific exercise for a specific word, topic and answer; the shadow should test the same thing.

The first version ([#163](https://github.com/pauk-slon/immer-wiederholen/pull/163)) rewrote only the question and explanation and kept everything else, so the shadow was correct by construction. From the start, generation was opt-in per topic (`ai_generation` in `topics.yaml`), for topics where the answer doesn't depend on the exact wording.

[#164](https://github.com/pauk-slon/immer-wiederholen/pull/164) then generated whole exercises, answer included, as a deliberate experiment: would a short prompt with the authoring guide produce good enough results on its own? The plan was to decide afterwards whether to narrow generation back down, add a verification pass, or both. Letting the model choose any answer correct for its own sentence turned out to quietly change what was being practiced for pairs that admit more than one correct answer.

## Decision

The shadow keeps `word`, `topic` and `answer` from the picked exercise. The model writes the question, distractors, explanation, recalls and, when the original has one, the description around that fixed answer ([#166](https://github.com/pauk-slon/immer-wiederholen/pull/166)).

## Alternatives considered

- **Let the model choose the answer** (the #164 experiment). More varied exercises, but the shadow could test something other than what the scheduler picked.
- **Rewrite only the wording** (the #163 version). Correct by construction; #164 moved away from it to find out how much a short prompt could generate well. No later pull request records a decision to go back.
- **Add a verification pass**, mentioned in #164 as an option. Not done.

## Consequences

- `answer` is correct by construction, and scheduling treats a shadow like the original.
- Distractors and recalls still depend on the model getting the grammar right.
- Per-topic opt-in stays necessary: bare-form questions, word-order exercises and topics where the subject decides the answer can't be rewritten safely even with a fixed answer.
