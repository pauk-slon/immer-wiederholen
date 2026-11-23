# 0032. The /ai mode is removed

**Status:** Accepted, 2026-11-23 ([#377](https://github.com/pauk-slon/immer-wiederholen/pull/377)). It supersedes [0005](0005-shadow-exercises-keep-the-answer.md). The plan is in [#370](https://github.com/pauk-slon/immer-wiederholen/issues/370).

## Context

The `/ai` mode replaced each exercise with a shadow that Claude wrote for the same word and answer ([ADR 0005](0005-shadow-exercises-keep-the-answer.md)). It was a testing tool behind the `ai_exercises` feature flag. The goal was to find out whether exercises that a model writes give useful variety. Only one test chat ever had the flag.

The lesson recall ([ADR 0031](0031-model-writes-and-checks-a-lesson-recall.md)) gives this variety in another way. After a lesson, the learner builds new sentences with what the lesson practiced. The authored exercises stay as they are.

The mode had its own costs:

- `_apply_ai_mode()` was a branch in each handler that shows an exercise. The lesson code had to handle a shadow, which has another key than the exercise that the lesson gave.
- Each topic had to enable it in `topics.yaml` with `ai_generation`, and the course format had to explain which topics are safe.
- The shared Anthropic client had a timeout and retries for `/ai`, and the lesson recall set its own for each request.
- `AUTHORING_GUIDE_PATH` sent the content repo's guide for authors to the model.

## Decision

The `/ai` mode is removed. This includes the `/ai` command, `wiederholen.school.authoring.shadow_exercises`, the `ai_mode` setting, `Course.ai_generatable_topics` and `AUTHORING_GUIDE_PATH`. The Anthropic client now has the SDK's default settings, and each call sets its own timeout and retries.

The course loader ignores `ai_generation` in `topics.yaml`, and the bot ignores the `ai_exercises` flag, as it ignores every unknown setting. So a course or a configuration from before still works.

[ADR 0006](0006-ai-generation-fails-visibly.md) stays, because the lesson recall also fails visibly with `AIGenerationError`.

## Alternatives considered

- **Keep `/ai` until the lesson recall is open to every chat,** as #370 first planned. Not chosen. No learner had `/ai`, so no learner loses it now.
- **Keep the shadow exercises in `school` without the command,** for a later use. Not chosen. Unused code still costs a branch in the lesson code and a setting in the course format. Git keeps it if it is needed again.

## Consequences

- One flow shows an exercise. The bot shows only authored exercises, and a lesson always gets an answer to the exercise that it gave.
- A course author no longer decides which topics a model may rewrite.
- `ai_mode` and `shown_is_ai_generated` can stay in the FSM data of the test chat. The bot doesn't read them, and the end of the next exercise removes them, because they aren't lasting chat state.
- [ADR 0006](0006-ai-generation-fails-visibly.md) gives its reason for a testing tool. The lesson recall is behind a feature flag too, so the reason still holds. Before the flag opens to everyone, ADR 0006 needs a review.
- The notes about shadows in [ADR 0022](0022-several-equal-answers.md), [ADR 0024](0024-primary-answer-per-topic.md) and [ADR 0030](0030-cue-field-sets-the-scene-or-turns-it-off.md) no longer apply.
