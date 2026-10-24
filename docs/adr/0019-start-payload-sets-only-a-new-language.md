# 0019. A /start language payload sets only a new chat's language

**Status:** Accepted, 2026-10-24 ([#295](https://github.com/pauk-slon/immer-wiederholen/pull/295)).

## Context

A "start the bot" link can carry a language as the deep-link payload, for example `t.me/ImmerWiederholenBot?start=en`. The payload was added for the landing page. There, a switch to the language of the page is probably what the visitor wants. Before this decision, `/start` with such a payload always overwrote the stored language.

Since [#285](https://github.com/pauk-slon/immer-wiederholen/pull/285), the bot links in the docs and in the README also carry `?start=en`. A Russian-speaking learner who taps such a link got an English interface without a warning. The learner then had to switch back with `/language`.

## Decision

The payload sets the language only in a new chat. A new chat is a chat that has no FSM data yet. It never changes the language of a chat that the learner already uses. A learner changes the language of an existing chat only with `/language`.

A missing `language` key isn't enough to find a new chat. The key exists only after `/language` or a payload. A learner who always uses the default language doesn't have it.

## Alternatives considered

- **Two different payloads.** For example, `?start=en` sets the language only for a new chat, and `?start=lang-en` always switches it. Not chosen, because each link then must choose the correct payload, and no current link needs to switch the language.
- **Ask the learner.** When the payload and the stored language are different, the bot shows a one-tap choice. Not chosen, because it adds a question to every start from a link in the other language. `/language` already does the same in one tap.

## Consequences

- A link in any language doesn't change the language of an existing learner.
- An existing learner who taps "English" on the landing page keeps the old language and must use `/language`.
