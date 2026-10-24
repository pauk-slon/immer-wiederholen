# Configuration

How to run the project: its processes, the environment variables they read, what the bot changes in Telegram, and the optional integrations, each of which stays off until its variables are set.

For a local run, `compose.yaml` already sets everything except `BOT_TOKEN`; put that in `.env` and run `docker compose up`.

## Processes

All processes run from one Docker image, `ghcr.io/pauk-slon/immer-wiederholen:main`, built from the `prod` stage of the `Dockerfile` on every push to `main`.

| Process | Command | What it does |
|---|---|---|
| bot | `python -m wiederholen.bot` (the image's default) | the Telegram bot, using long polling — needs no open port |
| reminder | `python -m wiederholen.bot.reminder` | sends reminders to learners who have gone quiet; checks every 15 minutes |
| web | `python -m wiederholen.web` | the web widget and its API, on port 8000 — see [Web frontend](web-frontend.md) |
| cue generator | `python -m wiederholen.school.authoring.cues` | a one-off run that generates missing illustrations — see [Illustrations](#illustrations) |

The image contains no course. Mount one into the container, e.g. at `/app/data` (the default `COURSE_PATH`), see [Course format](course-format.md).

Only one `bot` process may poll Telegram per bot token; a second one gets errors. The reminder uses the same token without polling, so it can run alongside. Don't run a local copy with the production bot's token — create a separate bot for development.

## Environment variables

| Variable | bot | reminder | web | Meaning |
|---|---|---|---|---|
| `BOT_TOKEN` | ✓ | ✓ | ✓ | the bot's token from [@BotFather](https://t.me/BotFather). The web app uses it only to verify Telegram logins |
| `STUDENT_RECORD_STORAGE_URL` | ✓ | ✓ | ✓ | learners' repetition schedules |
| `STUDENT_IDENTITY_STORAGE_URL` | ✓ | ✓ | ✓ | which Telegram chats and browser logins belong to which learner |
| `BOT_FSM_STORAGE_URL` | ✓ | ✓ | | Telegram chat state: language, settings, the exercise being answered |
| `WEB_SESSION_STORAGE_URL` | | | ✓ | the exercise shown in each web session |
| `WEB_ALLOWED_ORIGINS` | | | ✓ | comma-separated origins of the pages that embed the widget; also the only external targets allowed after a Telegram login |
| `WEB_COOKIE_DOMAIN` | | | ✓ | the domain for the session cookie; must cover the web app's own host |

All are required by the processes marked. In addition, every process reads `COURSE_PATH`, the course directory: it defaults to `data`, and `compose.yaml` sets it to `demo`.

### Redis

The four `*_STORAGE_URL` variables are Redis URLs, e.g. `redis://valkey:6379/0`; Valkey works as well as Redis. Every store prefixes its keys, so they can share one database, but we recommend a database per store, as in `compose.yaml` — then each can be inspected, cleared or moved on its own:

| Variable | Database |
|---|---|
| `STUDENT_RECORD_STORAGE_URL` | 0 |
| `STUDENT_IDENTITY_STORAGE_URL` | 1 |
| `WEB_SESSION_STORAGE_URL` | 2 |
| `BOT_FSM_STORAGE_URL` | 3 |

Each store has its own variable so any of them can move to another server on its own (see [ADR 0009](adr/0009-one-environment-variable-per-store.md)).

Make the Redis data persistent (a volume, as in `compose.yaml`): it holds all learners' progress.

### Telegram login on the web

The web app's "Log in with Telegram" button works only on the domain registered for the bot with BotFather's `/setdomain`. Telegram allows one domain per bot. See [Web frontend](web-frontend.md).

## What the bot changes in its Telegram profile

On every start, the bot overwrites parts of its own profile in Telegram. The changes stay after the bot stops:

- **Command menu**: always, for Russian and English users. Users with Telegram in other languages see the default menu set in BotFather, if any.
- **Name, description and short description**: if the course has a `bot.yaml` (see [Course format](course-format.md#botyaml)), for Russian and English users. Users with Telegram in other languages keep seeing the ones set in BotFather.

So give the project its own bot rather than reusing one made for something else. To keep the name and descriptions you set in BotFather, leave `bot.yaml` out of the course.

## Optional integrations

Each integration is switched on by its variables, with no separate flag: without them the feature is simply off, and the bot starts normally.

### AI-generated questions

**Bot only.** An `/ai` command that switches a chat to questions rewritten by an LLM (Anthropic's Claude), for topics with `ai_generation: true` in `topics.yaml`. It's an experiment, available only to chats listed in a feature flag:

| Variable | Meaning |
|---|---|
| `ANTHROPIC_API_KEY` | an [Anthropic API](https://console.anthropic.com/) key |
| `BOT_FEATURE_FLAGS` | `ai_exercises:<chat id>,<chat id>` — the chats that get `/ai`. For a private chat, the chat id is the user's Telegram id |
| `AUTHORING_GUIDE_PATH` | optional: a Markdown file with exercise-writing guidelines, sent to the model with each request. Everything from a `## Deploying` heading onward is left out, so the same file can keep deployment notes for humans at the end |

For anyone not in the flag, `/ai` does nothing. If `ANTHROPIC_API_KEY` is missing, a flagged chat with `/ai` on gets an error message whenever an AI question is due; questions of other topics are shown as usual.

`BOT_FEATURE_FLAGS` can hold several flags separated by `;`, e.g. `ai_exercises:123,456;other_flag:789`; `ai_exercises` is currently the only one. Changing it takes a restart.

### Illustrations

**Bot only.** Questions of topics with `cue_generation: true` are shown with an illustration ("cue"), see [Course format](course-format.md#ai-generated-questions-and-illustrations). Images are generated ahead of time by Cloudflare Workers AI and stored in Cloudflare R2; the bot only looks them up.

**1. Set up Cloudflare:**

1. Create an R2 bucket and connect a custom domain to it, so its objects are publicly readable, e.g. `https://cues.example.com/<key>`.
2. Create two R2 API tokens: read-only for the bot, read and write for the generator. Each gives an Access Key ID and a Secret Access Key.
3. Create a Cloudflare API token with Workers AI access, for the generator.

**2. Configure the bot:**

| Variable | Meaning |
|---|---|
| `R2_ACCOUNT_ID` | the Cloudflare account id. Unset: illustrations are off. Set: the other four are required too, or the bot fails to start |
| `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | the read-only R2 token |
| `R2_BUCKET` | the bucket name |
| `R2_PUBLIC_URL_BASE` | the bucket's public URL, e.g. `https://cues.example.com` |

**3. Run the generator** after adding or rewording exercises in such topics. It needs the same five variables, with the read-write token, plus:

| Variable | Meaning |
|---|---|
| `CLOUDFLARE_ACCOUNT_ID` | the Cloudflare account id |
| `CLOUDFLARE_API_TOKEN` | the Workers AI token |

It skips exercises that already have an illustration and logs a summary at the end. Workers AI's free tier covers about 90 images a day. Past that, the generator doesn't stop: every remaining exercise fails, and the summary shows them as failed. That's expected — run it again the next day, and it picks up where the quota cut it off.

The bot remembers each lookup for 12 hours, including "no illustration yet", so a newly generated image may take that long to appear. Restarting the bot clears this.

### Tracing

The bot, the reminder and the web app can send OpenTelemetry traces: one span per Telegram update, web request and reminder check, plus every Redis call. The cue generator doesn't. Tracing is off unless an endpoint is set: without one, the exporter would default to `localhost:4318` and keep retrying a collector that isn't there, filling the logs. It's configured with the [standard OpenTelemetry variables](https://opentelemetry.io/docs/languages/sdk-configuration/), for example:

| Variable | Example |
|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `https://api.honeycomb.io` |
| `OTEL_EXPORTER_OTLP_HEADERS` | `x-honeycomb-team=<api key>` |
| `OTEL_SERVICE_NAME` | `bot`, `reminder` or `web`. Set a different one per process: without it, all of them report as `unknown_service` |
| `OTEL_RESOURCE_ATTRIBUTES` | `deployment.environment=prod` |

Only the OTLP/HTTP exporter is installed; `OTEL_EXPORTER_OTLP_PROTOCOL=grpc` won't work. What gets traced is described in [Observability](tracing.md).

## Decisions

- [ADR 0009](adr/0009-one-environment-variable-per-store.md): one environment variable per store.
