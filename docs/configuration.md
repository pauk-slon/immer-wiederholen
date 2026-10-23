# Configuration

Everything is configured through environment variables. This page lists them per process, then the optional integrations, each of which stays off until its variables are set.

For a local run, `compose.yaml` already sets everything except `BOT_TOKEN`; put that in `.env` and run `docker compose up`.

## Processes

All processes run from one Docker image, `ghcr.io/pauk-slon/immer-wiederholen:main`, built from the `prod` stage of the `Dockerfile` on every push to `main`.

| Process | Command | What it does |
|---|---|---|
| bot | `python -m wiederholen.bot` (the image's default) | the Telegram bot, using long polling — needs no open port |
| reminder | `python -m wiederholen.bot.reminder` | sends reminders to learners who have gone quiet; checks every 15 minutes |
| web | `python -m wiederholen.web` | the web widget and its API, on port 8000 — see [Web frontend](web-frontend.md) |
| cue generator | `python -m wiederholen.school.authoring.cues` | a one-off run that generates missing illustrations — see [Illustrations](#illustrations) |

Only one bot process may run per bot token: Telegram rejects a second one polling the same bot. So don't run a local copy with the production bot's token — create a separate bot for development.

## Required variables

| Variable | bot | reminder | web | Meaning |
|---|---|---|---|---|
| `BOT_TOKEN` | ✓ | ✓ | ✓ | the bot's token from [@BotFather](https://t.me/BotFather). The web app uses it only to verify Telegram logins |
| `STUDENT_RECORD_STORAGE_URL` | ✓ | ✓ | ✓ | learners' repetition schedules |
| `STUDENT_IDENTITY_STORAGE_URL` | ✓ | ✓ | ✓ | which Telegram chats and browser logins belong to which learner |
| `BOT_FSM_STORAGE_URL` | ✓ | ✓ | | Telegram chat state: language, settings, the exercise being answered |
| `WEB_SESSION_STORAGE_URL` | | | ✓ | the exercise shown in each web session |
| `WEB_ALLOWED_ORIGINS` | | | ✓ | comma-separated origins of the pages that embed the widget; also the only external targets allowed after a Telegram login |
| `WEB_COOKIE_DOMAIN` | | | ✓ | the domain for the session cookie; must cover the web app's own host |

All processes also read `COURSE_PATH`, the course directory — see [Course format](course-format.md). It defaults to `data`; `compose.yaml` sets it to `demo`.

The four `*_STORAGE_URL` variables are Redis URLs, e.g. `redis://valkey:6379/0`. Valkey works as well as Redis. They can point at one server, but each needs its own database number, as in `compose.yaml`:

| Variable | Database |
|---|---|
| `STUDENT_RECORD_STORAGE_URL` | 0 |
| `STUDENT_IDENTITY_STORAGE_URL` | 1 |
| `WEB_SESSION_STORAGE_URL` | 2 |
| `BOT_FSM_STORAGE_URL` | 3 |

Make the Redis data persistent (a volume, as in `compose.yaml`): it holds all learners' progress.

## What the bot changes in its Telegram profile

On every start, the bot overwrites parts of its own profile in Telegram. The changes stay after the bot stops:

- **Command menu**: always, for Russian and English users.
- **Name, description and short description**: if the course has a `bot.yaml` (see [Course format](course-format.md#botyaml)), for Russian and English users only. Users with Telegram in other languages keep seeing the name set in BotFather.

So give the project its own bot rather than reusing one made for something else. To keep the name and descriptions you set in BotFather, leave `bot.yaml` out of the course.

## Optional integrations

### AI-generated questions

**Bot only.** An `/ai` command that switches a chat to questions rewritten by an LLM (Anthropic's Claude), for topics with `ai_generation: true` in `topics.yaml`. It's an experiment, available only to chats listed in a feature flag:

| Variable | Meaning |
|---|---|
| `ANTHROPIC_API_KEY` | an [Anthropic API](https://console.anthropic.com/) key |
| `BOT_FEATURE_FLAGS` | `ai_exercises:<chat id>,<chat id>` — the chats that get `/ai`. For a private chat, the chat id is the user's Telegram id |
| `AUTHORING_GUIDE_PATH` | optional: a Markdown file with exercise-writing guidelines, sent to the model along with each request. Everything from a `## Deploying` heading onward is cut off |

For anyone not in the flag, `/ai` does nothing. Without `ANTHROPIC_API_KEY`, a flagged chat gets an error message instead of an AI question.

`BOT_FEATURE_FLAGS` can hold several flags separated by `;`, e.g. `ai_exercises:123,456;other_flag:789`; `ai_exercises` is currently the only one. Changing it takes a restart.

### Illustrations

**Bot only.** Questions of topics with `cue_generation: true` are shown with an illustration ("cue"), see [Course format](course-format.md#ai-generated-questions-and-illustrations). Images are generated ahead of time by Cloudflare Workers AI and stored in Cloudflare R2; the bot only looks them up.

Setting it up in Cloudflare:

1. Create an R2 bucket and connect a custom domain to it, so its objects are publicly readable, e.g. `https://cues.example.com/<key>`.
2. Create three API tokens: R2 read-only for the bot; R2 read and write for the generator; Workers AI for the generator.

The bot needs:

| Variable | Meaning |
|---|---|
| `R2_ACCOUNT_ID` | the Cloudflare account id; illustrations are off if it's unset |
| `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | the read-only R2 token |
| `R2_BUCKET` | the bucket name |
| `R2_PUBLIC_URL_BASE` | the bucket's public URL, e.g. `https://cues.example.com` |

The generator needs the same five, with the read-write token, plus:

| Variable | Meaning |
|---|---|
| `CLOUDFLARE_ACCOUNT_ID` | the Cloudflare account id |
| `CLOUDFLARE_API_TOKEN` | the Workers AI token |

Run the generator after adding or rewording exercises in such topics. It skips exercises that already have an illustration and prints a summary at the end. Workers AI's free tier covers about 90 images a day; past that, requests fail until the next day, and a later run picks up where this one stopped.

The bot remembers each lookup for 12 hours, including "no illustration yet", so a newly generated image may take that long to appear. Restarting the bot clears this.

### Tracing

All processes can send OpenTelemetry traces: one span per Telegram update, web request and reminder check, plus every Redis call. Tracing is off unless an endpoint is set. It's configured with the [standard OpenTelemetry variables](https://opentelemetry.io/docs/languages/sdk-configuration/), for example:

| Variable | Example |
|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `https://api.honeycomb.io` |
| `OTEL_EXPORTER_OTLP_HEADERS` | `x-honeycomb-team=<api key>` |
| `OTEL_SERVICE_NAME` | `bot`, `reminder` or `web` — set a different one per process |
| `OTEL_RESOURCE_ATTRIBUTES` | `deployment.environment=prod` |

Traces go out over OTLP/HTTP.

## Design notes

- **One variable per store.** The four stores share one Redis today, but each has its own URL so any of them can move to a separate server without touching the others. The student stores are meant to be shared by every frontend; the bot's and web app's session stores are not.
- **Optional integrations turn on by their variables.** No separate on/off switch: a missing `ANTHROPIC_API_KEY` or `R2_ACCOUNT_ID` simply means the feature is off, and the bot starts normally.
- **Tracing needs an explicit endpoint.** Without one, the OpenTelemetry exporter would default to `localhost:4318` and keep retrying a collector that isn't there, filling the logs.
