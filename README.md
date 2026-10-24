# Immer wiederholen!

A project for creating Telegram bots that teach grammar with spaced repetition. You write the course in YAML, and the bot teaches it. It tracks what each learner knows and shows each exercise again shortly before the learner would forget it. You can also embed the exercises on any web page as a widget.

## Example

A German grammar course runs on this project. You can try it in Telegram or on the web:

- [@ImmerWiederholenBot](https://t.me/ImmerWiederholenBot), the bot
- [web.immer-wiederholen.com](https://web.immer-wiederholen.com/), the web app
- [immer-wiederholen.com](https://immer-wiederholen.com/), grammar pages with the exercises embedded as widgets

## Features

- **Spaced repetition per word and topic.** A first or wrong answer makes the exercise due again the same day. After that, each correct answer doubles the interval until the next repetition, up to 60 days. A learner gets up to seven new words a day and can ask for more.
- **Linked topics.** Answering one topic for a word can make a related topic due earlier, or unlock a topic that was hidden. For example, a verb's Partizip II comes before the sentences that use it.
- **Multiple-choice questions with explanations and hints.** A hint points to a well-known word with the same grammar ("Same as for …").
- **Recalls.** Some exercises have a recall. In a recall, the learner types a whole sentence with the word. After a wrong answer, the recall is required.
- **Reminders, topic selection and progress.** The bot can remind a learner to practice, limit exercises to chosen topics and show a progress summary.
- **The web widget and a standalone web app.** Logging in with Telegram shares progress with the bot. Hints, reminders, topic selection and AI content are only in the bot for now.
- **Optional AI content.** Sentence exercises can have illustrations, and an experimental mode lets Claude rewrite exercises.

## Quickstart

To run the project locally, install Docker and create a Telegram bot for development with [@BotFather](https://t.me/BotFather). Don't use a production bot's token. [CONTRIBUTING.md](CONTRIBUTING.md#setup) explains why. Put the token in `.env`:

```
BOT_TOKEN=123456:ABC...
```

Then start the services:

```bash
docker compose up
```

This starts the bot, the reminder, the web app and Valkey with the demo course from [`demo/`](demo). It has a few German exercises that use every feature of the course format. Open your bot in Telegram and press Start. Then send `/wiederholen` to get the first exercise.

To run your own course, see [CONTRIBUTING.md](CONTRIBUTING.md#setup). To open the web app locally, see [Web frontend](docs/web-frontend.md#running-locally).

## Documentation

The documentation site, [docs.immer-wiederholen.com](https://docs.immer-wiederholen.com/), is built from [`docs/`](docs). Start with the page for your role:

- [Course format](docs/course-format.md) for course authors
- [Configuration](docs/configuration.md) for operators
- [CONTRIBUTING.md](CONTRIBUTING.md) and then [Architecture](docs/architecture.md) for contributors

## License

[MIT](LICENSE)
