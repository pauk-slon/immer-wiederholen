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
- `recall` — optional nested object with recall step data:
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

## Recall (`recall.question` / `recall.answer`)

After the multiple-choice step, the bot asks the user to reconstruct a short phrase from memory.

`recall.question` — a minimal phrase built from the question's vocabulary: strip adverbs, time expressions, and extra clauses, keep only subject + verb + preposition + noun (+ separable prefix / reflexive pronoun if needed). Show the noun hint in nominative in parentheses — omit the hint when no article is needed (mass nouns, proper nouns). Always one `___` blank regardless of whether the answer is one or two words.

Example:
- Question: `"Ich warte schon eine Stunde ___ den Bus."`
- recall.question: `"Ich warte ___ (der Bus)."`

`recall.answer` — list of accepted full sentences (always a list, even if one item; multiple entries for cases where several phrasings are equally valid).

`recall.hint` — translation of the noun shown in italics below the recall prompt, to help the user focus on the grammar rather than vocabulary. Use when the noun in `recall.question` may be unfamiliar. Format: `"die Rede — речь"` / `"die Rede — speech"`. Both `ru` and `en` keys are optional — omit a language if the word sounds similar to its translation (e.g. `die Katastrophe` needs no `en` hint).

Vary the subject across exercises of the same topic to avoid identical recall prompts.

Sanity check: the recall.answer must be a natural, everyday German sentence. Do not force an article where none is natural — e.g. `"Sie verzichtet auf Fleisch."` not `"Sie verzichtet auf das Fleisch."`

YAML example with recall:
```yaml
- question: "Ich warte schon eine Stunde ___ den Bus."
  topic: warten
  answer: auf
  distractors: [für, an, um]
  explanation:
    ru: warten auf + Akk
    en: warten auf + Acc
  recall:
    question: "Ich warte ___ (der Bus)."
    answer:
      - "Ich warte auf den Bus."
    hint:
      ru: "der Bus — автобус"
```

## Repetition schedule

`Teacher` (in `wiederholen.exercises`) tracks review scheduling in `journal["topic_schedule"]` — `{"{topic}:{category}": {"interval_days": int, "due_date": "YYYY-MM-DD"}}`. The schedule key is `topic` + `category` (`Teacher._schedule_key`), not `topic` alone — so e.g. `sprechen`'s government exercises (different prepositions) and its `partizip_ii` exercise are scheduled independently, while exercises that intentionally share a `topic` within the same category (different prepositions of the same verb) still share one schedule entry. `next_exercise()` selects in two steps — first a random due key (`topic:category`), then a random exercise among the (possibly several) YAML entries sharing that key — so a key backed by many entries (e.g. several prepositions for one verb, or several near-duplicate recall variants) isn't shown more often than a key with only one entry. Falls back to the single earliest-due key if nothing is due yet. On a correct answer the interval doubles (capped at `Teacher.MAX_INTERVAL_DAYS`, currently 60 days); on a wrong answer it resets to 1 day (due again immediately). The journal's durability depends on the FSM storage backing it — see below.

## Persistence

`wiederholen.bot` builds `dispatcher` with aiogram's default in-memory FSM storage (needed so importing the package — e.g. from tests — never depends on an external service or env var). `wiederholen.bot.__main__.main()` swaps in real storage before polling starts: `dispatcher.fsm.storage = RedisStorage.from_url(os.environ["FSM_STORAGE_URL"])`, required with no fallback, same as `BOT_TOKEN`. Works with Valkey too (wire-compatible). `compose.yaml` and `deploy/compose.yaml` both run a `valkey` service and set `FSM_STORAGE_URL` for the `bot` service, backed by a named volume for durability across container recreation. Tests always force a fresh in-memory store regardless of `FSM_STORAGE_URL` (see `tests/plugins/aiogram.py::_reset_storage`), so they stay fast and hermetic.

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
