# Architecture decision records

An architecture decision record (ADR) is a short document about one significant decision: what problem it solved, what was chosen, what else was considered, and what follows from it. The reference pages in `docs/` describe how things work now; ADRs keep the reasons and the history, so the reference pages don't have to.

## When to write one

Write an ADR for a decision that had real alternatives and would be costly or risky to reverse — the kind a newcomer might "fix" without knowing why it's that way. A one-line lesson from a bug (a CSS rule, a fixed size) doesn't need one: it belongs next to the behavior it protects, in the reference page or a code comment.

A new decision gets its ADR in the same pull request that makes it.

## Format

Files are named `NNNN-short-title.md`, numbered in order of writing. Each has:

- **Status** — `Accepted` once the pull request that makes the decision is merged, or `Superseded by NNNN`; with the date and that pull request;
- **Context** — the situation and the problem;
- **Decision** — what was chosen;
- **Alternatives considered** — what else was on the table and why it lost;
- **Consequences** — what follows, good and bad.

ADRs aren't rewritten. When a decision changes, write a new ADR and mark the old one `Superseded by NNNN`.

The decisions made before ADRs existed are recorded after the fact, from their pull requests and issues, and dated by them.

## Index

Numbers follow the order of writing; the date is when the decision was made.

### Process

| ADR | Decision | Date | Status |
|---|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | 2026-10-24 | Accepted |
| [0018](0018-docs-site-built-with-zensical.md) | The docs site is built with Zensical | 2026-10-24 | Accepted |

### Repetition engine and course format

| ADR | Decision | Date | Status |
|---|---|---|---|
| [0002](0002-tutoring-events-on-the-current-span.md) | The repetition engine reports events on the current span | 2026-08-23 | Accepted |
| [0004](0004-links-only-schedule-unstarted-pairs.md) | Topic links only schedule pairs that haven't started | 2026-07-29 | Accepted |
| [0012](0012-gates-declared-explicitly.md) | Gates are declared explicitly | 2026-07-22 | Accepted |
| [0013](0013-word-bank-as-data.md) | Word banks are data, not text in the question | 2026-08-26 | Accepted |

### Storage and identity

| ADR | Decision | Date | Status |
|---|---|---|---|
| [0003](0003-separate-accounts-from-logins.md) | Separate learners from the ways they log in | 2026-09-19 | Accepted |
| [0007](0007-save-records-only-when-changed.md) | Save a student record only when it changes | 2026-08-23 | Accepted |
| [0008](0008-student-record-separate-from-chat-state.md) | Keep the student record separate from chat state | 2026-08-23 | Accepted |
| [0009](0009-one-environment-variable-per-store.md) | One environment variable per store | 2026-08-23 | Accepted |

### Telegram bot

| ADR | Decision | Date | Status |
|---|---|---|---|
| [0010](0010-reminders-as-a-separate-process.md) | Reminders run as a separate process | 2026-07-19 | Accepted |
| [0011](0011-remind-after-the-last-session.md) | Reminders count from the last session | 2026-10-15 | Accepted |

### Web frontend

| ADR | Decision | Date | Status |
|---|---|---|---|
| [0015](0015-web-component-not-iframe.md) | The web widget is a web component, not an iframe | 2026-08-23 | Accepted |
| [0016](0016-web-sessions-keyed-by-topics.md) | Web sessions are keyed by learner and topics | 2026-08-26 | Accepted |

### AI-generated content

| ADR | Decision | Date | Status |
|---|---|---|---|
| [0005](0005-shadow-exercises-keep-the-answer.md) | Shadow exercises keep the answer | 2026-08-14 | Accepted |
| [0006](0006-ai-generation-fails-visibly.md) | AI generation fails visibly, without a fallback | 2026-08-10 | Accepted |
| [0014](0014-cues-generated-ahead.md) | Illustrations are generated ahead of time | 2026-10-17 | Accepted |
| [0017](0017-cues-keyed-by-question-hash.md) | Illustrations are keyed by the question's hash | 2026-10-17 | Accepted |
