# 0031. A model writes a lesson recall and checks the translations

**Status:** Accepted, 2026-11-22 ([#368](https://github.com/pauk-slon/immer-wiederholen/pull/368)). The feature is described in [#367](https://github.com/pauk-slon/immer-wiederholen/issues/367).

## Context

Every exercise in the course checks one form in a sentence that the author wrote. The learner picks an option, types a word or puts chunks in order. A recall after an exercise asks for one authored sentence. Nothing makes the learner build new German sentences with what a whole lesson practiced. Translation from the learner's language does this.

A translation has many correct answers, so only a model can check it. Until now a model only wrote content (shadow exercises in ADR 0005 and illustrations in ADR 0014). The verdict always came from a comparison with the authored answer.

[#352](https://github.com/pauk-slon/immer-wiederholen/issues/352) tried translation exercises for verb government, with phrases that the author writes. Its three runs showed that Claude Haiku 5.5 checks a translation reliably ([first](https://github.com/pauk-slon/immer-wiederholen/issues/352#issuecomment-7019697765), [second](https://github.com/pauk-slon/immer-wiederholen/issues/352#issuecomment-7020175170), [third](https://github.com/pauk-slon/immer-wiederholen/issues/352#issuecomment-7020487588)). But the phrases needed much authored content. Each phrase also had to avoid every correct translation around the target construction, because the verdict was about that one construction.

#367 proposes that a model writes the sentences from the exercises of a lesson and checks the whole translation. Runs on lessons from the real course tested this:

- **Generation** ([results](https://github.com/pauk-slon/immer-wiederholen/issues/367#issuecomment-7081192918)). 22 lessons of 5 exercises. About 1 sentence of Haiku 5.5 in 20 was unnatural. Sonnet 5.5 was faster but left draft sentences with wrong German in 2 lessons. Haiku took about 8 s, Sonnet about 3 s.
- **Check** ([results](https://github.com/pauk-slon/immer-wiederholen/issues/367#issuecomment-7081330980)). 78 translations of 13 generated sentences. Haiku accepted no wrong answer and rejected 2 correct answers of 36. Both of these verdicts are debatable. A check took about 2 s.
- **Shorter lesson recalls** ([results](https://github.com/pauk-slon/immer-wiederholen/issues/367#issuecomment-7082700294)). The same lessons, with the rules of the engine and a draft of the course's guide in separate parts of the prompt. A guide that asked for one to three natural sentences gave two or three, and about 1 sentence in 15 had a small problem.
- **The learner's results** ([results](https://github.com/pauk-slon/immer-wiederholen/issues/367#issuecomment-7083251007)). The same lessons, with the exercises that the learner answered wrong marked. The model used all of them, against 62% without the marks. In 3 lessons it wrote sentences in German instead of Russian.

The prompts of the first two runs mixed two kinds of rules. Some are true for any course, such as the structure of the reply. Others are the method of this course, such as what the topic `partizip_ii` practices, which sentence needs it, and what a comment says.

## Decision

A lesson recall is a short task after a lesson. In the first version it is a translation from the learner's language into the language of the course. After a lesson of two or more exercises, the bot offers a lesson recall. A model writes the task from the exercises of the lesson, the learner's results in them, and the course's guide. The learner translates, and a model checks each translation by the same guide. The check gives a verdict, correct or wrong, and an optional explanation. A lesson recall doesn't change the schedule, `/progress` or the streak.

The name says what the feature does, not its format.

### The flow

1. The bot offers the lesson recall with the lesson summary. The summary follows the last answer of the lesson, or the required recall after a wrong last answer. The lesson is already finished, so the lesson recall doesn't delay the streak. How the learner starts it and the texts of its buttons are decided in the implementation.
2. The model gets the exercises of the lesson (`topic`, `word`, `question`, `answer`, and `explanation` in the learner's language), whether the learner answered each of them wrong, and the guide. It returns sentences in the learner's language, each with a reference translation and the numbers of the exercises that it uses. The learner's language is the interface language of the chat at the start, and it stays the same until the lesson recall ends.
3. The bot shows the sentences one at a time. The learner types a translation, or skips the sentence with a button. A skip shows the reference translation and goes to the next sentence, with no model call. There is no button that skips the whole lesson recall. The learner skips the sentences one by one, and a command ends the lesson recall at once.
4. The model gets the sentence, its exercises, the reference translation, the guide and the answer. It returns the verdict and the explanation.
5. The bot shows the verdict and the explanation as plain text. Then comes the next sentence, or the button to the next lesson after the last one.

The sentences come from the authored exercises, even when `/ai` showed a shadow. A shadow keeps the word, the topic and the answer of its original (ADR 0005), so it practiced the same thing.

### What the engine decides and what the course decides

The engine is the code in this repository. It includes the bot, the web app and `school`, and the repetition engine (`tutoring`) is a part of `school`. A new module, `wiederholen.school.authoring.lesson_recall`, holds the engine's prompts. They have only the rules that are true for any course. These are the flow above, the data that the model gets, the structure of both replies, and that the learner's answer is untrusted text.

The course owns the method, in a guide written for the model. The guide says how to write the task and how to check it. For example, it sets the language of the course, how many sentences to write and which exercises come first, which words and grammar the sentences may use, when a translation is correct, and what the explanation says. The rules of the runs for this course are the first version of the guide.

The guide is a file in the course directory, `lesson_recall.md`, next to `topics.yaml`. `Course.load()` reads it if it is there. A course without the file can't have lesson recalls, and the bot checks this at startup ([Rollout](#rollout)). Generation and the check both get the whole guide, as a cached block of the system prompt. `docs/course-format.md` describes the file, and `demo/` gets a short guide.

### Validation and failures

The module checks only the structure of a reply. It drops a sentence with an empty field, no exercises, or an exercise number outside the lesson. If there are more sentences than exercises, the extra sentences are dropped. If no sentence remains, the generation counts as failed. A reply cut off at `max_tokens`, a reply without the tool call, and a check reply without a verdict are failures too.

The module doesn't check the language or the content of a sentence. A rule in the guide is an instruction to the model, not a check, so a wrong sentence can reach the learner, such as a sentence in German in the last run. It costs the learner a skip.

A failure shows an error message, as ADR 0006 requires. After a failed generation, the learner can start the lesson recall again. After a failed check, the bot keeps the answer, and a button sends it again. A request to Anthropic times out after 30 s for generation and 15 s for a check, with no retry. The shared client keeps its settings for `/ai`, so these limits are set for each request with `with_options()`.

### The bot's state during a lesson recall

A model call takes up to 30 s. During it, the learner can tap another button or type a command, and another handler changes the FSM data. A handler that wrote back the data it read before the call would undo that change. For example, it would bring back the finished lesson after the learner started the next one. So the handlers follow these rules.

- When a lesson recall starts, the bot first removes the buttons of the summary message and shows "typing". If a button starts it, the bot answers the callback before the call, or the button in Telegram would spin for the whole call. Then the bot sets a state for the generation and stores an id for this lesson recall.
- Each lesson recall has three states, for the generation, for the wait for a translation, and for the check. A message during the generation or the check gets a short reply and isn't checked.
- After a model call, the handler reads the FSM data again. It writes only the keys of the lesson recall into this fresh copy, and only if the same lesson recall id is there in the expected state. Otherwise it drops the result. Another update of the chat can then be lost only in the milliseconds between the read and the write, because aiogram's `update_data()` writes the whole data (#249).
- A command or a button that leads to an exercise ends the lesson recall.
- These handlers don't open `check_out()`, because a lesson recall doesn't touch the student record. So a long model call doesn't widen the window in which `check_out()` can lose a write (#249).

### Rollout

A new feature flag, `lesson_recall`, turns lesson recalls on for its chats. A chat without the flag gets no lesson recall. If the flag has a chat but `ANTHROPIC_API_KEY` is missing or the course has no guide, the bot fails at startup. So a chat in the flag always has lesson recalls. Only the bot process checks this, because the reminder worker and the web app don't give lesson recalls. The web app doesn't get the lesson recall yet, because its lessons have one exercise ([#325](https://github.com/pauk-slon/immer-wiederholen/issues/325)).

A chat in the flag doesn't get the optional recall after a correct answer. A lesson recall takes its role, and two kinds of recall with similar buttons would confuse the learner. The required recall after a wrong answer stays, because it corrects that mistake at once, and a lesson recall may not use that exercise at all. `Tutor` still returns `RecallMode.optional`, and the bot doesn't show it, so the flag stays in the bot layer. Chats in the flag and chats without it can then be compared in the traces.

### In the code

- **The module `wiederholen.school.authoring.lesson_recall`.** It has the two model calls, the prompts and the validation, and it raises `AIGenerationError` on a failure of either call. AI calls stay in `authoring` (see [Architecture](../architecture.md)), and `tutoring` never imports the module.
- **`FinishedLesson` gets the keys of the lesson's exercises and which of them the learner answered wrong.** `Tutor` returns it in `Mark` when an answer finishes a lesson, and the bot already keeps it with the summary. To fill it, `Lesson` keeps the keys of the exercises that it gave, because `take_exercise_key()` removes them from the list of exercises to give, and the keys of the wrong answers.
- **A lesson recall is exercise state in FSM data,** not in `_LASTING_CHAT_STATE_KEYS`. It starts from `finished_lesson`, which the next exercise clears, so a tap on an old start button does nothing. Keys that the course no longer has are skipped, as in a lesson, and without keys the lesson recall doesn't start. It holds the sentences, their references, a copy of their exercises and the learner's language, so a deploy with a changed course doesn't break it.
- **The buttons of a lesson recall follow the rules for buttons in `docs/bot.md`.** The skip button, the button that sends an answer again, and the button after the last sentence are each followed by `remember_buttoned_message()`, and a handler that removes them calls `forget_buttoned_message()`.
- **Both calls use a tool for the result,** with `tool_choice` set to `auto`, as `shadow_exercises` does, so Haiku can think before it calls the tool. The model's output is untrusted text. The bot escapes it, and the module validates its structure.
- **The bot creates two spans around the calls, `lesson_recall.generate` and `lesson_recall.check`.** Their attributes are in the `lesson_recall.*` namespace. They record the duration, the failure type, the number of sentences and the verdict. A skip makes no call, so the span of its Telegram update gets the attribute `lesson_recall.skipped`.
- **No span records a sentence, an answer or an explanation.** `school` stays without tracing code.

## Alternatives considered

- **Translation exercises with phrases that the author writes,** as in #352 and its closed ADR draft ([#361](https://github.com/pauk-slon/immer-wiederholen/pull/361)). Not chosen. Each pair needs several phrases with references in two languages, and each phrase must avoid any correct translation around the target construction. A generated lesson recall needs no authored phrases and covers every topic.
- **A name after the format,** such as "translation task" or "prose translation". Not chosen, because the format can change while the role stays the same.
- **The method in the engine's prompts.** Not chosen. The rules for each topic name the topics of one course and its language, and the engine works with any course. The method also changes more often than the engine, and the author changes it without a release of the engine.
- **The guide in an environment variable, as `AUTHORING_GUIDE_PATH` for `/ai`.** Not chosen. The guide refers to the course's topics, so it belongs to the course and changes, deploys and rolls back with it. `AUTHORING_GUIDE_PATH` points to a guide for human authors that isn't part of the course.
- **Separate guides for generation and the check.** Not chosen. Both need to know what each topic practices, and two files would drift apart.
- **Checks of the language and the content in the engine,** such as a sentence that is the same as its reference. Not chosen. Each check is a rule of one language or one method, and the engine would grow a list of them. A wrong sentence costs a skip.
- **Sonnet 5.5 for generation.** It is about 3 s instead of about 8 s. Not chosen, because it left wrong German and draft sentences in the run. A learner who sees a mistake in the task stops trusting the check.
- **Generation in the background while the learner answers the last exercise,** so the sentences are ready at the summary. Not chosen for now. It costs a call for every lesson, used or not, and it needs the same protection of the FSM data as above, but without a state that the learner started.
- **Event isolation for each chat** (aiogram's `RedisEventIsolation`). The handlers of one chat would then run one at a time, and the writes to the FSM data would be safe. Not chosen, because a model call of up to 30 s would then block every other update of the chat, `/wiederholen` too.
- **A comparison with the reference translation before the model check,** as in #352. Not chosen. The reference can be wrong, and an exact match is rare for a whole sentence, so it saves little.
- **Only an explanation, with no verdict.** Not chosen. Every other answer in the bot gets a right or wrong mark, and an explanation alone can be unclear. The verdict was the most reliable part of the runs.
- **A result for each exercise in the check's reply,** such as whether the learner used its form right. Not chosen for now. Nothing in this version uses it. It comes with a decision to let a lesson recall change the schedule.
- **A lesson recall that changes the schedule.** A pair that the learner translated wrong would be due again today. Not chosen for now. A model verdict would then decide the schedule, and a debatable verdict or a prompt injection in the answer would change it.
- **No lesson recall, without an error, when the key or the guide is missing.** Not chosen. A silent fallback hides a configuration error, and a learner in the flag would lose the optional recall and get no lesson recall either. `/ai` shows an error at each exercise in this case. A check at startup finds the error earlier.
- **Hide the optional recall only on the last exercise of a lesson,** next to the summary. Not chosen, because the learner would still see two kinds of recall in one lesson.
- **A lesson recall in the web app after every few answers.** Not chosen for now. The web app has no lesson summary to put it in, and the web widget is small.

## Consequences

- The learner gets practice in building whole sentences after every lesson, with no new exercises in the course. The course adds one guide.
- A wrong verdict costs the learner a confusing explanation, not an extra repetition.
- The quality of the tasks and the explanations depends on the guide. The author fixes a bad sentence or explanation in the guide, or a wrong generalization in an exercise's `explanation`, with no release of the engine.
- The learner's text goes to Anthropic. It never goes to traces.
- A lesson recall costs one generation call and one call for each sentence. In the third run, generation took about 600 input and 1,500 output tokens with Haiku and a draft guide of about 2 KB. Most of the output is thinking. The guide is cached when it is long enough for the prompt cache.
- The learner waits about 8 s for the sentences. If this is too long, the next step is Haiku without thinking, or background generation.
- A chat in the flag has no optional recall, and a lesson recall doesn't use every exercise. So some exercises of a lesson get no task in which the learner writes the form. The comparison of chats in the flag and without it in the traces must show if this costs retention.
- A lesson that a learner started before the release has no exercise keys, so its summary has no lesson recall. The new keys in the lesson's data are safe for a rollback, because older code reads only the keys that it knows.
- `docs/configuration.md` says that a learner waits at most about two minutes for an Anthropic error. With the limits for each request this stays true only for `/ai`, and the text must say so.
- If lesson recalls work, they can replace two things. The recalls of single exercises are one. `/ai` is the other, because a lesson recall brings variety once for each lesson instead of a wait at each exercise. Without `/ai`, a lesson recall keeps `AIGenerationError` and the shared Anthropic client. Each replacement, and a verdict that changes the schedule, needs its own ADR.

Open questions:

- Should the bot tell the learner that the text goes to Anthropic? This must be decided before the flag opens to everyone.
- How do we check the quality again after a change of the guide, a prompt or the model? Now only a new run like those in #367 shows a drop. One option is a command that runs generation and the check on a fixed set of lessons and answers, with the set in the course next to the guide.
- How do we limit the cost? The first version has no limit, because only the chats in the flag get a lesson recall. The options are a limit on the length of an answer, which also limits a prompt injection, a daily limit for each chat, and a spend limit for the API key in the Anthropic console.
- Should the learner write the right sentence again after a wrong verdict, as after a wrong answer to an exercise? It changes the flow, so it is decided with the interface.
- Does an English interface work? Only Russian was tested, so it needs a run before the flag opens to English chats.
