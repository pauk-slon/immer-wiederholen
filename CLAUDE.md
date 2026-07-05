# immer-wiederholen

Telegram bot for practicing German with multiple choice questions (aiogram, Python). Exercises are loaded at startup from the path set by `EXERCISES_PATH` env var (default: `data/exercises.yaml`). Bot commands: `/start`, `/wiederholen` (show a exercise with answer options), `/language` (toggle ru/en).

## Key modules

- `wiederholen.exercises` — exercise domain: `Exercise` dataclass, loading from YAML, random picking
- `wiederholen.i18n` — supported languages (`Language` type, `LANGUAGES` set)
- `wiederholen.bot` — Telegram bot implementation (aiogram)

## Exercises (`data/exercises.yaml`)

Each exercise has the following fields.

- `question` — sentence with a blank (`___`) for government exercises, or with the infinitive in parentheses for partizip exercises (e.g. `"Er ist nach London (fliegen)."`)
- `topic` — verb in infinitive
- `type` — exercise category: `choice` (default) or `input` (keyboard input, not yet implemented)
- `answer` — correct answer
- `distractors` — 3 wrong options for government exercises, 2 for partizip exercises
- `explanation` — dict with `ru` and `en` keys
- `recall` — optional nested object with recall step data:
  - `question` — short phrase for the recall step
  - `answer` — list of accepted full sentences (required; always a list, even if one item)
  - `hint` — dict with `ru` and `en` keys: translation of the noun shown in italics below the recall prompt (optional)

`topic` — verb in infinitive that the exercise is about (e.g. `"sprechen"`, `"sich freuen"`). Reflexive verbs include `sich`. Exercises for the same verb but different prepositions (`sprechen mit`, `sprechen über`) share the same `topic: "sprechen"` — intentionally, so that all forms of the verb are shown together when the user makes a mistake.

Sanity check: substituting the answer into the question must produce a natural, everyday German sentence; substituting any distractor must not produce a grammatically valid one.

Exercise categories (marked with `# category:` comment in YAML):

**`government`** — verb government (preposition exercises). Two subtypes:

- *Preposition only* — answer is a single word. Distractors are other plausible prepositions.
- *Preposition + article* — answer is a string like `"auf den"`. Use only for Wechselpräpositionen (an, auf, über, in, etc.) where the case is not fixed. Skip for prepositions with fixed case (mit, bei, für, um, nach, zu, aus, von).

**`partizip`** — Partizip II forms of strong/irregular verbs. Question shows the infinitive in parentheses instead of `___`. 2 distractors (not 3).

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

## Distractor strategy for partizip exercises

2 distractors, both must look like plausible Partizip II forms of the same verb (same prefix, same `-en` ending). Never use other verbs' Partizip II forms — learner shouldn't need to recognise foreign vocabulary to eliminate distractors.

**Strategy:** apply wrong ablaut vowels to the same verb stem:
- distractor 1: stem with **Präteritum vowel** — the most common learner mistake (e.g. `schlafen → schlief → *geschliefen` instead of `geschlafen`)
- distractor 2: stem with **another wrong vowel** (e.g. infinitive vowel = no ablaut, or a third ablaut class)

Example for `waschen` (Infinitiv: a, Präteritum: u, Partizip: a):
- correct: `gewaschen`
- distractor 1: `gewuschen` (Präteritum vowel u — very common mistake)
- distractor 2: `gewoschen` (another wrong vowel)

**Prefix rule:** verbs with inseparable prefixes (`be-`, `ver-`, `er-`, `ge-`, `ent-`, `emp-`, `miss-`, `zer-`) do not get `ge-` in Partizip II — distractors must follow the same rule (e.g. `verlieren → verloren`, distractors: `verliegen`, `verlaren`, not `geverloren`).

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
