# 0016. Web sessions are keyed by learner and topics

**Status:** Accepted, 2026-08-26 ([#193](https://github.com/pauk-slon/immer-wiederholen/pull/193))

## Context

The web app remembers which exercise it showed a learner, so it can check the answer: the exercise sent to the browser has no answer in it. That state was keyed by the learner alone. The session cookie is shared by every page on the domain, and each page embeds a widget with its own topics; the widget's own reload cache is per page.

A learner reported a correct answer marked wrong, with another page's answer shown as correct. Opening a second landing page between loading a question on the first and answering it had replaced the shown exercise.

## Decision

`WebSessionStore` keys its state by learner **and** the sorted set of topics, matching the widget's per-page cache. Every exercise endpoint sends `topics`, even those that don't use them to pick an exercise.

## Alternatives considered

None are recorded in [#193](https://github.com/pauk-slon/immer-wiederholen/pull/193), which was a fix for the reported bug.

## Consequences

- Widgets on different pages no longer interfere.
- Two pages with the same topics share a session, which is harmless: they're the same widget.
- The language isn't part of the key; it only changes which translation of the same exercise is returned.
