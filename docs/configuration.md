# Configuration

This page describes how to run the project. It covers the processes, the environment variables that they read, the changes that the bot makes in Telegram, and the optional integrations.

For a local run, `compose.yaml` sets the variables except `BOT_TOKEN`. Put `BOT_TOKEN` in `.env` and run `docker compose up`.

## Processes

All processes run from one Docker image, `ghcr.io/pauk-slon/immer-wiederholen:main`. The image is built from the `prod` stage of the `Dockerfile` on every push to `main`. Each commit on `main` has a version, such as `2026.10.3`, and its image also gets the version as a tag, such as `ghcr.io/pauk-slon/immer-wiederholen:2026.10.3`. The version is the UTC month of the merge and the number of that merge among the month's merges into `main`. A larger version is always a later commit, so you can deploy or roll back to a specific commit by its version tag. The versions can have gaps. A merge whose checks fail isn't published, but it still takes a number. [ADR 0020](adr/0020-calendar-version-per-commit.md) explains why this format was chosen.

| Process | Command | What it does |
|---|---|---|
| bot | `python -m wiederholen.bot` (the image's default) | the Telegram bot. It uses long polling, so it needs no open port |
| reminder | `python -m wiederholen.bot.reminder` | sends a reminder when a learner hasn't answered for the time set in `/reminders`. It checks every 15 minutes |
| web | `python -m wiederholen.web` | the web widget, the web app and their API on port 8000 (see [Web frontend](web-frontend.md)) |
| cue generator | `python -m wiederholen.school.authoring.cues` | a one-off run that generates missing illustrations (see [Illustrations](#illustrations)) |

The image contains no course. Mount a course into the container, for example at `/app/data` (the default `COURSE_PATH`). [Course format](course-format.md) describes the files of a course.

Only one `bot` process can poll Telegram for each bot token. A second process gets errors. The reminder uses the same token without polling, so it can run at the same time. Don't run a local copy with the production bot's token, because the two processes would conflict. Create a separate bot for development.

## Environment variables

| Variable | bot | reminder | web | Meaning |
|---|---|---|---|---|
| `BOT_TOKEN` | ✓ | ✓ | ✓ | the bot's token from [@BotFather](https://t.me/BotFather). The web app uses it only to verify Telegram logins |
| `STUDENT_RECORD_STORAGE_URL` | ✓ | ✓ | ✓ | each learner's repetition schedule |
| `STUDENT_IDENTITY_STORAGE_URL` | ✓ | ✓ | ✓ | which Telegram chats and browser logins belong to which learner |
| `BOT_FSM_STORAGE_URL` | ✓ | ✓ | | Telegram chat state, such as the language, the settings and the exercise that the learner is answering |
| `WEB_SESSION_STORAGE_URL` | | | ✓ | the exercise shown in each web session |
| `WEB_ALLOWED_ORIGINS` | | | ✓ | comma-separated origins of the pages that embed the widget. After a Telegram login, the web app redirects only to these origins |
| `WEB_COOKIE_DOMAIN` | | | ✓ | the domain of the session cookie. It must cover the web app's own host |

A process with a ✓ requires the variable. Every process also reads `COURSE_PATH`, the course directory. It defaults to `data`, and `compose.yaml` sets it to `demo`.

### Redis

The four `*_STORAGE_URL` variables are Redis URLs, such as `redis://valkey:6379/0`. Valkey works as well as Redis. Each store adds a prefix to its keys, so all stores can share one database. But we recommend a separate database for each store. Then you can inspect or clear each store separately. `compose.yaml` uses these databases:

| Variable | Database |
|---|---|
| `STUDENT_RECORD_STORAGE_URL` | 0 |
| `STUDENT_IDENTITY_STORAGE_URL` | 1 |
| `WEB_SESSION_STORAGE_URL` | 2 |
| `BOT_FSM_STORAGE_URL` | 3 |

Each store has its own variable, so you can move any store to another server separately (see [ADR 0009](adr/0009-one-environment-variable-per-store.md)).

Make the Redis data persistent, for example with a volume as in `compose.yaml`. It holds the progress of all learners.

### Telegram login on the web

The "Log in with Telegram" button of the web app works only on the domain that you register for the bot with BotFather's `/setdomain`. Telegram allows one domain per bot. [Web frontend](web-frontend.md#telegram-login) describes how the login works.

## What the bot changes in its Telegram profile

On every start, the bot overwrites parts of its own profile in Telegram. The changes stay after the bot stops:

- **Command menu.** The bot always sets it for Russian and English users. Users with Telegram in other languages see the default menu from BotFather, if there is one.
- **Name, description and short description.** The bot sets them for Russian and English users if the course has a `bot.yaml` (see [Course format](course-format.md#botyaml)). Users with Telegram in other languages still see the values from BotFather.

For this reason, give the project its own bot. Don't reuse a bot that you made for another purpose. To keep the name and descriptions from BotFather, omit `bot.yaml` from the course.

## Optional integrations

You enable each integration with its variables. There is no separate flag. Without the variables, the feature is off, and the bot starts normally.

### AI-generated questions

**Bot only.** The `/ai` command switches a chat to exercises that an LLM (Anthropic's Claude) rewrites. It works for topics with `ai_generation: true` in `topics.yaml`. The feature is an experiment, so only the chats in a feature flag get it. The feature uses these variables:

| Variable | Meaning |
|---|---|
| `ANTHROPIC_API_KEY` | an [Anthropic API](https://console.anthropic.com/) key |
| `BOT_FEATURE_FLAGS` | the chats that get `/ai`, in the form `ai_exercises:<chat id>,<chat id>`. For a private chat, the chat id is the user's Telegram id |
| `AUTHORING_GUIDE_PATH` | optional. A Markdown file with guidelines for writing exercises, which the bot sends to the model with each request. The part from a `## Deploying` heading to the end of the file isn't sent, so the file can keep deployment notes for people |

For chats outside the flag, `/ai` does nothing. If `ANTHROPIC_API_KEY` is missing, a flagged chat with `/ai` on gets an error message each time an AI exercise is due. Exercises of other topics appear as usual.

`BOT_FEATURE_FLAGS` can hold several flags, separated by `;`, such as `ai_exercises:123,456;other_flag:789`. Currently `ai_exercises` is the only flag. After you change the variable, restart the bot.

### Illustrations

**Bot only.** For topics with `cue_generation: true`, the bot shows each question with an illustration (a "cue" in the code, see [Course format](course-format.md#ai-generated-questions-and-illustrations)). Cloudflare Workers AI generates the images ahead of time, and Cloudflare R2 stores them. The bot only reads them.

**1. Set up Cloudflare:**

1. Create an R2 bucket and connect a custom domain to it. This makes its objects publicly readable, for example at `https://cues.example.com/<key>`.
2. Create two R2 API tokens, a read-only token for the bot and a read-write token for the generator. Each token has an Access Key ID and a Secret Access Key.
3. Create a Cloudflare API token with Workers AI access for the generator.

**2. Configure the bot:**

| Variable | Meaning |
|---|---|
| `R2_ACCOUNT_ID` | the Cloudflare account id. If it isn't set, illustrations are off. If it is set, the other four variables are also required, or the bot fails to start |
| `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | the read-only R2 token |
| `R2_BUCKET` | the bucket name |
| `R2_PUBLIC_URL_BASE` | the bucket's public URL, such as `https://cues.example.com` |

**3. Run the generator** after you add or reword exercises in such topics. It needs the same five variables with the read-write token, and also these:

| Variable | Meaning |
|---|---|
| `CLOUDFLARE_ACCOUNT_ID` | the Cloudflare account id |
| `CLOUDFLARE_API_TOKEN` | the Workers AI token |

The generator skips exercises that already have an illustration and logs a summary at the end. The free tier of Workers AI covers about 90 images a day. After that limit, the generator doesn't stop. Every remaining exercise fails, and the summary shows them as failed. This is expected. Run the generator again the next day, and it continues from the point where the quota stopped it.

The bot caches each lookup for 12 hours, including "no illustration yet", so a new image can take up to 12 hours to appear. A restart of the bot clears the cache.

### Tracing

The bot, the reminder and the web app can send OpenTelemetry traces. They send one span per Telegram update, web request and reminder check, and one span per Redis call. The cue generator sends no traces.

Tracing is off until you set an OTLP endpoint. Without an endpoint, the exporter would use `localhost:4318` by default. It would keep retrying a collector that isn't there and fill the logs. You configure tracing with the [standard OpenTelemetry variables](https://opentelemetry.io/docs/languages/sdk-configuration/), for example:

| Variable | Example |
|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `https://api.honeycomb.io` |
| `OTEL_EXPORTER_OTLP_HEADERS` | `x-honeycomb-team=<api key>` |
| `OTEL_SERVICE_NAME` | `bot`, `reminder` or `web`. Set a different name for each process. Without it, all processes report as `unknown_service` |
| `OTEL_RESOURCE_ATTRIBUTES` | `deployment.environment=prod` |

The published image sets `APP_VERSION` to the version of its commit, and the processes send it as the `service.version` resource attribute. Don't set `APP_VERSION` yourself, because the traces would then show a version that isn't the one that runs. A locally built image doesn't set it, so its spans have no `service.version`.

Only the OTLP/HTTP exporter is installed, so `OTEL_EXPORTER_OTLP_PROTOCOL=grpc` doesn't work. [Observability](tracing.md) describes what gets traced.

## Decisions

- [One environment variable per store](adr/0009-one-environment-variable-per-store.md) (ADR 0009)
- [Each commit on main gets a calendar version](adr/0020-calendar-version-per-commit.md) (ADR 0020)
