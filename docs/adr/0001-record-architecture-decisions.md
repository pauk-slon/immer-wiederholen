# 0001. Record architecture decisions

**Status:** Accepted, 2026-10-24 ([#260](https://github.com/pauk-slon/immer-wiederholen/pull/260), part of [#244](https://github.com/pauk-slon/immer-wiederholen/issues/244))

## Context

The reasons behind the project's design used to be in `CLAUDE.md`, which is written for AI agents. Its long paragraphs mixed how something works with how it came to be, such as "an earlier version did X, which broke Y". These notes then moved into pages for people under `docs/`. The reference text became clearer, but the history had two options. The pages could drop it, or they could keep it in "Design notes" that would grow without limit. If the pages drop the history, the reasons behind non-obvious choices are lost. If the pages keep it, they are harder to read, and they mix facts that change with facts that don't.

## Decision

Record significant decisions as architecture decision records in `docs/adr/`. Use the format of [Michael Nygard's ADRs](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions) with an extra "Alternatives considered" section. Reference pages describe the current state and link to the ADRs for the reasons.

Decisions from before this one are recorded afterwards. Each such ADR has the date of its original pull request and a link to it. Short lessons from bugs stay next to the behavior that they protect and get no ADR.

## Alternatives considered

- **Keep "Design notes" in each page.** This needs no new structure. But the notes keep growing, and they can't show that a later decision replaced an earlier one.
- **Rely on pull requests and issues.** The history is there, but a reader can't find it without knowing which pull request to look for.

## Consequences

- Reference pages get shorter and describe only what is true now.
- A reader can find the reasons for a decision without a search through pull requests.
- An ADR is one more step in a significant change.
- An ADR written afterwards is only as good as the pull requests that it is based on. If nobody wrote down the reasons, the ADR says so and doesn't invent them. It also marks an observation that nobody discussed at the time.
