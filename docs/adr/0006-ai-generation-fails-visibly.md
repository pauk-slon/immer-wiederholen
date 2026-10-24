# 0006. AI generation fails visibly, without a fallback

**Status:** Accepted, 2026-08-10 ([#163](https://github.com/pauk-slon/immer-wiederholen/pull/163))

## Context

The generation of a shadow exercise in `/ai` mode can fail. The Anthropic API call can fail, the response can lack the expected tool call, the input can be malformed, or the result can fail validation (see [AI-generated content](../authoring.md#failures)). The mode is a testing tool. A feature flag enables it for one test chat, to find out whether AI-personalized exercises are worth building.

## Decision

Every failure raises `AIGenerationError`, and the learner sees an error message. The bot never shows the authored exercise in its place.

## Alternatives considered

- **Show the authored exercise instead.** Practice would continue without interruption. But a broken integration would look like a working one. The tester would keep seeing normal questions and would never know that generation had stopped working ([#163](https://github.com/pauk-slon/immer-wiederholen/pull/163)).

## Consequences

- A broken integration is noticed immediately.
- A failed generation stops practice until the learner tries again with `/wiederholen` or disables the mode.
- The reasoning depends on `/ai` being a testing tool. If it ever becomes a feature for regular learners, this decision needs a review and a new ADR that supersedes it.
