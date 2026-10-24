# Contributing

Before you start, read [Architecture](https://docs.immer-wiederholen.com/architecture/) on the [documentation site](https://docs.immer-wiederholen.com/).

## Setup

The repository has a Docker Compose setup ([`compose.yaml`](compose.yaml)) for local development. It runs the bot, the reminder, the web app and Valkey.

1. Create a separate bot for development with [@BotFather](https://t.me/BotFather) and put its token in `.env`:

   ```
   BOT_TOKEN=123456:ABC...
   ```

   Don't use a production bot's token. Only one process can poll a bot at a time, so a local run would interrupt the production bot. The bot also rewrites its Telegram profile on start, so a local run would change the production profile (see [Configuration](docs/configuration.md#what-the-bot-changes-in-its-telegram-profile)).

2. Start the services with the demo course:

   ```bash
   docker compose up
   ```

To use another course, put it in `data/` and set `COURSE_PATH=data` in `.env`. Git ignores `data/`. Compose mounts the repository into the containers, so the services can read the course.

## Running commands

The development tools are installed in the `bot` image, so run them through it:

```bash
docker compose run --rm bot pytest
docker compose run --rm bot ruff format .
docker compose run --rm bot ruff check . --fix
docker compose run --rm bot ty check .
docker compose run --rm bot uv add <package>
```

CI runs `ruff check`, `ty check` and `pytest` on every pull request, and builds the docs site (see [Documentation](#documentation)). All of these must pass. CI doesn't check formatting, so run `ruff format .` before you commit.

## Tests

- **Tests use the real Valkey server from `compose.yaml`** (Redis-compatible), not a fake, so they check real Redis behavior. `docker compose run` starts it automatically. All stores use database 15 during the test run (the `--redis-db-override` option in `pyproject.toml`), so the tests don't touch your local data. Each test starts with an empty database 15.
- **Keep coverage at 100%.** CI doesn't enforce it and only posts a coverage report on the pull request. `pytest` prints the lines that the tests don't cover.
- **Create mock objects with `spec=`**, so a test fails when the mocked interface changes. A mock for a single replaced function can be a plain `AsyncMock(return_value=...)`.
- **Use relative dates.** Fixtures use `date.today()` plus a `timedelta`, so the tests need no library that freezes time.
- **Put shared fixtures in [`tests/plugins/`](tests/plugins).**

To run part of the suite, pass pytest's usual arguments:

```bash
docker compose run --rm bot pytest tests/school/test_curriculum.py -k word_bank
```

## Documentation

The pages in [`docs/`](docs) are plain Markdown. You can read them on GitHub, and [Zensical](https://zensical.org/) also builds them into a site (see [ADR 0018](docs/adr/0018-docs-site-built-with-zensical.md)). To build the site once into `site/`, run:

```bash
docker compose run --rm bot zensical build --strict
```

To preview the site at `http://localhost:8001/` while you edit, run the command below. It rebuilds the site on every save.

```bash
docker compose run --rm -p 8001:8000 bot zensical serve -a 0.0.0.0:8000
```

With `--strict`, the build fails on a link to a missing page or heading. The check on pull requests uses the same flag. When you add a page, add an entry for it to `nav` in [`zensical.toml`](zensical.toml). ADRs are not in `nav`. A new ADR needs only a line in the [ADR index](docs/adr/README.md). The site contains only `docs/`, so a link from `docs/` to anything outside it, such as code, `demo/` or `CONTRIBUTING.md`, must be a GitHub URL.

### Writing style

The README, this file and the pages in `docs/` use simplified technical English, in the spirit of [ASD-STE100 Simplified Technical English](https://www.asd-ste100.org/) (STE). Short, simple sentences are easier to read, especially for readers whose first language is not English.

- Write short sentences. Put one idea in each sentence.
- Prefer the active voice. Write instructions in the imperative.
- Use one term for one thing. Don't switch to a synonym later on the page.
- Prefer a simple verb to a phrasal verb or an idiom (remove, not take out).
- Don't join clauses with semicolons, colons or dashes. Use a colon only before a list, a table or a code block.
- Connect the sentences in a paragraph by meaning. Don't list unrelated facts.
- Name the things you mean. Avoid vague words such as everything.
- Give the reason for a rule, not only the rule.

The strict STE dictionary doesn't apply. Code identifiers and terms such as span or middleware stay as they are. Accepted ADRs are never rewritten, so older ones may not follow this style.

## Pull requests

- Fork the repository and work on a branch. Then open a pull request. `main` changes only through pull requests.
- Write titles and descriptions in English. Write the title as a commit message, because the squash merge makes it the commit message on `main`. The messages of the commits inside the pull request don't matter.
- If a change affects the course format, configuration or architecture, update the matching page in [`docs/`](docs) in the same pull request.
- If a design decision has real alternatives and would be costly to reverse, write an [architecture decision record](docs/adr/README.md) for it in the same pull request.
- If you change the course format, also update [`demo/`](demo). A test checks that the demo course uses every field and setting.
- Dependabot updates `uv.lock` weekly. If your pull request conflicts there, take the version from `main` and re-run `uv lock` (or your `uv add`) rather than merging the file by hand. A lock file merged by hand often doesn't match `pyproject.toml`.

## Issues and security

Report bugs and ideas as [GitHub issues](https://github.com/pauk-slon/immer-wiederholen/issues). Report security problems privately, through a [security advisory](https://github.com/pauk-slon/immer-wiederholen/security/advisories/new), not an issue.

Contributions are licensed under the [MIT license](LICENSE), like the rest of the project.
