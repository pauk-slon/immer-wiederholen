# Immer wiederholen!

A Telegram bot and an embeddable web widget for practicing grammar with spaced repetition. The course is plain YAML, so the engine isn't tied to one language; the course it runs today is German, with the interface in Russian and English.

[![Telegram](https://img.shields.io/badge/Telegram-@ImmerWiederholenBot-2CA5E0?logo=telegram&logoColor=white)](https://t.me/ImmerWiederholenBot)

## Features

- **Spaced repetition per word and topic.** A wrong answer brings an exercise back the same day; each correct answer doubles the wait, up to 60 days. New words are introduced a few a day.
- **Linked topics.** Answering one topic for a word can bring a related topic forward, or unlock one that stays hidden until then — e.g. a verb's Partizip II before sentences that use it.
- **Multiple-choice questions with explanations**, and recalls: a follow-up sentence to write out in full, required after a wrong answer.
- **Reminders** a set time after the last session, topic selection, and a progress summary.
- **A web widget** for embedding on landing pages, plus a standalone web app; logging in with Telegram shares progress with the bot.
- **Optional AI content:** illustrations generated ahead of time for sentence exercises, and an experimental mode where Claude rewrites questions.

## Quickstart

You need Docker and a Telegram bot token for development from [@BotFather](https://t.me/BotFather) — not a production bot's token, since the bot rewrites its Telegram profile on start.

```bash
echo "BOT_TOKEN=123456:ABC..." > .env
docker compose up
```

This starts the bot, the reminder, the web app and Valkey with the demo course from [`demo/`](demo): a few German exercises that use every feature of the course format. Send `/wiederholen` to your bot to get the first exercise. To open the web app locally, see [Web frontend](docs/web-frontend.md#running-locally).

To run your own course, put it in `data/` and set `COURSE_PATH=data` in `.env`.

## Documentation

For course authors:

- [Course format](docs/course-format.md) — `exercises.yaml`, `topics.yaml` and `bot.yaml`

For operators:

- [Configuration](docs/configuration.md) — processes, environment variables, optional integrations

For contributors — start with [CONTRIBUTING.md](CONTRIBUTING.md):

- [Architecture](docs/architecture.md) — packages, processes and where state lives
- [Repetition schedule](docs/repetition-schedule.md) — how the next exercise is picked
- [Storage and identity](docs/storage.md)
- [Telegram bot](docs/bot.md)
- [Web frontend](docs/web-frontend.md)
- [AI-generated content](docs/authoring.md)
- [Tracing](docs/tracing.md)
- [Architecture decision records](docs/adr/README.md) — why things are the way they are

## License

[MIT](LICENSE)
