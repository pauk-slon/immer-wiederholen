# 0002. The repetition engine reports events on the current span

**Status:** Accepted, 2026-08-23 ([#175](https://github.com/pauk-slon/immer-wiederholen/pull/175), closing [#173](https://github.com/pauk-slon/immer-wiederholen/issues/173)). Replaces the design of [#124](https://github.com/pauk-slon/immer-wiederholen/pull/124).

## Context

`check_answer()` and `next_exercise()` returned events that only tracing used. The events are worth seeing in traces. Examples are a marked answer, a scheduled linked topic, and the case when nothing is left to show. But `wiederholen.school.tutoring` intentionally has no infrastructure dependencies, so that its tests of `Tutor` need no mocks.

The first design ([#124](https://github.com/pauk-slon/immer-wiederholen/pull/124)) kept OpenTelemetry out of `tutoring`. `check_answer()` and `next_exercise()` returned their result together with a list of event dataclasses. The bot turned each event into a span event at every call site (`record_tutoring_events()`). Later it became clear that the bot was the only user of those lists, and it never read their content. For example, the "Study more" button depends only on `next_exercise()` returning `None`, not on the `reason` of the event.

## Decision

`Tutor` reports events with a call to `wiederholen.school.tutoring.events.emit()` at the moment when they happen. `emit()` adds a span event to `trace.get_current_span()`. `check_answer()` and `next_exercise()` return only their result. The events stay frozen dataclasses. They are declared next to the code that emits them and are internal to `tutoring`.

`tutoring` now depends on `opentelemetry-api`, but not on the SDK.

## Alternatives considered

- **Return events to the caller** (the design of #124). This keeps OpenTelemetry out of `tutoring`. But every caller gets a second return value to unpack and forward, for a fact that only tracing uses.
- **Inline `span.add_event()` calls with dict literals.** This is simpler, but the shape of each event is then spread across call sites. The content of an event is domain knowledge, and it belongs in one place.

## Consequences

- `Tutor`'s methods have plain signatures again. Frontends need no tracing code for its events, and the web app gets them without extra work.
- The OpenTelemetry API does nothing without a configured provider, so the tests of `Tutor` needed no changes.
- A test of an event needs a recording provider and an in-memory exporter (the shared `tracer` and `exporter` fixtures). It no longer checks a returned list.
- The rule that `tutoring` has no infrastructure dependencies now has one documented exception. This is the OpenTelemetry API, never the SDK.
