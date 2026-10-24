# Immer wiederholen!

A Telegram bot and an embeddable web widget for practicing grammar with spaced repetition. *Immer wiederholen* is German for "always repeat". The course is plain YAML; the one it runs today is German, with explanations and the interface in Russian and English.

[![Telegram](https://img.shields.io/badge/Telegram-@ImmerWiederholenBot-2CA5E0?logo=telegram&logoColor=white)](https://t.me/ImmerWiederholenBot)

## Features

- **Spaced repetition per word and topic.** A wrong or first answer brings an exercise back the same day; after that, each correct answer doubles the wait, up to 60 days. Up to seven new words a day, more on request.
- **Linked topics.** Answering one topic for a word can bring a related topic forward, or unlock one that stays hidden until then — e.g. a verb's Partizip II before sentences that use it.
- **Multiple-choice questions with explanations**, hints that point to a well-known word with the same grammar ("Same as for …"), and recalls: a follow-up sentence to write out in full, required after a wrong answer.
- **Reminders** a set time after the last session, topic selection, and a progress summary.
- **A web widget** for embedding on landing pages, plus a standalone web app; logging in with Telegram shares progress with the bot. Hints, reminders, topic selection and AI content are bot-only for now.
- **Optional AI content:** illustrations shown with sentence exercises, and an experimental mode where Claude rewrites questions.

## Quickstart

You need Docker and a Telegram bot for development, created with [@BotFather](https://t.me/BotFather). Don't use a production bot's token: see [CONTRIBUTING.md](CONTRIBUTING.md#setup) for why. Put the token in `.env`:

```
BOT_TOKEN=123456:ABC...
```

Then start everything:

```bash
docker compose up
```

This starts the bot, the reminder, the web app and Valkey with the demo course from [`demo/`](demo): a few German exercises that use every feature of the course format. Open your bot in Telegram, press Start, then send `/wiederholen` for the first exercise. To open the web app locally, see [Web frontend](docs/web-frontend.md#running-locally).

To run your own course, put it in `data/` (gitignored; the repo is mounted into the containers) and set `COURSE_PATH=data` in `.env`. The files it needs are described in [Course format](docs/course-format.md).

## Documentation

Course authors need [Course format](docs/course-format.md): `exercises.yaml`, `topics.yaml` and `bot.yaml`. Operators need [Configuration](docs/configuration.md): processes, environment variables and optional integrations.

Contributors should start with [CONTRIBUTING.md](CONTRIBUTING.md), then:

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
