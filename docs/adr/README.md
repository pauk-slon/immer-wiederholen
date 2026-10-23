# Architecture decision records

An architecture decision record (ADR) is a short document about one significant decision: what problem it solved, what was chosen, what else was considered, and what follows from it. The reference pages in `docs/` describe how things work now; ADRs keep the reasons and the history, so the reference pages don't have to.

## When to write one

Write an ADR for a decision that had real alternatives and would be costly or risky to reverse — the kind a newcomer might "fix" without knowing why it's that way. A one-line lesson from a bug (a CSS rule, a fixed size) doesn't need one: it belongs next to the behavior it protects, in the reference page or a code comment.

A new decision gets its ADR in the same pull request that makes it.

## Format

Files are named `NNNN-short-title.md`, numbered in order of writing. Each has:

- **Status** — `Accepted`, or `Superseded by NNNN`, with the date and the pull request that made the decision;
- **Context** — the situation and the problem;
- **Decision** — what was chosen;
- **Alternatives considered** — what else was on the table and why it lost;
- **Consequences** — what follows, good and bad.

ADRs aren't rewritten. When a decision changes, write a new ADR and mark the old one `Superseded by NNNN`.

The decisions made before ADRs existed are recorded after the fact, from their pull requests and issues, and dated by them.

## Index

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-tutoring-events-on-the-current-span.md) | The repetition engine reports events on the current span | Accepted |
| [0003](0003-separate-accounts-from-logins.md) | Separate learners from the ways they log in | Accepted |
| [0004](0004-links-only-schedule-unstarted-pairs.md) | Topic links only schedule pairs that haven't started | Accepted |
| [0005](0005-shadow-exercises-keep-the-answer.md) | Shadow exercises keep the answer and never fall back | Accepted |
