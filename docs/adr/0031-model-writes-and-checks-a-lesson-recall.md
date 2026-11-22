# 0031. A model writes and checks a lesson recall

**Status:** Accepted, 2026-11-22 ([#368](https://github.com/pauk-slon/immer-wiederholen/pull/368)). The feature is described in [#367](https://github.com/pauk-slon/immer-wiederholen/issues/367).

## Context

Every exercise in the course checks one form in a sentence that the author wrote. The learner picks an option, types a word or puts chunks in order. A recall after an exercise asks for one authored sentence. Nothing makes the learner build new German sentences with what a whole lesson practiced. Translation from the learner's language does this.

A translation has many correct answers, so only a model can check it. Until now a model only wrote content (shadow exercises, ADR 0005, and illustrations, ADR 0014). The verdict always came from a comparison with the authored answer.

[#352](https://github.com/pauk-slon/immer-wiederholen/issues/352) tried translation exercises for verb government, with phrases that the author writes. Its three runs showed that Claude Haiku 5.5 checks a translation reliably ([first](https://github.com/pauk-slon/immer-wiederholen/issues/352#issuecomment-7019697765), [second](https://github.com/pauk-slon/immer-wiederholen/issues/352#issuecomment-7020175170), [third](https://github.com/pauk-slon/immer-wiederholen/issues/352#issuecomment-7020487588)). But the phrases needed much authored content. Each phrase also had to avoid every correct translation around the target construction, because the verdict was about that one construction.

#367 lets a model write the sentences from the exercises of a lesson and check the whole translation. Two experiments tested this on lessons from the real course:

- **Generation** ([results](https://github.com/pauk-slon/immer-wiederholen/issues/367#issuecomment-7081192918)). 22 lessons of 5 exercises. Haiku 5.5 used all 5 exercises of each lesson, and about 1 sentence in 20 was unnatural. Sonnet 5.5 was faster but left draft sentences with wrong German in 2 lessons. Haiku took about 8 s, Sonnet about 3 s.
- **Check** ([results](https://github.com/pauk-slon/immer-wiederholen/issues/367#issuecomment-7081330980)). 78 translations of 13 generated sentences. Haiku accepted no wrong answer and rejected 2 correct answers of 36, both debatable. A check took about 2 s.

The prompts of both experiments mixed two kinds of rules. Some are true for any course, such as the structure of the reply and what a correct translation is. Others are about this course, such as what the topic `partizip_ii` practices and which sentence needs it.

## Decision

After a lesson of two or more exercises, the bot offers an optional lesson recall. A model writes short sentences from the exercises of the lesson, the learner translates them, and a model checks each translation. A lesson recall doesn't change the schedule.

The name says what the feature does, not its format. Translation is the format of the first version. If a lesson recall works, it can later replace the recalls of single exercises.

### The flow

1. Every message with the lesson summary gets a button that starts the lesson recall. The lesson is already finished, so the lesson recall doesn't delay the streak or the next lesson. The labels are chosen in the implementation.
2. The model gets the exercises of the lesson (`topic`, `word`, `question`, `answer`, `explanation` in the interface language) and the course's guide. It writes one short sentence in the learner's language for each exercise, with a reference translation and the numbers of the exercises that the sentence uses. Two exercises share a sentence only if it stays natural. An exercise that no natural sentence can use is skipped with a reason.
3. The bot shows the sentences one at a time. The learner types a translation.
4. The model gets the sentence, its exercises, the reference translation, the guide and the answer. It returns a verdict, a comment, a corrected sentence, and for each exercise of the sentence whether the learner used its form right, wrong or not at all.
5. The bot shows the verdict, the comment, and the corrected sentence with the changes marked by `answer_diff`, as after a wrong recall. Then comes the next sentence, or the button to the next lesson after the last one.

The sentences come from the authored exercises, even when `/ai` showed a shadow. A shadow keeps the word, the topic and the answer of its original (ADR 0005), so it practiced the same thing.

### What the engine decides and what the course decides

The engine owns the contract. Its prompts in the code hold the rules that are true for any course:

- The flow above, and the structure of both replies.
- One sentence for each exercise, no copy of an exercise sentence, and a reference that translates the whole sentence.
- The verdict. The translation is correct if it is correct in the target language and keeps the meaning. The practiced form is never required, and the reference is only a guide, because the generation experiment found mistakes in it.
- The comment. It is only about mistakes, in the interface language, in one or two sentences. The practiced forms come first, then at most two other mistakes. It is empty if there is no mistake, and it has no praise and no restated rule. In Russian it addresses the learner as "вы".
- The learner's answer is untrusted text.

The course owns the method, in a guide written for the model. The guide says what each topic practices and how to build a sentence that needs that form, which words the sentences may use, how strict the check is about word choice and spoken variants, and which topics to skip. The rules of the experiments for this course, such as a narrative context for `praeteritum` and a visible article for `genus`, are its first version.

The guide is a file in the course directory, `lesson_recall.md`, next to `topics.yaml`. `Course.load()` reads it if it is there. A course without the file has no lesson recall. Generation and the check both get the whole guide, as a cached block of the system prompt, because the check also needs to know what each topic practices and which variants the course accepts. `docs/course-format.md` describes the file, and `demo/` gets a short guide.

### Validation and failures

The engine drops a sentence with no exercises, an empty field, or an exercise number outside the lesson. These came from Sonnet in the experiment. If the remaining sentences use less than half of the exercises, the generation counts as failed. A reply cut off at `max_tokens`, a reply without the tool call, and a check reply with a missing field are failures too.

A failure shows an error message, as ADR 0006 requires. After a failed generation, the learner can start the lesson recall again. After a failed check, the bot keeps the answer, and a button sends it again. A request to Anthropic times out after 30 s for generation and 15 s for a check, with no retry. The shared client keeps its settings for `/ai`, so these limits are set for each request with `with_options()`.

### The bot's state during a lesson recall

A model call takes up to 30 s. During it, the learner can tap another button or type a command, and another handler changes the FSM data. A handler that wrote back the data it read before the call would undo that change. For example, it would bring back the finished lesson after the learner started the next one. So:

- A tap on the button first answers the callback, removes the buttons of the summary message and shows "typing". Then the bot sets a state for the generation and stores an id for this lesson recall. Otherwise the button in Telegram would spin for the whole call.
- Each lesson recall has its own states: generation, waiting for a translation, and the check. A message during the generation or the check gets a short reply and isn't checked.
- After a model call, the handler reads the FSM data again right before it writes. It writes the result only if the same lesson recall id is there in the expected state. Otherwise it drops the result. It changes only the keys of the lesson recall in that fresh copy, never data that it read before the call. aiogram's `update_data()` still reads and writes the whole data, so an update of the same chat between the two steps can be lost. This makes the window milliseconds instead of the duration of the call, with the same rule of the last write as in #249.
- A command or a button that leads to an exercise ends the lesson recall. A result that comes later finds another state and is dropped.

These handlers don't open `check_out()`, because a lesson recall doesn't touch the student record. So the long calls don't make the window of #249 larger.

### Rollout

A lesson recall needs `ANTHROPIC_API_KEY`, the guide in the course, and a new feature flag, `lesson_recall`. A chat without the flag doesn't see the button. The web app doesn't get the lesson recall yet, because its lessons have one exercise ([#325](https://github.com/pauk-slon/immer-wiederholen/issues/325)).

### In the code

- **A new module `wiederholen.school.authoring.lesson_recall`.** It has the two model calls, the prompts and the validation, and it raises `AIGenerationError` on a failure of either call. A failed check follows ADR 0006 as a failed generation does, so the bot handles both in one way. AI calls stay in `authoring` (see [Architecture](../architecture.md)), and `tutoring` never imports it, because a lesson recall doesn't change the schedule.
- **`FinishedLesson` gets the keys of the lesson's exercises.** `Tutor` returns it in `Mark` when an answer finishes a lesson, and the bot already keeps it with the summary. To fill it, `Lesson` keeps the keys of the exercises that it gave, because `take_exercise_key()` removes them from the list of exercises to give.
- **The lesson recall is exercise state in FSM data.** It holds the sentences with their references and a copy of their exercises, so a deploy with a changed course during a lesson recall doesn't break it. It isn't in `_LASTING_CHAT_STATE_KEYS`.
- **Both calls use a tool for the result,** with `tool_choice` set to `auto`, as `shadow_exercises` does, so Haiku can think before it calls the tool. The model's output is untrusted text. The bot escapes it, and the module validates its structure.
- **The bot creates two spans around the calls, `lesson_recall.generate` and `lesson_recall.check`.** They record the duration, the failure type, the number of sentences and of skipped exercises, the verdict, and the topics of the exercises used right, wrong or not at all. Topic names come from the course, not from the learner. They never record a sentence, an answer, a comment or a corrected sentence. `school` stays without tracing code.

## Alternatives considered

- **Translation exercises with phrases that the author writes,** as in #352 and its closed ADR draft ([#361](https://github.com/pauk-slon/immer-wiederholen/pull/361)). Not chosen. Each pair needs several phrases with references in two languages, and each phrase must avoid any correct translation around the target construction. A generated lesson recall needs no authored phrases and covers every topic.
- **A name after the format,** such as "translation task" or "prose translation". Not chosen, because the format can change while the role stays the same.
- **All rules in the engine's prompt.** Not chosen. The rules for each topic name the topics of one course and its language, and the engine doesn't depend on a course.
- **The guide in an environment variable, as `AUTHORING_GUIDE_PATH` for `/ai`.** Not chosen. The guide refers to the course's topics, so it belongs to the course and changes, deploys and rolls back with it. `AUTHORING_GUIDE_PATH` points to a guide for human authors that isn't part of the course.
- **Separate guides for generation and the check.** Not chosen. Both need to know what each topic practices, and two files would drift apart.
- **A lesson recall that changes the schedule.** A pair that the learner translated wrong would be due again today. Not chosen for now. A model verdict would then decide the schedule, and a debatable verdict or a prompt injection in the answer would change it. The spans record the result for each exercise, so this decision can use real data later.
- **Sonnet 5.5 for generation.** It is about 3 s instead of about 8 s. Not chosen, because it left wrong German and draft sentences in the experiment. A learner who sees a mistake in the task stops trusting the check.
- **Event isolation for each chat** (aiogram's `RedisEventIsolation`). The handlers of one chat would then run one at a time, and the writes to the FSM data would be safe. Not chosen, because a model call of up to 30 s would then block every other update of the chat, `/wiederholen` too.
- **Generation in the background while the learner answers the last exercise,** so the sentences are ready at the summary. Not chosen for now. It costs a call for every lesson, used or not, and it needs the same protection of the FSM data as above, but without a state that the learner started.
- **A lesson recall after every lesson without a button.** Not chosen, because a lesson then takes longer, and a learner who has no time would break the habit of finishing lessons.
- **A comparison with the reference translation before the model check,** as in #352. Not chosen. The reference can be wrong, and an exact match is rare for a whole sentence, so it saves little.
- **Show the reference translation instead of a corrected sentence.** Not chosen. A corrected version of the learner's own sentence shows the mistake. A different correct sentence makes the learner compare two translations.
- **A lesson recall in the web app after every few answers.** Not chosen for now. The web app has no lesson summary to put it in, and the web widget is small.

## Consequences

- The learner gets practice in building whole sentences after every lesson, for every topic, with no new exercises in the course. The course adds one guide.
- The schedule, `/progress` and the streak don't change. A wrong verdict costs the learner a confusing comment, not a review.
- A comment can repeat a wrong generalization from an exercise's `explanation`, and about 1 sentence in 20 is unnatural. The author fixes the first in the course and the second in the guide.
- The learner's text goes to Anthropic. It never goes to traces. The bot doesn't tell the learner about Anthropic yet. This is an open question before the flag is opened to everyone.
- Only Russian was tested. An English interface needs a run before the flag opens to English chats.
- A lesson recall costs one generation call (about 1,800 input and 2,000 output tokens with Haiku, plus the guide, which is cached when it is long enough for the prompt cache) and one call for each sentence.
- The learner waits about 8 s for the sentences. If this is too long, the next step is Haiku without thinking, or background generation.
- A lesson that a learner started before the release has no exercise keys, so its summary has no lesson recall. The new key in the lesson's data is safe for a rollback, because older code reads only the keys that it knows.
- `docs/configuration.md` says that a learner waits at most about two minutes for an Anthropic error. With the per-request limits this stays true only for `/ai`, and the text must say so.
- A model now decides a verdict that the learner sees, which ADR 0005 avoided for exercises. It stays outside the schedule. A later decision to let it change the schedule, or to replace the recalls of single exercises with a lesson recall, needs its own ADR.
