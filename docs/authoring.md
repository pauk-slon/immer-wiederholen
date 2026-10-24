# AI-generated content

[`wiederholen.school.authoring`](https://github.com/pauk-slon/immer-wiederholen/tree/main/wiederholen/school/authoring) is the one package that calls generative AI. Both of its parts work only in the bot. The two parts are independent:

- **Shadow exercises** are exercises that Claude writes for the `/ai` mode. They are generated when the bot shows them.
- **Cues** are illustrations for sentence exercises. They are generated ahead of time.

`topics.yaml` sets which topics get them (see [Course format](course-format.md#ai-generated-questions-and-illustrations)). [Configuration](configuration.md#optional-integrations) lists the environment variables and the Cloudflare setup.

`authoring` is a sibling of `tutoring`, not a part of it. It depends only on the course model (`wiederholen.school.curriculum`), so the repetition engine never gets a network dependency. The two parts share nothing else. They use different providers and different credentials, and neither imports the other.

## Shadow exercises

The `/ai` command enables or disables AI mode for chats with the `ai_exercises` feature flag (see [Telegram bot](bot.md#feature-flags)). In AI mode, the bot replaces each exercise that `Tutor` picks with a **shadow**. A shadow is a new exercise for the same word and answer, written by the model.

### What's generated and what's kept

[`generate_shadow_exercise(client, exercise, course, *, authoring_guide=None)`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/school/authoring/shadow_exercises.py) takes the exercise that `Tutor.next_exercise()` picked. It returns a copy made with `dataclasses.replace()`:

| Kept as authored | Generated |
|---|---|
| `word`, `topic`, `answer`, `word_bank`, `grammar_classes` | `question`, `distractors`, `explanation`, `recalls`, and `description` if the original has one |

Because the shadow keeps `word`, `topic` and `answer`, it tests exactly what `Tutor` chose. The model can't pick a different answer, even one that would be correct for its own sentence. A different answer would silently change what the learner practices (see [ADR 0005](adr/0005-shadow-exercises-keep-the-answer.md)). The schedule uses `word` and `topic` as its key, and `chains_by_answer` uses `answer`, so a shadow is scheduled like the original. But two generated fields do matter to `check_answer()`. The shadow's `recalls` decide whether a recall follows, and its `question` is stored as the last exercise shown.

The model must generate `description` together with the question. The description translates the sentence, so the old description would describe a sentence that no longer exists.

`dataclasses.replace()` runs `Exercise.__post_init__()`, so the shadow is validated like any authored exercise.

### The request

`MODEL` pins the model (`claude-haiku-4-5-20251001`). Each request has two parts:

- **A system block with the authoring guide.** The guide has the guidelines for writing exercises from the content repo, if `AUTHORING_GUIDE_PATH` points to them (see [Configuration](configuration.md#ai-generated-questions)). The block is the same for every request, so Anthropic's prompt cache caches it. Without a guide, the generation uses only the examples.
- **A user message with the exercise to replace.** It also has up to three examples of the same topic as a style reference. Exercises with the same word come first.

The model answers with a call to a tool, `submit_shadow_exercise`. The input schema of the tool is the generated fields. The call isn't forced, because the prompt asks the model to reason first, in plain text, about the grammar of the fixed answer. Then the model submits.

### Failures

`AIGenerationError` covers all failures. The API call can fail, the model can skip the tool call, the tool input can be malformed, or the result can fail validation. The bot intentionally doesn't show the authored exercise instead. `/ai` is a testing tool, and a silent fallback would hide a broken integration behind questions that look normal. The learner sees an error message without buttons. `/wiederholen` tries again, and `/ai` disables the mode (see [ADR 0006](adr/0006-ai-generation-fails-visibly.md)).

### In the bot

Right after `next_exercise()` picks an exercise, the caller computes whether AI mode applies to it, with `ai_mode and exercise.topic in course.ai_generatable_topics`. The caller passes the result to `_apply_ai_mode()` in `commands/wiederholen.py`:

- If the result is false, `_apply_ai_mode()` returns the exercise unchanged, with no error and no marker.
- Otherwise it generates a shadow. Meanwhile, it shows Telegram's "typing…" indicator and sends it again every few seconds, because Telegram removes it after about five seconds.
- It returns `None` if there is no Anthropic client or the generation failed. The caller then shows the error message. Nothing needs to be undone, because `next_exercise()` doesn't write to the record.

The bot marks a shadow with `🤖` in front of the question. `ai_mode` is a chat setting (see [Telegram bot](bot.md#chat-settings)), so it stays on from one exercise to the next.

### Which topics are safe

A kept answer is correct only if the answer doesn't depend on the exact wording of the sentence. For this reason, each topic must enable generation explicitly. [Course format](course-format.md#ai-generated-questions-and-illustrations) lists for course authors which kinds of topics this excludes.

## Cues

A **cue** is an illustration of an exercise's sentence. The bot shows it with the question to help the learner remember the sentence, because a picture and the sentence that it shows support each other. Cues suit topics that test the understanding of a concrete sentence, such as the `_meaning` topics. They don't suit pure grammar forms.

### Generating

[`cues/__init__.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/school/authoring/cues/__init__.py) has two functions:

- **`build_cue_prompt(exercise)`** returns `description.en` with a fixed style suffix, `", simple clear illustration, single scene, no text or letters in the image"`. It returns `None` if the exercise has no description. The suffix keeps the illustrations visually consistent. It also asks for no text in the image, because image models often distort letters, and the picture shouldn't show wrong German.
- **`generate_exercise_cue(client, exercise, *, account_id, api_token)`** sends the prompt to Cloudflare Workers AI (`@cf/black-forest-labs/flux-1-schnell`) and returns the image bytes (JPEG). It raises `httpx.HTTPError` on failure. The response has the base64 image either as `{"result": {"image": ...}}` or as `{"image": ...}`, and the function accepts both.

[`cues/__main__.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/school/authoring/cues/__main__.py) is the generator. You run it after content changes (`python -m wiederholen.school.authoring.cues`). For each exercise of a topic with `cue_generation`, it checks with a cheap `HEAD` request whether a cue exists. If not, it generates a cue and uploads it. At the end it logs one summary line with four counts: generated, already had one, no description, failed. There's no review step before the upload. The person who runs the generator reads the summary and checks samples of the result.

The generator is a one-off command, not a service, because exercises change rarely, at authoring time. It is next to the code that it uses, not next to `bot` and `web`, because it is an authoring tool and not a frontend. It is the `__main__` of a package, not a `cues.py` with `if __name__ == "__main__"`. The reason is that `authoring/__init__.py` imports `cues`, and `python -m` on a module that is already imported runs it a second time (runpy's "found in sys.modules" warning). It is the one module under `wiederholen.school` that reads environment variables. This is acceptable, because no module imports it.

### Keys

Cues are stored under `Exercise.cue_key`, the SHA-256 of the exercise's `question`. The key is computed in one place, so the generator and the bot always agree. The key comes from the question and not from the word and topic, because several exercises of a topic can share a word, each with its own sentence and picture.

If you edit the text of a question, its key changes, and its old cue is no longer used. The bot never shows that cue for the wrong sentence. But the question has no picture until the generator runs again.

### Storing and showing

[`wiederholen.school.cue_store`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/school/cue_store.py) has three classes:

- **`CueStore`** declares `get_cue_url(exercise)` and `upload_cue(exercise, image_bytes)`.
- **`R2CueStore`** implements `CueStore` on Cloudflare R2 with `aioboto3`, an async S3 client. It uses `head_object` to check for a cue and `put_object` to upload one (as `image/jpeg`). The URL of a cue is `R2_PUBLIC_URL_BASE` followed by the key (see [Configuration](configuration.md#illustrations)).
- **`CachedCueStore`** wraps `R2CueStore` in the bot with an in-process cache for 12 hours, so the bot doesn't call R2 every time it shows a question. The cache also stores "no cue yet", so a new cue can take up to 12 hours to appear. A restart clears the cache. The cache is in-process because the bot runs as one process, and the loss of the cache on restart costs only a few `HEAD` requests.

In the bot, `bootstrap.load_cue_store()` builds the cached store. It returns `None` if R2 isn't configured. `_answer_with_optional_cue()` sends a question as a photo with the text as its caption if all of these are true:

- the topic has cues
- a cue exists for the question
- the text fits Telegram's caption limit of 1024 characters

Otherwise it sends plain text. If the lookup fails, the bot logs the error and sends text, so storage problems never stop practice.

## Testing

- **Shadow exercises.** [`tests/school/authoring/test_shadow_exercises.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/tests/school/authoring/test_shadow_exercises.py) mocks the client as `Mock(spec=AsyncAnthropic)`. It builds the model's response from `Mock(spec=Message)` and `Mock(spec=ToolUseBlock, input=...)`, so each failure path, such as no tool call, malformed input or an invalid result, is one fake response.
- **Cue generation.** `tests/school/authoring/cues/test_generation.py` mocks Workers AI as `Mock(spec=httpx.AsyncClient)` that returns a `Mock(spec=httpx.Response)`. `test_main.py` runs the generator against a mocked store.
- **Storage.** `tests/school/test_cue_store.py` covers `R2CueStore` and the cache.
- **In the bot.** Handler tests pass a mocked `anthropic_client` or `cue_store` to `feed_message(...)`, the same way they pass the course.

## Decisions

- [Shadow exercises keep the answer](adr/0005-shadow-exercises-keep-the-answer.md) (ADR 0005)
- [AI generation fails visibly, without a fallback](adr/0006-ai-generation-fails-visibly.md) (ADR 0006)
- [Illustrations are generated ahead of time](adr/0014-cues-generated-ahead.md) (ADR 0014)
- [Illustrations are keyed by the question's hash](adr/0017-cues-keyed-by-question-hash.md) (ADR 0017)
