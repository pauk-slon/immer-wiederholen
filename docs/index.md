# Immer wiederholen!

A project for creating Telegram bots that teach grammar with spaced repetition. You write the course in YAML, and the bot teaches it. The bot tracks what each learner knows. It shows each exercise again shortly before the learner would forget it. You can also embed the exercises on any web page as a widget.

See [@ImmerWiederholenBot](https://t.me/ImmerWiederholenBot) for an example of a bot that teaches German grammar.

The [README](https://github.com/pauk-slon/immer-wiederholen#readme) describes the features and how to run the project locally.

## Course authors

[Course format](course-format.md) describes the three files of a course (`exercises.yaml`, `topics.yaml` and `bot.yaml`) with every field and setting.

## Operators

[Configuration](configuration.md) describes the processes, their environment variables and the optional integrations.

## Contributors

Start with [CONTRIBUTING.md](https://github.com/pauk-slon/immer-wiederholen/blob/main/CONTRIBUTING.md) for setup and conventions, then [Architecture](architecture.md) for the map of the code. Each subsystem has its own page:

- [Repetition schedule](repetition-schedule.md) describes how the project picks the next exercise
- [Storage and identity](storage.md) describes where each learner's state is stored
- [Telegram bot](bot.md)
- [Web frontend](web-frontend.md)
- [AI-generated content](authoring.md)
- [Observability](tracing.md)

The [Architecture decision records](adr/README.md) explain the reasons for the main design choices.
