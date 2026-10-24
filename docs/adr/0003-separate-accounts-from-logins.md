# 0003. Separate learners from the ways they log in

**Status:** Accepted, 2026-09-19 ([#208](https://github.com/pauk-slon/immer-wiederholen/pull/208)). Extended to browser logins on 2026-09-20 ([#219](https://github.com/pauk-slon/immer-wiederholen/pull/219)).

## Context

A `StudentID` addresses the record of a learner. The bot used to derive it from the Telegram chat id (`TelegramStudentID.encode(chat_id)`). This tied "who is this learner" to "which chat is this". It worked while Telegram was the only way to use the project. But a second login had nothing to point to. A login to the web app with the same Telegram account, or a future email login, couldn't reach the learner of an existing chat.

When the web login was added, its cookie first held the `StudentID` itself (`student:{student_id}`).

## Decision

Keep two concepts apart:

- A **learner** is a `StudentID`, an opaque random id that addresses the record.
- A **login** is a provider (`telegram`, `browser`) with the identifier of that provider. `StudentIdentityStore` resolves a login to a learner.

In the code, a learner is a `StudentID`, and a login is a `(provider, identifier)` pair. Earlier discussions call them *account* and *credential*. Every frontend resolves a login before it uses a record. A logged-in browser holds a random `browser` token that is linked to the learner, not the `StudentID` ([#219](https://github.com/pauk-slon/immer-wiederholen/pull/219)). Anonymous web visitors aren't logins and aren't in the store.

## Alternatives considered

- **Derive ids for each provider** (the old scheme). This is simple, but one learner can never have two logins.
- **Introduce a separate `AccountID`.** `StudentID` already is the account. A second id type would be two names for one value.
- **Put the `StudentID` in the web cookie.** This saves one lookup. But a leaked cookie shows the permanent id, and a logout of one browser would mean a change of the learner's id.
- **Count anonymous visitors as logins.** Every page view would create a learner, and the size of the store would mean nothing.

## Consequences

- A learner who uses the bot and then logs in on the web gets the same record.
- A new way to log in is a new provider, not a new id scheme.
- Every request costs one more Redis lookup (observed, not discussed in #208).
- After the change of schemes, the records created under the old scheme had no learner. There were no real users to migrate yet.
