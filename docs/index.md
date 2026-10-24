# Immer wiederholen!

A project for creating Telegram bots that teach grammar with spaced repetition. You bring the course, written in YAML, and the bot handles the teaching. It keeps track of what each learner knows and brings every exercise back just before it would be forgotten. The exercises can also be embedded on any web page as a widget.

See [@ImmerWiederholenBot](https://t.me/ImmerWiederholenBot) for an example of a bot that teaches German grammar.

What the project can do and how to run it locally is in the [README](https://github.com/pauk-slon/immer-wiederholen#readme).

## Course authors

[Course format](course-format.md) — the files a course is made of: `exercises.yaml`, `topics.yaml` and `bot.yaml`, with every field and setting.

## Operators

[Configuration](configuration.md) — the processes, their environment variables, and the optional integrations.

## Contributors

Start with [CONTRIBUTING.md](https://github.com/pauk-slon/immer-wiederholen/blob/main/CONTRIBUTING.md) for setup and conventions, then [Architecture](architecture.md) for the map of the code. Each subsystem has its own page:

- [Repetition schedule](repetition-schedule.md) — how the next exercise is picked
- [Storage and identity](storage.md) — where per-learner state lives
- [Telegram bot](bot.md)
- [Web frontend](web-frontend.md)
- [AI-generated content](authoring.md)
- [Observability](tracing.md)

Why things are the way they are is in the [Architecture decision records](adr/README.md).
