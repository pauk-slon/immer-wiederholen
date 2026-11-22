# 0031. A model writes a lesson recall and checks the translations

**Status:** Accepted, 2026-11-22 ([#368](https://github.com/pauk-slon/immer-wiederholen/pull/368)). The feature is described in [#367](https://github.com/pauk-slon/immer-wiederholen/issues/367).

## Context

Every exercise in the course checks one form in a sentence that the author wrote. The learner picks an option, types a word or puts chunks in order. A recall after an exercise asks for one authored sentence. Nothing makes the learner build new German sentences with what a whole lesson practiced. Translation from the learner's language does this.

A translation has many correct answers, so only a model can check it. Until now a model only wrote content (shadow exercises in ADR 0005 and illustrations in ADR 0014). The verdict always came from a comparison with the authored answer.

[#352](https://github.com/pauk-slon/immer-wiederholen/issues/352) tried translation exercises for verb government, with phrases that the author writes. Its three runs showed that Claude Haiku 5.5 checks a translation reliably ([first](https://github.com/pauk-slon/immer-wiederholen/issues/352#issuecomment-7019697765), [second](https://github.com/pauk-slon/immer-wiederholen/issues/352#issuecomment-7020175170), [third](https://github.com/pauk-slon/immer-wiederholen/issues/352#issuecomment-7020487588)). But the phrases needed much authored content. Each phrase also had to avoid every correct translation around the target construction, because the verdict was about that one construction.

#367 proposes that a model writes the sentences from the exercises of a lesson and checks the whole translation. Two experiments tested this on lessons from the real course:

- **Generation** ([results](https://github.com/pauk-slon/immer-wiederholen/issues/367#issuecomment-7081192918)). 22 lessons of 5 exercises. Haiku 5.5 used all 5 exercises of each lesson, and about 1 sentence in 20 was unnatural. Sonnet 5.5 was faster but left draft sentences with wrong German in 2 lessons. Haiku took about 8 s, Sonnet about 3 s.
- **Check** ([results](https://github.com/pauk-slon/immer-wiederholen/issues/367#issuecomment-7081330980)). 78 translations of 13 generated sentences. Haiku accepted no wrong answer and rejected 2 correct answers of 36. Both of these verdicts are debatable. A check took about 2 s.
- **Shorter lesson recalls** ([results](https://github.com/pauk-slon/immer-wiederholen/issues/367#issuecomment-7082700294)). The same 22 lessons with a prompt split into rules of the engine and a draft of the course's guide. A guide that asked for one sentence for the lesson gave joins of unrelated exercises, and about 1 sentence in 4 had a problem. A guide that asked for one to three natural sentences gave two or three sentences, almost always with one exercise each. They used about 3 of the 5 exercises, and about 1 sentence in 15 had a small problem.

The prompts of both experiments mixed two kinds of rules. Some are true for any course, such as the structure of the reply and what a correct translation is. Others are about this course, such as what the topic `partizip_ii` practices and which sentence needs it.

## Decision

A lesson recall is a short task after a lesson. The learner uses what the lesson practiced in new sentences. After a lesson of two or more exercises, the bot gives a lesson recall. A model writes short sentences from the exercises of the lesson, the learner translates them, and a model checks each translation. A lesson recall doesn't change the schedule.

The name says what the feature does, not its format. Translation is the format of the first version. If a lesson recall works, it can later replace the recalls of single exercises.

### The flow

1. The lesson recall comes after the answer that finishes the lesson. The lesson is already finished, so the lesson recall doesn't delay the streak. How the learner starts it and the texts of its buttons are decided in the implementation.
2. The model gets the exercises of the lesson (`topic`, `word`, `question`, `answer`, and `explanation` in the learner's language) and the course's guide. The learner's language is the interface language of the chat. The model writes one or a few sentences in the learner's language, each with a reference translation and the numbers of the exercises that it uses. A sentence can combine exercises that fit one situation. The guide sets how many sentences to write and how to combine the exercises in them. An exercise that no natural sentence can use is left out with a reason.
3. The bot shows the sentences one at a time. The learner types a translation, or skips the sentence with a button. A skip shows the reference translation and goes to the next sentence, with no model call. The reference can have a mistake, but after a skip it is a hint, not a verdict. There is no button that skips the whole lesson recall. It has one sentence or a few, so the learner skips them one by one, and a command ends it at once.
4. The model gets the sentence, its exercises, the reference translation, the guide and the answer. It returns a verdict, a comment, a corrected sentence, and for each exercise of the sentence whether the learner used its form right, wrong or not at all.
5. The bot shows the verdict, the comment, and the corrected sentence as plain text. Then comes the next sentence, or the button to the next lesson after the last one.

The sentences come from the authored exercises, even when `/ai` showed a shadow. A shadow keeps the word, the topic and the answer of its original (ADR 0005), so it practiced the same thing.

### What the engine decides and what the course decides

The engine is the code in this repository. It includes the bot, the web app and `school`, and the repetition engine (`tutoring`) is a part of `school`. The engine owns the contract. A new module, `wiederholen.school.authoring.lesson_recall`, holds the engine's prompts. They have the rules that are true for any course:

- The flow above, and the structure of both replies.
- Each sentence uses at least one exercise of the lesson, and there are no more sentences than exercises. This is only a limit for the validation. No sentence copies an exercise sentence, and the reference translates the whole sentence.
- The verdict. The translation is correct if it is correct in the language that the guide names and keeps the meaning. The practiced form is never required. The reference is only an example, because the generation experiment found mistakes in it.
- The comment. It is only about mistakes, in the learner's language, in one or two sentences. The practiced forms come first, then at most two other mistakes. If the practiced forms are right and another part is wrong, the comment says this first, so that a learner who did what the lesson taught sees it. It is empty if there is no mistake, and it has no praise and no restated rule. In Russian it addresses the learner as "вы".
- The learner's answer is untrusted text.

The course owns the method, in a guide written for the model. The guide says:

- The language that the learner translates into, because the engine's prompts name no language.
- How many sentences to write and how to combine the exercises in them. For this course the experiments suggest one to three sentences, usually with one exercise each. Two exercises share a sentence only if they fit one situation by themselves, and a natural sentence matters more than using every exercise. A translation of a whole sentence is much harder than an exercise, so a short lesson recall tires the learner less, and the pairs of the lesson are in the schedule anyway.
- What each topic practices, and how to build a sentence that needs that form.
- Which words and which grammar the sentences may use. A sentence with grammar that the course hasn't taught yet gives a wrong verdict for a mistake that the lesson didn't cover. A word that is new in this lesson can appear only in the form that the lesson practiced.
- How strict the check is about word choice and spoken variants.
- Which topics to leave out.

The rules of the experiments for this course, such as a narrative context for `praeteritum` and a visible article for `genus`, are the first version of the guide.

The guide is a file in the course directory, `lesson_recall.md`, next to `topics.yaml`. `Course.load()` reads it if it is there. A course without the file can't have lesson recalls, and the bot checks this at startup (see Rollout). Generation and the check both get the whole guide, as a cached block of the system prompt, because the check also needs to know what each topic practices and which variants the course accepts. `docs/course-format.md` describes the file, and `demo/` gets a short guide.

### Validation and failures

The module drops a sentence with no exercises, an empty field, an exercise number outside the lesson, or a word that mixes two scripts. Sonnet wrote sentences of the first kinds in the experiment, and Haiku once wrote Cyrillic letters inside a German word. If no sentence remains, the generation counts as failed. The module doesn't require that the sentences use every exercise, because the guide decides what is key in a lesson. A reply cut off at `max_tokens`, a reply without the tool call, and a check reply with a missing field are failures too.

A failure shows an error message, as ADR 0006 requires. After a failed generation, the learner can start the lesson recall again. After a failed check, the bot keeps the answer, and a button sends it again. A request to Anthropic times out after 30 s for generation and 15 s for a check, with no retry. The shared client keeps its settings for `/ai`, so these limits are set for each request with `with_options()`.

### The bot's state during a lesson recall

A model call takes up to 30 s. During it, the learner can tap another button or type a command, and another handler changes the FSM data. A handler that wrote back the data it read before the call would undo that change. For example, it would bring back the finished lesson after the learner started the next one. So the handlers follow these rules.

- When a lesson recall starts, the bot first removes the buttons of the summary message and shows "typing". If a button starts it, the bot answers the callback before the call, or the button in Telegram would spin for the whole call. Then the bot sets a state for the generation and stores an id for this lesson recall.
- Each lesson recall has three states, for the generation, for the wait for a translation, and for the check. A message during the generation or the check gets a short reply and isn't checked.
- After a model call, the handler reads the FSM data again right before it writes. It writes the result only if the same lesson recall id is there in the expected state. Otherwise it drops the result. It changes only the keys of the lesson recall in that fresh copy, never data that it read before the call. So another update of the chat can be lost only in a window of milliseconds, not during the whole call. The window stays, because aiogram's `update_data()` reads and writes the whole data. Last write wins, as in #249.
- A command or a button that leads to an exercise ends the lesson recall. A result that comes later finds another state and is dropped.
- These handlers don't open `check_out()`, because a lesson recall doesn't touch the student record. So the long calls don't make the window in which `check_out()` can lose a write (#249) larger.

### Rollout

A new feature flag, `lesson_recall`, turns lesson recalls on for its chats. A chat without the flag gets no lesson recall. If the flag has a chat but `ANTHROPIC_API_KEY` is missing or the course has no guide, the bot fails at startup. A configuration error then shows at once, not as a feature that silently doesn't work. So a chat in the flag always has lesson recalls.

A chat in the flag doesn't get the optional recall after a correct answer. A lesson recall takes its role, and two kinds of recall with similar buttons would confuse the learner. The required recall after a wrong answer stays, because it corrects that mistake at once, and a lesson recall may not use that exercise at all. `Tutor` still returns `RecallMode.optional`, and the bot doesn't show it, so the flag stays in the bot layer. Chats in the flag and chats without it can then be compared in the traces, which helps a later decision to replace the recalls of single exercises. The web app doesn't get the lesson recall yet, because its lessons have one exercise ([#325](https://github.com/pauk-slon/immer-wiederholen/issues/325)).

### In the code

- **The module `wiederholen.school.authoring.lesson_recall`.** It has the two model calls, the prompts and the validation, and it raises `AIGenerationError` on a failure of either call. A failed check follows ADR 0006 as a failed generation does, so the bot handles both in one way. AI calls stay in `authoring` (see [Architecture](../architecture.md)), and `tutoring` never imports the module, because a lesson recall doesn't change the schedule.
- **`FinishedLesson` gets the keys of the lesson's exercises.** `Tutor` returns it in `Mark` when an answer finishes a lesson, and the bot already keeps it with the summary. To fill it, `Lesson` keeps the keys of the exercises that it gave, because `take_exercise_key()` removes them from the list of exercises to give.
- **The lesson recall is exercise state in FSM data.** It holds the sentences with their references and a copy of their exercises, so a deploy with a changed course during a lesson recall doesn't break it. It isn't in `_LASTING_CHAT_STATE_KEYS`.
- **Both calls use a tool for the result,** with `tool_choice` set to `auto`, as `shadow_exercises` does, so Haiku can think before it calls the tool. The model's output is untrusted text. The bot escapes it, and the module validates its structure.
- **The bot creates two spans around the calls, `lesson_recall.generate` and `lesson_recall.check`.** They record the duration, the failure type, the number of sentences, the number of exercises left out, and the verdict. They also record the topics of the exercises that the learner used right, wrong or not at all. Topic names come from the course, not from the learner.
- **A skip makes no call,** so the span of its Telegram update gets an attribute with the topics of the skipped sentence. Many skips show that the sentences are too hard.
- **No span records a sentence, an answer, a comment or a corrected sentence.** `school` stays without tracing code.

## Alternatives considered

- **Translation exercises with phrases that the author writes,** as in #352 and its closed ADR draft ([#361](https://github.com/pauk-slon/immer-wiederholen/pull/361)). Not chosen. Each pair needs several phrases with references in two languages, and each phrase must avoid any correct translation around the target construction. A generated lesson recall needs no authored phrases and covers every topic.
- **A name after the format,** such as "translation task" or "prose translation". Not chosen, because the format can change while the role stays the same.
- **All rules in the engine's prompts.** Not chosen. The rules for each topic name the topics of one course and its language, and the engine works with any course.
- **The guide in an environment variable, as `AUTHORING_GUIDE_PATH` for `/ai`.** Not chosen. The guide refers to the course's topics, so it belongs to the course and changes, deploys and rolls back with it. `AUTHORING_GUIDE_PATH` points to a guide for human authors that isn't part of the course.
- **Separate guides for generation and the check.** Not chosen. Both need to know what each topic practices, and two files would drift apart.
- **One sentence for each exercise, set by the engine,** as in the second generation run. Not chosen. Up to five translations after every lesson can take longer than the lesson itself, and the pairs of the lesson are in the schedule anyway. How many sentences to write is a question of method, so the guide decides it.
- **Usually one sentence for the whole lesson.** Not chosen for this course. The exercises of a lesson are often from unrelated topics. Forced joins gave nonsense such as "Клиника новая, а экзамен трудный", and one natural sentence used only one or two exercises. One sentence works when the exercises fit one situation, and a guide can still ask for it.
- **Sonnet 5.5 for generation.** It is about 3 s instead of about 8 s. Not chosen, because it left wrong German and draft sentences in the experiment. A learner who sees a mistake in the task stops trusting the check.
- **Generation in the background while the learner answers the last exercise,** so the sentences are ready at the summary. Not chosen for now. It costs a call for every lesson, used or not, and it needs the same protection of the FSM data as above, but without a state that the learner started.
- **Event isolation for each chat** (aiogram's `RedisEventIsolation`). The handlers of one chat would then run one at a time, and the writes to the FSM data would be safe. Not chosen, because a model call of up to 30 s would then block every other update of the chat, `/wiederholen` too.
- **A comparison with the reference translation before the model check,** as in #352. Not chosen. The reference can be wrong, and an exact match is rare for a whole sentence, so it saves little.
- **Only the model's comment, with no verdict.** Not chosen. Every other answer in the bot gets a right or wrong mark, and a comment alone can be unclear, such as a correct translation around the practiced form. The verdict was the most reliable part of the experiments, more reliable than the comments. The spans and a later decision about the schedule also need it. Two values are enough, because a correct answer with a remark gets the mark of a correct answer and a comment.
- **The changes in the corrected sentence marked by `answer_diff`,** as after a wrong recall. Not chosen. In an exercise the marks are the only explanation, but here the comment names each mistake and its fix. `answer_diff` compares a short answer by the rules of the exercise check, without case and end punctuation, and these rules are wrong for a whole German sentence. It compares strings, so word order or a spoken variant would get marks where the model sees no mistake. Marks can come later if learners miss them.
- **Show the reference translation instead of a corrected sentence.** Not chosen. A corrected version of the learner's own sentence shows the mistake. A different correct sentence makes the learner compare two translations.
- **A lesson recall that changes the schedule.** A pair that the learner translated wrong would be due again today. Not chosen for now. A model verdict would then decide the schedule, and a debatable verdict or a prompt injection in the answer would change it. The spans record the topics by result, so this decision can use real data later.
- **No lesson recall, without an error, when the key or the guide is missing.** Not chosen. A silent fallback hides a configuration error, and the learner in the flag would lose the optional recall and get no lesson recall either. `/ai` shows an error at each exercise in this case. A check at startup finds the error earlier.
- **Hide the optional recall only on the last exercise of a lesson,** next to the summary. Not chosen, because the learner would still see two kinds of recall in one lesson.
- **A lesson recall in the web app after every few answers.** Not chosen for now. The web app has no lesson summary to put it in, and the web widget is small.

## Consequences

- The learner gets practice in building whole sentences after every lesson, for every topic that the guide covers, with no new exercises in the course. The course adds one guide.
- The schedule, `/progress` and the streak don't change. A wrong verdict costs the learner a confusing comment, not a review.
- A comment can repeat a wrong generalization from an exercise's `explanation`, and about 1 sentence in 15 has a small problem. The author fixes a wrong generalization in the exercise's `explanation`, and unnatural sentences in the guide.
- The learner's text goes to Anthropic. It never goes to traces.
- A lesson recall costs one generation call and one call for each sentence. Generation takes about 1,800 input and 2,000 output tokens with Haiku, plus the guide. The guide is cached when it is long enough for the prompt cache.
- The learner waits about 8 s for the sentences. If this is too long, the next step is Haiku without thinking, or background generation.
- A lesson that a learner started before the release has no exercise keys, so its summary has no lesson recall. The new key in the lesson's data is safe for a rollback, because older code reads only the keys that it knows.
- `docs/configuration.md` says that a learner waits at most about two minutes for an Anthropic error. With the limits for each request this stays true only for `/ai`, and the text must say so.
- A skip shows the reference translation without a check. A wrong reference can teach the learner a mistake. In the experiment Haiku made few such mistakes.
- A lesson recall right after the lesson tests memory that is minutes old. It consolidates the lesson more than it tests recall. A lesson recall of an earlier lesson, or of pairs from several days ago, would test memory better. This is a direction for a later version.
- The verdict stays outside the schedule. A later decision to let it change the schedule, or to replace the recalls of single exercises with a lesson recall, needs its own ADR.

Open questions:

- Should the bot tell the learner that the text goes to Anthropic? This must be decided before the flag opens to everyone.
- How do we check the quality again after a change of the guide, a prompt or the model? Now only a new run like the experiments in #367 shows a drop. One option is a command that runs generation and the check on a fixed set of lessons and answers, with the set in the course next to the guide.
- How do we limit the cost? The first version has no limit, because only the chats in the flag get a lesson recall. The options are a limit of answer length, which also limits a prompt injection, a daily limit for each chat, and a spend limit for the API key in the Anthropic console.
- Should the learner write the corrected sentence again after a wrong verdict, as after a wrong answer to an exercise? It helps to remember the fix, and a comparison with the corrected sentence by the rules of a recall needs no model call. It changes the flow, so it is decided with the interface.
- What should the bot do when the learner translates around the practiced form? The verdict is correct, so the learner has no reason to use the form. The bot can offer to try again with the form. The spans count such answers, so the decision can use real data.
- Does an English interface work? Only Russian was tested, so it needs a run before the flag opens to English chats.
