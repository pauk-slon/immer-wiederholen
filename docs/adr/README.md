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

| ADR | Decision | Date | Status |
|---|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | 2026-10-24 | Accepted |
| [0002](0002-tutoring-events-on-the-current-span.md) | The repetition engine reports events on the current span | 2026-08-23 | Accepted |
| [0003](0003-separate-accounts-from-logins.md) | Separate learners from the ways they log in | 2026-09-19 | Accepted |
| [0004](0004-links-only-schedule-unstarted-pairs.md) | Topic links only schedule pairs that haven't started | 2026-07-29 | Accepted |
| [0005](0005-shadow-exercises-keep-the-answer.md) | Shadow exercises keep the answer | 2026-08-14 | Accepted |
| [0006](0006-ai-generation-fails-visibly.md) | AI generation fails visibly, without a fallback | 2026-08-10 | Accepted |
