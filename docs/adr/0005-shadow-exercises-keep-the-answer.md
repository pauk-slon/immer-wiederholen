# 0005. Shadow exercises keep the answer and never fall back

**Status:** Accepted, 2026-08-14 ([#163](https://github.com/pauk-slon/immer-wiederholen/pull/163), [#164](https://github.com/pauk-slon/immer-wiederholen/pull/164), [#166](https://github.com/pauk-slon/immer-wiederholen/pull/166))

## Context

The `/ai` mode ([#163](https://github.com/pauk-slon/immer-wiederholen/pull/163)) replaces the exercise the scheduler picked with a "shadow" written by an LLM (see [AI-generated content](../authoring.md#shadow-exercises)). The scheduler picked a specific exercise for a specific word, topic and answer; the shadow has to test the same thing, and an LLM can get German grammar wrong. It's a testing tool, used by one flagged chat.

At first only the question and explanation were rewritten. Generating whole exercises ([#164](https://github.com/pauk-slon/immer-wiederholen/pull/164)) let the model also choose the answer, as long as it was correct for its own sentence. For pairs that admit several correct answers, that quietly changed what was being practiced.

## Decision

- The shadow keeps `word`, `topic` and `answer` from the picked exercise; the model writes the question, distractors, explanation, recalls and, when the original has one, the description around that fixed answer ([#166](https://github.com/pauk-slon/immer-wiederholen/pull/166)).
- Generation is opt-in per topic (`ai_generation`), only for topics where the answer doesn't depend on the exact wording.
- Any failure shows an error message. There's no fallback to the authored exercise ([#163](https://github.com/pauk-slon/immer-wiederholen/pull/163)).

## Alternatives considered

- **Let the model choose the answer.** More varied exercises, but the shadow could test something other than what the scheduler picked.
- **Rewrite only the wording.** Safest, but the shadow's distractors and recalls would still refer to the original sentence.
- **Fall back to the authored exercise on failure.** Smoother for the learner, but a broken integration would look like a working one: the tester would see normal questions and never know.

## Consequences

- `answer` is correct by construction, and scheduling treats a shadow like the original.
- Distractors and recalls still depend on the model getting the grammar right.
- Some topics can't use the mode at all: bare-form questions, word-order exercises, topics where the subject decides the answer.
- A failed generation interrupts practice until the learner retries or turns the mode off.
