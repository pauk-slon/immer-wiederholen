# AI-generated content

[`wiederholen.school.authoring`](https://github.com/pauk-slon/immer-wiederholen/tree/main/wiederholen/school/authoring) is the one package that calls generative AI. It has two independent parts:

**Bot only.** The web widget uses neither.

- **shadow exercises** — questions rewritten by an LLM for the `/ai` mode, generated on the fly;
- **cues** — illustrations for sentence exercises, generated ahead of time.

Which topics get them is set per topic in `topics.yaml` (see [Course format](course-format.md#ai-generated-questions-and-illustrations)); the environment variables and the Cloudflare setup are in [Configuration](configuration.md#optional-integrations).

`authoring` is a sibling of `tutoring`, not part of it: it depends only on the course model (`wiederholen.school.curriculum`), so the scheduling engine never gains a network dependency. The two parts share nothing else: different providers, different credentials, and neither imports the other.

## Shadow exercises

The `/ai` command is a toggle for chats with the `ai_exercises` feature flag (see [Telegram bot](bot.md#feature-flags)). With it on, each exercise the scheduler picks is replaced by a **shadow**: a new exercise for the same word and answer, written by Claude.

### What's generated and what's kept

[`generate_shadow_exercise(client, exercise, course, *, authoring_guide=None)`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/school/authoring/shadow_exercises.py) takes the exercise `Tutor.next_exercise()` picked and returns a copy made with `dataclasses.replace()`:

| Kept as authored | Generated |
|---|---|
| `word`, `topic`, `answer`, `word_bank`, `grammar_classes` | `question`, `distractors`, `explanation`, `recalls`, and `description` if the original has one |

Keeping `word`, `topic` and `answer` means the shadow tests exactly what the scheduler chose. The model isn't allowed to pick a different answer, even one that would be correct for its own sentence: that would quietly change what's being practiced (see [ADR 0005](adr/0005-shadow-exercises-keep-the-answer.md)). Scheduling is keyed on those three fields, so a shadow is scheduled like the original. Two generated fields do matter to `check_answer()`, though: the shadow's `recalls` decide whether a recall follows, and its `question` is what's stored as the last exercise shown.

`description` must be regenerated together with the question: it translates the sentence, so keeping the old one would describe a sentence that's no longer there. This was a real bug — a new question about apples from the garden, shown with a description about a table made of wood.

Because `dataclasses.replace()` runs `Exercise.__post_init__()`, the shadow is validated like any authored exercise.

### The request

The model is pinned in `MODEL` (`claude-haiku-4-5-20251001`). Each request has:

- **a system block** with the authoring guide — the exercise-writing guidelines from the content repo, if `AUTHORING_GUIDE_PATH` points at them (see [Configuration](configuration.md#ai-generated-questions)). It's cached by Anthropic's prompt cache, since it's the same for every request. Without a guide, generation relies on the examples alone;
- **a user message** with the exercise to replace and up to three examples of the same topic as a style reference, exercises with the same word first.

The model answers by calling a tool, `submit_shadow_exercise`, whose input schema is the generated fields. The tool isn't forced: the prompt asks the model to reason about the fixed answer's grammar first, in plain text, and then submit.

### Failures

`AIGenerationError` covers everything that can go wrong: the API call fails, the model doesn't call the tool, the tool input is malformed, or the result fails validation. There's deliberately no fallback to the authored exercise: `/ai` is a testing tool, and a silent fallback would hide a broken integration behind questions that look normal. The learner sees an error message, with no button attached; `/wiederholen` tries again, `/ai` turns the mode off (see [ADR 0006](adr/0006-ai-generation-fails-visibly.md)).

### In the bot

Right after `next_exercise()` has picked an exercise, the caller narrows the chat's `ai_mode` to that exercise — `ai_mode and exercise.topic in course.ai_generatable_topics` — and passes it to `_apply_ai_mode()` in `commands/wiederholen.py`:

- if it's off, the exercise passes through unchanged — no error, no marker;
- otherwise it generates a shadow, showing Telegram's "typing…" indicator in the meantime (refreshed every few seconds, since Telegram drops it after about five);
- it returns `None` when there's no Anthropic client or generation failed, and the caller shows the error message. Nothing needs rolling back: `next_exercise()` doesn't write to the record.

A shadow is marked with `🤖` in front of the question. `ai_mode` is a chat setting (see [Telegram bot](bot.md#chat-settings)), so it stays on across exercises.

### Which topics are safe

The kept-answer argument only holds when the answer doesn't depend on the exact wording of the sentence, which is why generation is opt-in per topic. Which kinds of topics that rules out is listed for course authors in [Course format](course-format.md#ai-generated-questions-and-illustrations).

## Cues

A **cue** is an illustration of an exercise's sentence, shown with the question to help remember it: a picture and the sentence it depicts reinforce each other. It suits topics that test understanding of a concrete sentence (the `_meaning` topics), not pure grammar forms. The idea was tried by hand, with an external image generator, before any of this was built.

### Generating

[`cues/__init__.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/school/authoring/cues/__init__.py):

- `build_cue_prompt(exercise)` returns `description.en` plus a fixed style suffix — `", simple clear illustration, single scene, no text or letters in the image"` — or `None` if there's no description. The suffix keeps the set visually consistent and asks for no text in the image: image models often garble letters, and the picture shouldn't show wrong German.
- `generate_exercise_cue(client, exercise, *, account_id, api_token)` sends the prompt to Cloudflare Workers AI (`@cf/black-forest-labs/flux-1-schnell`) and returns the image bytes (JPEG), raising `httpx.HTTPError` on failure. The response wraps the base64 image either as `{"result": {"image": ...}}` or as bare `{"image": ...}`, and both are accepted.

[`cues/__main__.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/school/authoring/cues/__main__.py) is the generator, run on demand after content changes (`python -m wiederholen.school.authoring.cues`). For each exercise of a topic with `cue_generation`, it checks whether a cue exists — a cheap `HEAD` request — and if not, generates and uploads one. At the end it logs one summary line: generated, already had one, no description, failed. There's no review step before upload: that summary is what the person who ran it reads to spot-check the result.

It's a one-off command rather than a service because exercises change rarely, at authoring time. It lives next to the code it drives rather than beside `bot` and `web`, since it's an authoring tool, not a frontend; and it's a package's `__main__` rather than a `cues.py` with `if __name__ == "__main__"` because `authoring/__init__.py` imports `cues`, and `python -m` on an already-imported module runs it a second time (runpy's "found in sys.modules" warning). It's the one module under `wiederholen.school` that reads environment variables, which is fine since nothing imports it.

### Keys

Cues are stored under `Exercise.cue_key`, the SHA-256 of the exercise's `question`. It's computed in one place, so the generator and the bot always agree. It's keyed by the question rather than by word and topic because several exercises of a topic can share a word, each with its own sentence and picture.

Editing a question's text changes its key, so its cue is orphaned: it's never shown for the wrong sentence, but the question has no picture until the generator runs again.

### Storing and showing

[`wiederholen.school.cue_store`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/school/cue_store.py):

- **`CueStore`** declares `get_cue_url(exercise)` and `upload_cue(exercise, image_bytes)`.
- **`R2CueStore`** implements it on Cloudflare R2 with `aioboto3`, an async S3 client: `head_object` to check, `put_object` to upload (as `image/jpeg`). A cue's URL is `R2_PUBLIC_URL_BASE` plus the key (see [Configuration](configuration.md#illustrations)).
- **`CachedCueStore`** wraps it in the bot with an in-process cache for 12 hours, so rendering a question doesn't hit R2 every time. "No cue yet" is cached too, so a new cue can take up to 12 hours to appear; a restart clears the cache. The cache is in-process because the bot runs as one process, and losing it on restart costs only a few `HEAD` requests.

In the bot, `bootstrap.load_cue_store()` builds the cached store, or returns `None` when R2 isn't configured. `_answer_with_optional_cue()` sends a question as a photo with the text as caption when the topic has cues, one exists, and the text fits Telegram's 1024-character caption limit — otherwise as plain text. A failed lookup is logged and falls back to text, so storage problems never block practice.

## Testing

- **Shadow exercises**: [`tests/school/authoring/test_shadow_exercises.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/tests/school/authoring/test_shadow_exercises.py) mocks the client as `Mock(spec=AsyncAnthropic)` and builds the model's response from `Mock(spec=Message)` and `Mock(spec=ToolUseBlock, input=...)`, so each failure path — no tool call, malformed input, invalid result — is one fake response.
- **Cue generation**: `tests/school/authoring/cues/test_generation.py` mocks Workers AI as `Mock(spec=httpx.AsyncClient)` returning a `Mock(spec=httpx.Response)`; `test_main.py` runs the generator against a mocked store.
- **Storage**: `tests/school/test_cue_store.py` covers `R2CueStore` and the cache.
- **In the bot**: handler tests pass a mocked `anthropic_client` or `cue_store` to `feed_message(...)`, the same way they pass the course.

## Decisions

- [ADR 0005](adr/0005-shadow-exercises-keep-the-answer.md): shadow exercises keep the answer.
- [ADR 0006](adr/0006-ai-generation-fails-visibly.md): AI generation fails visibly, without a fallback.
- [ADR 0014](adr/0014-cues-generated-ahead.md): illustrations are generated ahead of time.
- [ADR 0017](adr/0017-cues-keyed-by-question-hash.md): illustrations are keyed by the question's hash.
