# 0016. Web sessions are keyed by learner and topics

**Status:** Accepted, 2026-08-26 ([#193](https://github.com/pauk-slon/immer-wiederholen/pull/193))

## Context

The web app stores which exercise it showed a learner, so that it can check the answer. The exercise sent to the browser has no answer in it. The key of this state was the learner alone. All pages on the domain share the session cookie, and each page embeds a widget with its own topics. The widget's own cache for page reloads is separate for each page.

A learner reported that a correct answer was marked wrong, and that the answer of another page was shown as correct. The learner had loaded a question on one landing page and opened a second landing page before the answer. The second page had replaced the shown exercise.

## Decision

`WebSessionStore` keys its state by learner **and** the sorted set of topics, in the same way as the widget's cache for each page. Every exercise endpoint sends `topics`, even the endpoints that don't use them to pick an exercise.

## Alternatives considered

[#193](https://github.com/pauk-slon/immer-wiederholen/pull/193) records no alternatives. It was a fix for the reported bug.

## Consequences

- Widgets on different pages no longer affect each other.
- Two pages with the same topics share a session. This does no harm, because they are the same widget.
- The language isn't part of the key, because it only changes which translation of the same exercise the server returns.
