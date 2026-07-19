# immer-wiederholen

Telegram bot for practicing German with multiple choice questions (aiogram, Python). Exercises are loaded at startup from the path set by `EXERCISES_PATH` env var (default: `data/exercises.yaml`). Bot commands: `/start`, `/wiederholen` (show a exercise with answer options), `/language` (toggle ru/en).

## Key modules

- `wiederholen.exercises` — exercise domain: `Exercise` dataclass, loading from YAML, `Teacher` (date-based repetition scheduling, see below)
- `wiederholen.i18n` — supported languages (`Language` type, `LANGUAGES` set)
- `wiederholen.bot` — Telegram bot implementation (aiogram); each command lives in its own module under `wiederholen.bot.commands`

## Exercises (`data/exercises.yaml`)

Each exercise has the following fields.

- `question` — sentence with a blank (`___`) for government exercises, or `"verb → Partizip II"` for partizip exercises
- `topic` — verb in infinitive
- `category` — `government` or `partizip_ii` (see below); together with `topic` forms the key `Teacher` uses for repetition scheduling, so exercises of different categories for the same verb are scheduled independently
- `answer` — correct answer
- `distractors` — list of wrong options. 3 for government exercises; empty (`[]`) for partizip exercises (empty list triggers text input instead of multiple choice)
- `explanation` — dict with `ru` and `en` keys
- `recalls` — optional list of recall-step variants (empty/omitted means no recall step). `Teacher.pick_recall()` picks one variant at random each time recall starts, avoiding an immediate repeat of the previously shown variant when more than one is available. Each variant has:
  - `question` — short phrase for the recall step
  - `answer` — list of accepted full sentences (required; always a list, even if one item)
  - `hint` — dict with `ru` and `en` keys: translation of the noun shown in italics below the recall prompt (optional)

`topic` — verb in infinitive that the exercise is about (e.g. `"sprechen"`, `"sich freuen"`). Reflexive verbs include `sich`. Exercises for the same verb but different prepositions (`sprechen mit`, `sprechen über`) share the same `topic: "sprechen"` — intentionally, so that all forms of the verb are shown together when the user makes a mistake.

Sanity check: substituting the answer into the question must produce a natural, everyday German sentence; substituting any distractor must not produce a grammatically valid one.

Exercise categories (`category` field):

**`government`** — verb government (preposition exercises). Two subtypes:

- *Preposition only* — answer is a single word. Distractors are other plausible prepositions.
- *Preposition + article* — answer is a string like `"auf den"`. Use only for Wechselpräpositionen (an, auf, über, in, etc.) where the case is not fixed. Skip for prepositions with fixed case (mit, bei, für, um, nach, zu, aus, von).

**`partizip_ii`** — Partizip II forms of strong/irregular verbs. Question format: `"verb → Partizip II"`. No distractors (`distractors: []`) — user types the answer.

Distractor strategy for preposition + article exercises — use a 2×2 grid (2 prepositions × 2 cases):
- `[prep1][case1]` — correct answer
- `[prep1][case2]` — correct preposition, wrong case → tests case
- `[prep2][case1]` — wrong preposition, correct case → tests preposition
- `[prep2][case2]` — wrong preposition, wrong case

This ensures each preposition appears exactly twice, so the learner cannot eliminate the wrong preposition by frequency and must choose on all four dimensions.

Case compatibility rule: all distractors must be compatible with the case visible in the sentence. If the noun form clearly shows Akkusativ (e.g. `den`, `einen`, `meinen`), do not use prepositions that only take Dativ (`von`, `mit`, `bei`, `nach`, `zu`, `aus`) as distractors — they can be eliminated without knowing the answer. Same applies in reverse for Dativ nouns. When a noun has no article or the form is ambiguous (e.g. mass nouns without article), any preposition is fine as a distractor.

Special cases:
- `sich freuen`: use `"auf das"` ↔ `"über das"` as a distractor — common confusion between the two constructions
- `sich streiten über`: use `"um das"` — `sich streiten um` is a real expression, making it a plausible mistake

## Recall (`recalls[].question` / `recalls[].answer`)

After the multiple-choice step, the bot asks the user to reconstruct a short phrase from memory. `recalls` is a list — usually one variant, but add more when the exercise's own `question` can't vary between repetitions (notably `partizip_ii`, where `question` is always the fixed `"verb → Partizip II"` template) so the recall prompt doesn't feel identical every time the topic comes up. `Teacher.pick_recall()` picks a variant at random each time (excluding the immediately-previous one when possible, including on recall retries), so different variants don't need to be equivalent rephrasings of the same prompt — each is a full, independent recall variant (own `question`, `answer`, optional `hint`).

`recalls[].question` — a minimal phrase built from the question's vocabulary: strip adverbs, time expressions, and extra clauses, keep only subject + verb + preposition + noun (+ separable prefix / reflexive pronoun if needed). Show the noun hint in nominative in parentheses — omit the hint when no article is needed (mass nouns, proper nouns). Always one `___` blank regardless of whether the answer is one or two words.

Example:
- Question: `"Ich warte schon eine Stunde ___ den Bus."`
- recalls[].question: `"Ich warte ___ (der Bus)."`

`recalls[].answer` — list of accepted full sentences (always a list, even if one item; multiple entries for cases where several phrasings are equally valid for that *same* variant's prompt).

`recalls[].hint` — translation of the noun shown in italics below the recall prompt, to help the user focus on the grammar rather than vocabulary. Use when the noun in `recalls[].question` may be unfamiliar. Format: `"die Rede — речь"` / `"die Rede — speech"`. Both `ru` and `en` keys are optional — omit a language if the word sounds similar to its translation (e.g. `die Katastrophe` needs no `en` hint).

For categories whose `question` already varies per exercise (`government`), a single recall variant is normally enough — vary the subject across *exercises* of the same topic instead, to avoid identical recall prompts across those. For `partizip_ii`, add 2 (or more) variants within the one exercise instead, since there's no per-exercise variation to lean on.

Sanity check: every `recalls[].answer` must be a natural, everyday German sentence. Do not force an article where none is natural — e.g. `"Sie verzichtet auf Fleisch."` not `"Sie verzichtet auf das Fleisch."`

YAML example with `recalls`:
```yaml
- question: "Ich warte schon eine Stunde ___ den Bus."
  topic: warten
  category: government
  answer: auf
  distractors: [für, an, um]
  explanation:
    ru: warten auf + Akk
    en: warten auf + Acc
  recalls:
    - question: "Ich warte ___ (der Bus)."
      answer:
        - "Ich warte auf den Bus."
      hint:
        ru: "der Bus — автобус"
```

YAML example with multiple `recalls` variants (`partizip_ii`, fixed `question` per exercise):
```yaml
- question: "helfen → Partizip II"
  topic: helfen
  category: partizip_ii
  answer: geholfen
  distractors: []
  explanation:
    ru: "helfen — помогать; Partizip II: geholfen (haben)"
    en: "helfen — to help; Partizip II: geholfen (haben)"
  recalls:
    - question: "Er hat mir ___."
      answer:
        - "Er hat mir geholfen."
    - question: "Sie hat ihr ___."
      answer:
        - "Sie hat ihr geholfen."
```

## Repetition schedule

`Teacher` (in `wiederholen.exercises`) tracks review scheduling in `journal["topic_schedule"]` — `{"{topic}:{category}": {"interval_days": int, "due_date": "YYYY-MM-DD"}}`. The schedule key is `topic` + `category` (`Teacher._schedule_key`), not `topic` alone — so e.g. `sprechen`'s government exercises (different prepositions) and its `partizip_ii` exercise are scheduled independently, while exercises that intentionally share a `topic` within the same category (different prepositions of the same verb) still share one schedule entry. `next_exercise()` selects in two steps — first a random due key (`topic:category`), then a random exercise among the (possibly several) YAML entries sharing that key — so a key backed by many entries (e.g. several prepositions for one verb) isn't shown more often than a key with only one entry. Falls back to a random key among those tied for the earliest due date if nothing is due yet. `check_answer()` also records `journal["last_answered_question"]` (the `question` of the exercise just checked), and `next_exercise()` reads it back to exclude any within-key candidate with a matching `question`, unless that would leave no candidates at all (e.g. a key whose only entry happens to match — repeating is then unavoidable, not a bug). This keeps repeat-avoidance entirely inside `Teacher`/`journal` — the bot layer doesn't pass or know anything about it. On a correct answer the interval doubles (capped at `Teacher.MAX_INTERVAL_DAYS`, currently 60 days); on a wrong answer it resets to 1 day (due again immediately). The journal's durability depends on the FSM storage backing it — see below.

`pick_recall()` follows the same pattern for recall variants: it records `journal["last_recall_question"]` and reads it back next time to exclude a matching candidate, unless that would leave no candidates. This too lives entirely inside `Teacher`/`journal` — the bot layer (`_start_recall` in `wiederholen.bot.commands.wiederholen`) just calls `teacher.pick_recall(exercise)` and doesn't track which variant was shown last.

## Persistence

`wiederholen.bot` builds `dispatcher` with aiogram's default in-memory FSM storage (needed so importing the package — e.g. from tests — never depends on an external service or env var). `wiederholen.bot.bootstrap.load_bot_school_and_storage()` constructs the real `ScanningRedisStorage` (a `RedisStorage` subclass, see "Reminders" below) from `FSM_STORAGE_URL`, required with no fallback, same as `BOT_TOKEN` — both `wiederholen.bot.__main__.main()` (polling bot) and `wiederholen.bot.reminder.main()` (reminder worker) call it, so both processes always share the same storage class. Works with Valkey too (wire-compatible). `compose.yaml` and `deploy/compose.yaml` both run a `valkey` service and set `FSM_STORAGE_URL` for the `bot` and `reminder` services, backed by a named volume for durability across container recreation.

Tests run against a real Redis/Valkey too, not an in-memory fake — `tests/plugins/aiogram.py::pytest_configure` pins `FSM_STORAGE_URL` to a dedicated DB number (15, separate from dev/prod's DB 0) for the whole test session, before any test code runs, so the suite can never touch a DB a real dev/prod bot might be using regardless of what's set in the environment. The `redis_storage` fixture (same module) builds a `ScanningRedisStorage` from that URL and flushes it before every test; the autouse `_reset_storage` fixture wires it into `dispatcher.fsm.storage`. This is deliberately fidelity-over-speed: it's still fast (no measurable slowdown at this suite's size) and catches real Redis/`KeyBuilder` behavior that an in-memory double can't (see "Reminders" below — this is exactly how a key-format bug was caught). The `redis_storage` fixture is function-scoped, not session-scoped: pytest-asyncio gives each test its own event loop by default, and a Redis connection can't outlive the loop it was created in.

## Reminders

A separate worker process (`python -m wiederholen.bot.reminder`, its own `reminder` service in `compose.yaml`/`deploy/compose.yaml`) nudges users who've gone quiet with material due — not an in-process `asyncio` task in the polling bot, specifically to avoid leaking an uncancelled background task across `tests/bot/test_main.py`'s repeated `main()` calls.

`Teacher` owns the decision, journal-backed like the rest of its scheduling state: `check_answer()` records `journal["last_answered_at"]` (a timestamp, alongside the existing `last_answered_question`) — "activity" means answering the main exercise specifically, not any interaction with the bot (recall answers don't count). `Teacher.should_remind()` is a pure query — no side effects — returning `True` only if `due_topics_count() > 0`, `last_answered_at` is ≥`Teacher.REMIND_AFTER` (24h) old, and there hasn't already been a reminder since that last answer (`last_reminded_at is None or last_reminded_at < last_answered_at`) — this last condition means exactly one reminder per period of inactivity, not a repeating nag. `Teacher.record_reminder_sent()` is a separate method, called by the bot layer only *after* a Telegram send actually succeeds — `should_remind()` itself never mutates the journal, so a failed send never gets wrongly marked as delivered.

The worker has no separate registry of known chats — `wiederholen.bot.redis_storage.ScanningRedisStorage` (a `RedisStorage` subclass) adds `iter_fsm_data(bot_id)`, which enumerates every chat with FSM data via a real Redis `SCAN` and returns each chat's data alongside its id. It doesn't assume any particular `KeyBuilder` format: it builds a marker `StorageKey` (`chat_id`/`user_id` set to sentinel strings — `KeyBuilder.build()` only ever does `str(key.chat_id)`, so this works despite the declared `int` type) and derives both the SCAN glob pattern and a parsing regex from whatever comes back, rather than hardcoding `DefaultKeyBuilder`'s shape. `wiederholen.bot.reminder.tick()` calls this once per sweep, then for each chat with `Teacher.should_remind()` true sends `locale.reminder_text` and calls `record_reminder_sent()`; one chat raising (e.g. malformed journal data) is caught and logged, not fatal to the sweep. `run()` loops `tick()` every `POLL_INTERVAL_SECONDS` (15 min).

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
