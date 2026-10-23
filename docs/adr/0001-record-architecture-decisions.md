# 0001. Record architecture decisions

**Status:** Accepted, 2026-10-24 ([#244](https://github.com/pauk-slon/immer-wiederholen/issues/244))

## Context

The project's reasoning used to live in `CLAUDE.md`, written for AI agents: long paragraphs mixing how something works with how it came to be — "an earlier version did X, which broke Y". When those notes moved into human-readable pages under `docs/`, the reference text got clearer, but the history either had to be dropped or kept as ever-growing "Design notes". Dropping it loses the reasons behind non-obvious choices; keeping it inline makes the reference pages harder to read and mixes facts that change with facts that don't.

## Decision

Record significant decisions as architecture decision records in `docs/adr/`, in the format of [Michael Nygard's ADRs](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions) with an added "Alternatives considered" section. Reference pages describe the current state and link to the ADRs for the reasons.

Decisions made before this one are recorded retroactively, each dated by and linked to its original pull request. One-line lessons from bugs stay next to the behavior they protect instead of getting ADRs.

## Alternatives considered

- **Keep "Design notes" in each page.** No new structure, but the notes keep growing, and there's no way to show that a decision was later replaced.
- **Rely on pull requests and issues.** The history is there, but nobody finds it without knowing which pull request to look for.

## Consequences

- Reference pages get shorter and describe only what is true now.
- A decision's reasons can be found without digging through pull requests.
- Writing an ADR is one more step when making a significant change.
- Retroactive ADRs are only as good as the pull requests they're reconstructed from; where the reasons weren't written down, the ADR says so instead of inventing them.
