# 0003. Separate learners from the ways they log in

**Status:** Accepted, 2026-09-19 ([#208](https://github.com/pauk-slon/immer-wiederholen/pull/208)); extended to browser logins 2026-09-20 ([#219](https://github.com/pauk-slon/immer-wiederholen/pull/219))

## Context

A learner's record is addressed by a `StudentID`. The bot used to derive it from the Telegram chat id (`TelegramStudentID.encode(chat_id)`), which tied "who is this learner" to "which chat is this". That worked while Telegram was the only way in, but left nowhere for a second login to point: logging in to the web app with the same Telegram account, or a future email login, couldn't reach the learner a chat already had.

When web login was added, its cookie first carried the `StudentID` itself (`student:{student_id}`).

## Decision

Keep two concepts apart:

- a **learner** is a `StudentID`, an opaque random id that addresses the record;
- a **login** is a provider (`telegram`, `browser`) plus that provider's identifier, and is resolved to a learner by `StudentIdentityStore`.

In code, a learner is a `StudentID` and a login is a `(provider, identifier)` pair; earlier discussions call them *account* and *credential*. Every frontend resolves a login before touching a record. A logged-in browser holds a random `browser` token, linked to the learner, not the `StudentID` ([#219](https://github.com/pauk-slon/immer-wiederholen/pull/219)). Anonymous web visitors aren't logins and stay out of the store.

## Alternatives considered

- **Derive ids per provider** (the old scheme). Simple, but one learner can never have two logins.
- **Introduce a separate `AccountID`.** `StudentID` already is the account; a second id type would be two names for one value.
- **Put the `StudentID` in the web cookie.** One lookup fewer, but a leaked cookie reveals the permanent id, and logging one browser out would mean changing the learner's id.
- **Count anonymous visitors as logins.** Every page view would become a learner, making the store's size meaningless.

## Consequences

- A learner who uses the bot and then logs in on the web lands on the same record.
- New ways to log in are a new provider, not a new id scheme.
- Every request costs one more Redis lookup (observed, not discussed in #208).
- Switching schemes orphaned the records created under the old one; there were no real users to migrate yet.
