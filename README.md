# immer-wiederholen

Telegram bot for memorizing foreign words using spaced repetition.

## Development

Set the `BOT_TOKEN` environment variable with your Telegram bot token (e.g. via `.env` file).

Start the bot:

```bash
docker compose up
```

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
