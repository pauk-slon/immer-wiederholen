# Immer wiederholen!

Telegram bot for practicing language grammar using spaced repetition.

[![Telegram](https://img.shields.io/badge/Telegram-@ImmerWiederholenBot-2CA5E0?logo=telegram&logoColor=white)](https://t.me/ImmerWiederholenBot)

## Spaced repetition implementation

Each exercise has a due date:

- A wrong answer makes the exercise due again today.
- A correct answer pushes the due date further away, doubling the wait each time, up to a maximum of 60 days.

## Development

Set the `BOT_TOKEN` environment variable with your Telegram bot token (e.g. via `.env` file).

Start the bot:

```bash
docker compose up
```

Locally the bot runs the small demo course from [`demo/`](demo): a handful of German exercises that use every field and topic setting the course format supports, with comments explaining them. To run your own course, point `COURSE_PATH` at a directory with the same files (e.g. `COURSE_PATH=data` in `.env`):

- `exercises.yaml` — the exercises (required)
- `topics.yaml` — topic groups and the relations between topics (optional)
- `bot.yaml` — the bot's Telegram name and descriptions (optional)

The format is described in [docs/course-format.md](docs/course-format.md); environment variables and optional integrations in [docs/configuration.md](docs/configuration.md).

Tests:

```bash
docker compose run --rm bot pytest .
```

Linting and formatting:

```bash
docker compose run --rm bot ruff format .
docker compose run --rm bot ruff check . --fix
docker compose run --rm bot ty check .
```
