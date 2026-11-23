# AI-generated content

[`wiederholen.school.authoring`](https://github.com/pauk-slon/immer-wiederholen/tree/main/wiederholen/school/authoring) is the one package that calls generative AI. All of its parts work only in the bot. The parts are independent:

- **Lesson recalls** are translation tasks that Claude writes after a lesson. Claude also checks the translations.
- **Cues** are illustrations for sentence exercises. They are generated ahead of time.

`topics.yaml` sets which topics get cues (see [Course format](course-format.md#illustrations)). [Configuration](configuration.md#optional-integrations) lists the environment variables and the Cloudflare setup.

`authoring` is a sibling of `tutoring`, not a part of it. It depends only on the course model (`wiederholen.school.curriculum`), so the repetition engine never gets a network dependency. The parts share only `AIGenerationError` (in `errors.py`). Lesson recalls use Anthropic. Cues use another provider with other credentials. No part imports another.

## Lesson recalls

A lesson recall is a short translation task after a lesson. Claude writes sentences in the learner's language from the exercises of the lesson, and then checks each translation of the learner (see [ADR 0031](adr/0031-model-writes-and-checks-a-lesson-recall.md)). [`lesson_recall.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/school/authoring/lesson_recall.py) has the two model calls. [Telegram bot](bot.md#lesson-recall) describes how the bot uses them.

### The method and the engine

The course owns the method. Its guide, `lesson_recall.md`, says how to write the task and when a translation is correct (see [Course format](course-format.md#lesson_recallmd)). The engine's prompts have only the steps of a lesson recall and the structure of the replies. How to write a sentence, for example whether to start from the sentence in the language of the course, is method, so it is in the guide. The rules don't say which of `text` and `reference` comes first. Each request has two system blocks, first the engine's rules and then the guide. Both are the same for every request of the course, so a cache breakpoint follows the guide. The cache works only if the prefix reaches the model's minimum length, which a short guide may not reach.

The module checks only the structure of a reply. It never looks at the language or the content of a sentence. A bad sentence reaches the learner.

### Writing the task

`generate_lesson_recall(client, exercises, *, wrong_exercise_keys, guide, language)` sends the exercises of the lesson in their order. For each exercise, it sends `topic`, `word`, `question`, every answer and `explanation` in the learner's language. It marks the exercises with a key in `wrong_exercise_keys`. The model calls the `submit_task` tool with sentences. Each sentence has `text` in the learner's language, a `reference` with the same sentence in the language that the learner translates into, and the numbers of its exercises. The tool also has `left_out`, the exercises that no sentence uses, with a reason. The module doesn't use `left_out`. It only gives the model a place to explain a skipped exercise.

The function returns a `LessonRecall` with a copy of the exercises, the sentences and the learner's language. Each sentence is a `LessonRecallSentence` with `text`, `reference` and `exercise_indexes`, the positions of its exercises in `LessonRecall.exercises`. The sentences refer to the exercises by position, so they stay together in one object. A check then always sees the exercises that the task came from, even if the course changed. The language is the language at the start, so `/language` during a lesson recall doesn't change the check. The function drops a sentence with an empty field, with no exercises or with a number outside the lesson. It also drops the sentences after as many as the lesson has exercises. An exercise that a sentence lists twice counts once. The bot stores a `LessonRecall` in its FSM data with `to_dict()` and `from_dict()`.

### Checking a translation

`check_translation(client, lesson_recall, sentence_index, answer, *, guide)` sends the sentence, its exercises, the reference and the learner's answer, in the language of the lesson recall. The answer is in `<answer>` tags, and the rules say that it is text to check, never instructions. The function replaces `<` and `>` in the answer with `‹` and `›`, so the answer can't close its tag. A prompt injection could at worst get a wrong verdict, which doesn't change the schedule (see [ADR 0031](adr/0031-model-writes-and-checks-a-lesson-recall.md)). The reference is only a guide, because the model's translation can be wrong. The model calls the `submit_check` tool with `correct` and `explanation`. The function returns a `TranslationCheck` with `is_correct` and `explanation`. An empty explanation becomes `None`. The explanation is plain text from the model, so the bot sends it without `parse_mode` (see [Telegram bot](bot.md#the-states)).

### The request

`MODEL` pins Claude Haiku 5.5. In the runs of [#367](https://github.com/pauk-slon/immer-wiederholen/issues/367), Sonnet 5.5 was faster but left wrong German in the task. Both calls use effort `low` and a tool with `tool_choice` `auto`, because Haiku thinks before it calls the tool. The timeouts are 30 s for the task and 15 s for a check, with no retry, also not for 429 or 529 (overloaded). The learner then sees an error message and can try again. They are set per request with `with_options()`, so the shared client keeps the SDK's defaults.

Each call that gets a reply adds its token counts to the current span as `lesson_recall.*` attributes (see [Observability](tracing.md#what-gets-traced)). The module uses only the OpenTelemetry API.

### Failures

`AIGenerationError` covers all failures (see [ADR 0006](adr/0006-ai-generation-fails-visibly.md)):

- the API call fails or times out
- the reply is cut off at `max_tokens`
- the reply has no call of the expected tool, or its input isn't an object
- the task has no usable sentence
- the check has no boolean verdict, or its explanation isn't a string

## Cues

A **cue** is an illustration of an exercise's sentence. The bot shows it with the question to help the learner remember the sentence, because a picture and the sentence that it shows support each other. Cues suit topics that test the understanding of a concrete sentence, such as the `_meaning` topics. They don't suit pure grammar forms.

### Generating

[`cues/__init__.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/school/authoring/cues/__init__.py) has two functions:

- **`build_cue_prompt(exercise)`** returns the scene in `cue`, or else `description.en`, with a fixed style suffix, `", simple clear illustration, single scene, no text or letters in the image"`. It returns `None` for `cue: false` and for an exercise with neither a scene nor a description. The suffix keeps the illustrations visually consistent. It also asks for no text in the image, because image models often distort letters, and the picture shouldn't show wrong German.
- **`generate_exercise_cue(client, exercise, *, account_id, api_token)`** sends the prompt to Cloudflare Workers AI (`@cf/black-forest-labs/flux-1-schnell`) and returns the image bytes (JPEG). It raises `httpx.HTTPError` on failure. The response has the base64 image either as `{"result": {"image": ...}}` or as `{"image": ...}`, and the function accepts both.

[`cues/__main__.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/school/authoring/cues/__main__.py) is the generator. You run it after content changes (`python -m wiederholen.school.authoring.cues`). For each exercise of a topic with `cue_generation`, it checks with a cheap `HEAD` request whether a cue exists. If not, it generates a cue and uploads it. It skips an exercise with `cue: false` without a request. At the end it logs one summary line with five counts: generated, already had one, no description, turned off, failed. There's no review step before the upload. The person who runs the generator reads the summary and checks samples of the result.

The generator is a one-off command, not a service, because exercises change rarely, at authoring time. It is next to the code that it uses, not next to `bot` and `web`, because it is an authoring tool and not a frontend. It is the `__main__` of a package, not a `cues.py` with `if __name__ == "__main__"`. The reason is that `authoring/__init__.py` imports `cues`, and `python -m` on a module that is already imported runs it a second time (runpy's "found in sys.modules" warning). It is the one module under `wiederholen.school` that reads environment variables. This is acceptable, because no module imports it.

### Keys

Cues are stored under `Exercise.cue_key`, the SHA-256 of the exercise's `question`, or of `question` and the scene if `cue` has one (see [ADR 0030](adr/0030-cue-field-sets-the-scene-or-turns-it-off.md)). The key is computed in one place, so the generator and the bot always agree. The key comes from the question and not from the word and topic, because several exercises of a topic can share a word, each with its own sentence and picture.

If you edit the text of a question or its scene, its key changes, and its old cue is no longer used. The bot never shows that cue for the wrong sentence. But the question has no picture until the generator runs again. So a course author fixes a bad cue with a scene in `cue`, and the next run of the generator draws the scene.

### Storing and showing

[`wiederholen.school.cue_store`](https://github.com/pauk-slon/immer-wiederholen/blob/main/wiederholen/school/cue_store.py) has three classes:

- **`CueStore`** declares `get_cue_url(exercise)` and `upload_cue(exercise, image_bytes)`.
- **`R2CueStore`** implements `CueStore` on Cloudflare R2 with `aioboto3`, an async S3 client. It uses `head_object` to check for a cue and `put_object` to upload one (as `image/jpeg`). The URL of a cue is `R2_PUBLIC_URL_BASE` followed by the key (see [Configuration](configuration.md#illustrations)).
- **`CachedCueStore`** wraps `R2CueStore` in the bot with an in-process cache for 12 hours, so the bot doesn't call R2 every time it shows a question. The cache also stores "no cue yet", so a new cue can take up to 12 hours to appear. A restart clears the cache. The cache is in-process because the bot runs as one process, and the loss of the cache on restart costs only a few `HEAD` requests.

In the bot, `bootstrap.load_cue_store()` builds the cached store. It returns `None` if R2 isn't configured. `_answer_with_optional_cue()` sends a question as a photo with the text as its caption if all of these are true:

- the topic has cues
- the exercise doesn't have `cue: false`
- a cue exists for the question
- the text fits Telegram's caption limit of 1024 characters

Otherwise it sends plain text. If the lookup fails, the bot logs the error and sends text, so storage problems never stop practice.

## Testing

- **Lesson recalls.** [`tests/school/authoring/test_lesson_recall.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/tests/school/authoring/test_lesson_recall.py) mocks the client as `Mock(spec=AsyncAnthropic)`. It builds the model's response from `Mock(spec=Message)` and `Mock(spec=ToolUseBlock, input=...)`, so each failure path is one fake response. `with_options()` returns a second `Mock(spec=AsyncAnthropic)`, and the tests check the request that this copy gets.
- **Cue generation.** `tests/school/authoring/cues/test_generation.py` mocks Workers AI as `Mock(spec=httpx.AsyncClient)` that returns a `Mock(spec=httpx.Response)`. `test_main.py` runs the generator against a store mocked as `Mock(spec=R2CueStore)`.
- **Storage.** [`tests/school/test_cue_store.py`](https://github.com/pauk-slon/immer-wiederholen/blob/main/tests/school/test_cue_store.py) covers `R2CueStore` and the cache. It mocks the aioboto3 session as `Mock(spec=aioboto3.Session)`. The S3 client is a plain `Mock`, because aiobotocore builds its class at runtime (see the testing rules in [`CONTRIBUTING.md`](https://github.com/pauk-slon/immer-wiederholen/blob/main/CONTRIBUTING.md)).
- **In the bot.** Handler tests pass a mocked `anthropic_client` or `cue_store` to `feed_message(...)`, the same way they pass the course.

## Decisions

- [Shadow exercises keep the answer](adr/0005-shadow-exercises-keep-the-answer.md) (ADR 0005, superseded by ADR 0032)
- [The /ai mode is removed](adr/0032-ai-mode-removed.md) (ADR 0032)
- [AI generation fails visibly, without a fallback](adr/0006-ai-generation-fails-visibly.md) (ADR 0006)
- [A model writes a lesson recall and checks the translations](adr/0031-model-writes-and-checks-a-lesson-recall.md) (ADR 0031)
- [Illustrations are generated ahead of time](adr/0014-cues-generated-ahead.md) (ADR 0014)
- [Illustrations are keyed by the question's hash](adr/0017-cues-keyed-by-question-hash.md) (ADR 0017)
