# Contributing

Before you start, read [Architecture](https://docs.immer-wiederholen.com/architecture/) on the [documentation site](https://docs.immer-wiederholen.com/).

## Setup

For local development, the repository comes with a Docker Compose setup ([`compose.yaml`](compose.yaml)) that runs the bot, the reminder, the web app and Valkey.

1. Create a separate bot for development with [@BotFather](https://t.me/BotFather) and put its token in `.env`:

   ```
   BOT_TOKEN=123456:ABC...
   ```

   A production bot's token won't do: only one process can poll a bot at a time, and the bot rewrites its Telegram profile on start (see [Configuration](docs/configuration.md#what-the-bot-changes-in-its-telegram-profile)).

2. Start the services with the demo course:

   ```bash
   docker compose up
   ```

To use another course, put it in `data/` and set `COURSE_PATH=data` in `.env`. The directory is gitignored, and the repository is mounted into the containers, so they see it.

## Running commands

The development tools are installed in the `bot` image, so run them through it:

```bash
docker compose run --rm bot pytest
docker compose run --rm bot ruff format .
docker compose run --rm bot ruff check . --fix
docker compose run --rm bot ty check .
docker compose run --rm bot uv add <package>
```

CI runs `ruff check`, `ty check` and `pytest` on every pull request, and builds the docs site (see [Documentation](#documentation)). All of these must pass. CI doesn't check formatting, so run `ruff format .` before committing.

## Tests

- **Tests run against a real Valkey server** (Redis-compatible), the one from `compose.yaml`, not a fake. `docker compose run` starts it by itself. To keep them away from your local data, all stores are pointed at database 15 for the test run (the `--redis-db-override` option in `pyproject.toml`), which is cleared before each test.
- **Coverage is 100%**, and we keep it there by agreement: CI doesn't fail on lower coverage, it only posts a report on the pull request. `pytest` prints the missing lines.
- **Mock objects are created with `spec=`**, so a test fails when the mocked interface changes. A single replaced function can be a plain `AsyncMock(return_value=...)`.
- **Dates are relative.** Fixtures use `date.today()` plus a `timedelta` rather than freezing time.
- Shared fixtures live in [`tests/plugins/`](tests/plugins).

To run part of the suite, pass pytest's usual arguments:

```bash
docker compose run --rm bot pytest tests/school/test_curriculum.py -k word_bank
```

## Documentation

The pages in [`docs/`](docs) are plain Markdown. They read on GitHub, and [Zensical](https://zensical.org/) also builds them into a site (see [ADR 0018](docs/adr/0018-docs-site-built-with-zensical.md)). To build the site once into `site/`, run:

```bash
docker compose run --rm bot zensical build --strict
```

To preview the site at `http://localhost:8001/` while you edit, run the command below. It rebuilds the site on every save.

```bash
docker compose run --rm -p 8001:8000 bot zensical serve -a 0.0.0.0:8000
```

With `--strict`, the build fails on a link to a missing page or heading. The check on pull requests uses the same flag. When you add a page, add an entry for it to `nav` in [`zensical.toml`](zensical.toml). A new ADR needs only a line in the [ADR index](docs/adr/README.md). The site contains only `docs/`. So a link from `docs/` to anything outside it, such as code, `demo/` or `CONTRIBUTING.md`, must be a GitHub URL.

### Writing style

The README, this file and the pages in `docs/` use simplified technical English, in the spirit of [ASD-STE100](https://www.asd-ste100.org/). The goal is text that is easy to read for everyone, including readers whose first language is not English.

- Write short sentences. Put one idea in each sentence.
- Use the active voice. Write instructions in the imperative.
- Use one term for one thing. Don't switch to a synonym later on the page.
- Prefer a simple verb to a phrasal verb or an idiom.
- Don't join clauses with semicolons, colons or dashes. Use a colon only before a list, a table or a code block.
- Describe what the project does. Don't state rules without a reason.

The strict STE dictionary doesn't apply. Code identifiers and terms such as span or middleware stay as they are. Accepted ADRs are never rewritten, so older ones may not follow this style.

## Pull requests

- Fork the repository, work on a branch, and open a pull request. `main` changes only through pull requests.
- Write titles and descriptions in English. Pull requests are squash-merged, and the title becomes the commit message on `main`, so write it as one. The messages of the commits inside don't matter.
- If a change affects the course format, configuration or architecture, update the matching page in [`docs/`](docs) in the same pull request.
- A significant design decision, one with real alternatives that would be costly to reverse, gets an [architecture decision record](docs/adr/README.md) in the same pull request.
- A course format change also needs [`demo/`](demo) updated: a test checks that it uses every field and setting.
- Dependabot updates `uv.lock` weekly. If your pull request conflicts there, take the version from `main` and re-run `uv lock` (or your `uv add`) rather than merging the file by hand.

## Issues and security

Report bugs and ideas as [GitHub issues](https://github.com/pauk-slon/immer-wiederholen/issues). Report security problems privately, through a [security advisory](https://github.com/pauk-slon/immer-wiederholen/security/advisories/new), not an issue.

Contributions are licensed under the [MIT license](LICENSE), like the rest of the project.
