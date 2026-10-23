# 0002. The repetition engine reports events on the current span

**Status:** Accepted, 2026-08-23 ([#175](https://github.com/pauk-slon/immer-wiederholen/pull/175), closing [#173](https://github.com/pauk-slon/immer-wiederholen/issues/173)); replaces the design of [#124](https://github.com/pauk-slon/immer-wiederholen/pull/124)

## Context

Things worth observing happen inside `Tutor`: an answer is marked, a linked topic is scheduled, nothing is left to show. They should appear in the traces. `wiederholen.school.tutoring` deliberately has no infrastructure dependencies, so that `Tutor` can be tested without mocks.

The first design ([#124](https://github.com/pauk-slon/immer-wiederholen/pull/124)) kept `tutoring` free of OpenTelemetry: `check_answer()` and `next_exercise()` returned their result together with a list of event dataclasses, and the bot turned each event into a span event at every call site (`record_tutoring_events()`). It turned out the bot was the only consumer of those lists, and it never looked at their content — for example, the "Study more" button depends only on `next_exercise()` returning `None`, not on the event's `reason`.

## Decision

`Tutor` reports events by calling `wiederholen.school.tutoring.events.emit()` at the moment they happen. `emit()` adds a span event to `trace.get_current_span()`. `check_answer()` and `next_exercise()` return only their result. The events stay frozen dataclasses, declared next to the code that fires them, and are internal to `tutoring`.

`tutoring` now depends on `opentelemetry-api`, but not the SDK.

## Alternatives considered

- **Return events to the caller** (the #124 design). Keeps `tutoring` free of OpenTelemetry, but adds a second return value every caller has to unpack and forward, for a fact only tracing uses.
- **Inline `span.add_event()` calls with dict literals.** Simpler, but scatters each event's shape across call sites; what an event contains is domain knowledge that belongs in one place.

## Consequences

- `Tutor`'s methods have plain signatures again, and frontends need no tracing code for its events — the web app gets them for free.
- The OpenTelemetry API is a no-op without a configured provider, so `Tutor`'s tests needed no changes.
- Testing an event means a recording provider and an in-memory exporter (the shared `tracer`/`exporter` fixtures) instead of asserting on a returned list.
- `tutoring`'s "no infrastructure" rule now has one documented exception: the OpenTelemetry API, never the SDK.
