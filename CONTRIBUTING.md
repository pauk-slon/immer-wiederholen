# Contributing

## Setup

You need Docker. Everything else — Python, dependencies, Redis — runs in containers.

1. Create a bot for development with [@BotFather](https://t.me/BotFather) and put its token in `.env`:

   ```
   BOT_TOKEN=123456:ABC...
   ```

2. Start the bot, the reminder, the web app and Valkey with the demo course:

   ```bash
   docker compose up
   ```

Don't use a production bot's token: only one process can poll a bot at a time, and the bot rewrites its Telegram profile on start (see [Configuration](docs/configuration.md#what-the-bot-changes-in-its-telegram-profile)).

To use another course, set `COURSE_PATH` in `.env` and mount the course directory in a `compose.override.yaml` (gitignored).

## Running commands

All commands run inside the `bot` container:

```bash
docker compose run --rm bot pytest
docker compose run --rm bot ruff format .
docker compose run --rm bot ruff check . --fix
docker compose run --rm bot ty check .
docker compose run --rm bot uv add <package>
```

CI runs `ruff check`, `ty check` and `pytest` on every pull request; all three must pass.

## Tests

- **Tests use a real Redis**, the Valkey container from `compose.yaml`, not a fake. To keep them away from your local data, all stores are pointed at database 15 for the test run (the `--redis-db-override` option in `pyproject.toml`), which is cleared before each test.
- **Coverage is 100%**, and should stay so. `pytest` prints the missing lines, and CI posts a coverage report on the pull request.
- **Mocks are created with `spec=`**, so a test fails when the mocked interface changes.
- **Dates are relative.** Fixtures use `date.today()` plus a `timedelta` rather than freezing time.
- Shared fixtures live in [`tests/plugins/`](tests/plugins).

## Pull requests

- Work on a branch; `main` changes only through pull requests.
- Write titles and descriptions in English.
- If a change affects the course format, configuration or architecture, update the matching page in [`docs/`](docs) in the same pull request. A course format change also needs [`demo/`](demo) updated: a test checks that it uses every field and setting.
- Dependabot opens weekly updates for Python packages and GitHub Actions.

## Where to start

- [Architecture](docs/architecture.md) — how the code is organized.
- [Course format](docs/course-format.md) — what the YAML files look like.
- [Configuration](docs/configuration.md) — the environment variables.
