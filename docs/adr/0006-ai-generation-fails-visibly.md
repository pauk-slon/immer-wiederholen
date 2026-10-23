# 0006. AI generation fails visibly, without a fallback

**Status:** Accepted, 2026-08-10 ([#163](https://github.com/pauk-slon/immer-wiederholen/pull/163))

## Context

Generating a shadow exercise in `/ai` mode can fail: the Anthropic API call, a response without the expected tool call, malformed input, or a result that fails validation (see [AI-generated content](../authoring.md#failures)). The mode is a testing tool, enabled by a feature flag for a single test chat, to judge whether AI-personalized exercises are worth building.

## Decision

Every failure raises `AIGenerationError`, and the learner sees an error message. The authored exercise is never shown in its place.

## Alternatives considered

- **Fall back to the authored exercise.** Smoother practice, but a broken integration would look like a working one: the tester would keep seeing normal questions and never know generation had stopped working ([#163](https://github.com/pauk-slon/immer-wiederholen/pull/163)).

## Consequences

- A broken integration is noticed immediately.
- A failed generation interrupts practice until the learner retries with `/wiederholen` or turns the mode off.
- The reasoning depends on `/ai` being a testing tool. If it ever becomes a feature for regular learners, this decision should be revisited and superseded.
