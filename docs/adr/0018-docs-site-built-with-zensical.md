# 0018. The docs site is built with Zensical

**Status:** Accepted, 2026-10-24 ([#265](https://github.com/pauk-slon/immer-wiederholen/pull/265))

## Context

The pages under `docs/` are plain Markdown that reads well on GitHub. They use relative links between pages and GitHub URLs for links to code, so that a site generator can build them later without changes ([#244](https://github.com/pauk-slon/immer-wiederholen/issues/244)). On GitHub, the pages have no navigation between them and no search. Nothing checks that a link still points to an existing page or heading.

## Decision

[Zensical](https://zensical.org/) builds the site from `zensical.toml`, and `.github/workflows/docs.yml` publishes it to GitHub Pages. The same workflow builds the site with `--strict` on every pull request, so a broken link or anchor fails the check. The Markdown stays readable on GitHub, because nothing in `docs/` depends on the site.

## Alternatives considered

- **Material for MkDocs.** This is the theme that the authors of Zensical made before Zensical. It is mature, but it has been in maintenance mode since November 2025. Its authors promise fixes only until November 2026, and new work goes into Zensical.
- **Keep the docs only on GitHub.** This needs no extra tools, but gives no search, no navigation and no link checks.

Other generators, such as Sphinx and Docusaurus, weren't evaluated. The choice was between the two options above from the start.

## Consequences

- Zensical is still before version 1.0, so an upgrade can break the build. `uv.lock` pins it (in the `dev` dependency group), so an upgrade comes in a pull request, where the strict build shows any problem.
- Every page under `docs/` needs a `nav` entry in `zensical.toml`. Individual ADRs are the exception, because readers reach them from their index.
- Links from `docs/` to files outside it (`CONTRIBUTING.md`, `demo/`, code) must be GitHub URLs, because the site contains only `docs/`.
