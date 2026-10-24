# 0018. The docs site is built with Zensical

**Status:** Accepted, 2026-10-24 ([#265](https://github.com/pauk-slon/immer-wiederholen/pull/265))

## Context

The pages under `docs/` are plain Markdown written to read well on GitHub, with relative links between them and links to code as GitHub URLs, so that a site generator could build them later without changes ([#244](https://github.com/pauk-slon/immer-wiederholen/issues/244)). Read on GitHub, they have no navigation across pages, no search, and nothing checks that a link still points at an existing page or heading.

## Decision

The site is built with [Zensical](https://zensical.org/) from `zensical.toml` and published to GitHub Pages by `.github/workflows/docs.yml`. The same workflow builds it with `--strict` on every pull request, so a broken link or anchor fails the check. The Markdown stays readable on GitHub: nothing in `docs/` depends on the site.

## Alternatives considered

- **Material for MkDocs**, the theme Zensical's authors made before it. It's mature, but it has been in maintenance mode since November 2025, with fixes promised only until November 2026; new work goes into Zensical.
- **Keeping the docs on GitHub only.** No extra tooling, but no search, no navigation and no link checks.

Other generators (Sphinx, Docusaurus) weren't evaluated: the choice was between the two above from the start.

## Consequences

- Zensical is still before 1.0; an upgrade can break the build. It's pinned in `uv.lock` (the `docs` dependency group), so that happens only in a Dependabot pull request, where the strict build shows it.
- Every page under `docs/` needs a `nav` entry in `zensical.toml`, except individual ADRs, which are reached from their index.
- Links that leave `docs/` (`CONTRIBUTING.md`, `demo/`, code) must be GitHub URLs: the site sees only `docs/`.
