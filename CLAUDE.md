# immer-wiederholen

Telegram bot for practicing German with multiple choice questions (aiogram, Python). Cards are loaded at startup from the path set by `CARDS_PATH` env var (default: `data/cards.yaml`). Bot commands: `/start`, `/wiederholen` (show a card with answer options), `/language` (toggle ru/en).

## Key modules

- `wiederholen.cards` — card domain: `Card` dataclass, loading from YAML, random picking
- `wiederholen.i18n` — supported languages (`Language` type, `LANGUAGES` set)
- `wiederholen.bot` — Telegram bot implementation (aiogram)

## Cards (`data/cards.yaml`)

Each card has the following fields. Use `___` for blanks in `question` and `recall`.

- `question` — sentence with a blank
- `topic` — verb in infinitive
- `answer` — correct answer (preposition or preposition + article)
- `distractors` — list of 3 wrong options
- `explanation` — dict with `ru` and `en` keys
- `recall` — minimal phrase for the recall step (optional)
- `recall_answer` — list of accepted full sentences for the recall step (optional, required if `recall` is set)

`topic` — глагол в инфинитиве, которому посвящена карточка (например `"sprechen"`, `"sich freuen"`). Рефлексивные глаголы включают `sich`. Карточки с одним глаголом но разными предлогами (`sprechen mit`, `sprechen über`) имеют одинаковый `topic: "sprechen"` — это намеренно, чтобы при ошибке показывались все формы глагола.

Sanity check: substituting the answer into the question must produce a natural, everyday German sentence; substituting any distractor must not produce a grammatically valid one.

Two card types:

**Preposition only** — answer is a single word. Distractors are other plausible prepositions.

**Preposition + article** — answer is a string like `"auf den"`. Use only for Wechselpräpositionen (an, auf, über, in, etc.) where the case is not fixed. Skip for prepositions with fixed case (mit, bei, für, um, nach, zu, aus, von).

Distractor strategy for preposition + article cards — use a 2×2 grid (2 prepositions × 2 cases):
- `[prep1][case1]` — correct answer
- `[prep1][case2]` — correct preposition, wrong case → tests case
- `[prep2][case1]` — wrong preposition, correct case → tests preposition
- `[prep2][case2]` — wrong preposition, wrong case

This ensures each preposition appears exactly twice, so the learner cannot eliminate the wrong preposition by frequency and must choose on all four dimensions.

Case compatibility rule: all distractors must be compatible with the case visible in the sentence. If the noun form clearly shows Akkusativ (e.g. `den`, `einen`, `meinen`), do not use prepositions that only take Dativ (`von`, `mit`, `bei`, `nach`, `zu`, `aus`) as distractors — they can be eliminated without knowing the answer. Same applies in reverse for Dativ nouns. When a noun has no article or the form is ambiguous (e.g. mass nouns without article), any preposition is fine as a distractor.

Special cases:
- `sich freuen`: use `"auf das"` ↔ `"über das"` as a distractor — common confusion between the two constructions
- `sich streiten über`: use `"um das"` — `sich streiten um` is a real expression, making it a plausible mistake

## Recall (`recall` / `recall_answer`)

After the multiple-choice step, the bot asks the user to reconstruct a short phrase from memory.

`recall` — a minimal phrase built from the question's vocabulary: strip adverbs, time expressions, and extra clauses, keep only subject + verb + preposition + noun (+ separable prefix / reflexive pronoun if needed). Show the noun hint in nominative in parentheses. Always one `___` blank regardless of whether the answer is one or two words.

Example:
- Question: `"Ich warte schon eine Stunde ___ den Bus."`
- Recall:   `"Ich warte ___ (der Bus)."`

`recall_answer` — list of accepted full sentences (always a list, even if one item; multiple entries for cases where several phrasings are equally valid).

Vary the subject across cards of the same topic to avoid identical recall prompts.

Sanity check: the recall_answer must be a natural, everyday German sentence.

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
