# Contributing

## Setup

The project provides a Docker Compose configuration ([`compose.yaml`](compose.yaml)) for a local environment: the bot, the reminder, the web app and Valkey, each in its own container.

1. Create a bot for development with [@BotFather](https://t.me/BotFather) and put its token in `.env`:

   ```
   BOT_TOKEN=123456:ABC...
   ```

2. Start the environment with the demo course:

   ```bash
   docker compose up
   ```

Don't use a production bot's token: only one process can poll a bot at a time, and the bot rewrites its Telegram profile on start (see [Configuration](docs/configuration.md#what-the-bot-changes-in-its-telegram-profile)).

To use another course, put it in `data/` (gitignored; the repo is mounted into the containers) and set `COURSE_PATH=data` in `.env`.

## Running commands

All commands run inside the `bot` container:

```bash
docker compose run --rm bot pytest
docker compose run --rm bot ruff format .
docker compose run --rm bot ruff check . --fix
docker compose run --rm bot ty check .
docker compose run --rm bot uv add <package>
```

CI runs `ruff check`, `ty check` and `pytest` on every pull request, and builds the docs site (see [Documentation](#documentation)); all must pass. CI doesn't check formatting, so run `ruff format .` before committing.

`docker compose run` starts Valkey for the tests by itself. To run part of the suite, pass pytest's usual arguments:

```bash
docker compose run --rm bot pytest tests/school/test_curriculum.py -k word_bank
```

## Tests

- **Tests use a real Redis**, the Valkey container from `compose.yaml`, not a fake. To keep them away from your local data, all stores are pointed at database 15 for the test run (the `--redis-db-override` option in `pyproject.toml`), which is cleared before each test.
- **Coverage is 100%**, and we keep it there by agreement: CI doesn't fail on lower coverage, it only posts a report on the pull request. `pytest` prints the missing lines.
- **Mock objects are created with `spec=`**, so a test fails when the mocked interface changes. A single replaced function can be a plain `AsyncMock(return_value=...)`.
- **Dates are relative.** Fixtures use `date.today()` plus a `timedelta` rather than freezing time.
- Shared fixtures live in [`tests/plugins/`](tests/plugins).

## Documentation

The pages in [`docs/`](docs) are plain Markdown that reads on GitHub and is also built into a site with [Zensical](https://zensical.org/) (see [ADR 0018](docs/adr/0018-docs-site-built-with-zensical.md)). To build it once, into `site/`:

```bash
docker compose run --rm bot zensical build --strict
```

To preview it at `http://localhost:8001/` while editing, rebuilt on every save:

```bash
docker compose run --rm -p 8001:8000 bot zensical serve -a 0.0.0.0:8000
```

`--strict` fails on a link to a missing page or heading, as the check on pull requests does. A new page needs an entry in `nav` in [`zensical.toml`](zensical.toml); a new ADR only needs a line in the [ADR index](docs/adr/README.md). Links from `docs/` to anything outside it — code, `demo/`, `CONTRIBUTING.md` — are GitHub URLs, since the site contains only `docs/`.

## Pull requests

- Fork the repository, work on a branch, and open a pull request; `main` changes only through pull requests.
- Write titles and descriptions in English.
- If a change affects the course format, configuration or architecture, update the matching page in [`docs/`](docs) in the same pull request. A significant design decision — one with real alternatives that would be costly to reverse — also gets an [architecture decision record](docs/adr/README.md) in the same pull request. A course format change also needs [`demo/`](demo) updated: a test checks that it uses every field and setting.
- Expect weekly Dependabot pull requests for Python packages and GitHub Actions.

## Issues and security

Report bugs and ideas as [GitHub issues](https://github.com/pauk-slon/immer-wiederholen/issues). Report security problems privately, through a [security advisory](https://github.com/pauk-slon/immer-wiederholen/security/advisories/new), not an issue.

Contributions are licensed under the [MIT license](LICENSE), like the rest of the project.

## Where to start

- [Architecture](docs/architecture.md) — how the code is organized.
- [Course format](docs/course-format.md) — what the YAML files look like.
- [Configuration](docs/configuration.md) — the environment variables.
