# Immer wiederholen!

A project for creating Telegram bots for practicing grammar with spaced repetition. You bring the course, written in YAML, and the bot handles the teaching. It keeps track of what each learner knows and brings every exercise back just before it would be forgotten. The exercises can also be embedded on any web page as a widget.

For example, [@ImmerWiederholenBot](https://t.me/ImmerWiederholenBot) teaches German grammar.

## Features

- **Spaced repetition per word and topic.** A wrong or first answer brings an exercise back the same day. After that, each correct answer doubles the wait, up to 60 days. Up to seven new words a day, more on request.
- **Linked topics.** Answering one topic for a word can bring a related topic forward, or unlock one that stays hidden until then. For example, a verb's Partizip II comes before the sentences that use it.
- **Multiple-choice questions with explanations and hints.** A hint points to a well-known word with the same grammar ("Same as for …").
- **Recalls.** Some exercises are followed by a recall, where the learner writes out a whole sentence with the word. After a wrong answer, the recall is required.
- **Reminders, topic selection and a progress summary** in the bot.
- **The web widget and a standalone web app.** Logging in with Telegram shares progress with the bot. Hints, reminders, topic selection and AI content are only in the bot for now.
- **Optional AI content**, with illustrations for sentence exercises and an experimental mode where Claude rewrites questions.

## Quickstart

You need Docker and a Telegram bot for development, created with [@BotFather](https://t.me/BotFather). Don't use a production bot's token. [CONTRIBUTING.md](CONTRIBUTING.md#setup) explains why. Put the token in `.env`:

```
BOT_TOKEN=123456:ABC...
```

Then start the services:

```bash
docker compose up
```

This starts the bot, the reminder, the web app and Valkey with the demo course from [`demo/`](demo), a few German exercises that use every feature of the course format. Open your bot in Telegram, press Start, then send `/wiederholen` for the first exercise.

To run your own course, see [CONTRIBUTING.md](CONTRIBUTING.md#setup). To open the web app locally, see [Web frontend](docs/web-frontend.md#running-locally).

## Documentation

The documentation is at [docs.immer-wiederholen.com](https://docs.immer-wiederholen.com/), built from [`docs/`](docs). Where to start:

- [Course format](docs/course-format.md) for course authors
- [Configuration](docs/configuration.md) for operators
- [CONTRIBUTING.md](CONTRIBUTING.md) and then [Architecture](docs/architecture.md) for contributors

## License

[MIT](LICENSE)
