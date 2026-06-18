# immer-wiederholen

Telegram bot for practicing German with multiple choice questions (aiogram, Python). Cards are loaded at startup from the path set by `CARDS_PATH` env var (default: `data/cards.yaml`). Bot commands: `/start`, `/wiederholen` (show a card with answer options), `/language` (toggle ru/en).

## Key modules

- `wiederholen.cards` — card domain: `Card` dataclass, loading from YAML, random picking
- `wiederholen.i18n` — supported languages (`Language` type, `LANGUAGES` set)
- `wiederholen.bot` — Telegram bot implementation (aiogram)

## Commands

All commands run inside the Docker container:

```bash
docker compose run --rm bot <command>
```

Examples:
- `docker compose run --rm bot ruff check . --fix`
- `docker compose run --rm bot ty check .`
- `docker compose run --rm bot uv add <package>`
- `docker compose run --rm bot pytest`
