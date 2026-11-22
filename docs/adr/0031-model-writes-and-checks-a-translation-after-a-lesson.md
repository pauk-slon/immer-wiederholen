# 0031. A model writes and checks a translation task after a lesson

**Status:** Accepted, 2026-11-22 ([#PR](https://github.com/pauk-slon/immer-wiederholen/pull/PR)). The feature is described in [#367](https://github.com/pauk-slon/immer-wiederholen/issues/367).

## Context

Every exercise in the course checks one form in a sentence that the author wrote. The learner picks an option, types a word or puts chunks in order. Nothing makes the learner build a whole German sentence and use what a lesson practiced. Translation from the learner's language does this.

A translation has many correct answers, so only a model can check it. Until now a model only wrote content (shadow exercises, ADR 0005, and illustrations, ADR 0014). The verdict always came from a comparison with the authored answer.

[#352](https://github.com/pauk-slon/immer-wiederholen/issues/352) tried translation exercises for verb government, with phrases that the author writes. Its three runs showed that Claude Haiku 5.5 checks a translation reliably ([first](https://github.com/pauk-slon/immer-wiederholen/issues/352#issuecomment-7019697765), [second](https://github.com/pauk-slon/immer-wiederholen/issues/352#issuecomment-7020175170), [third](https://github.com/pauk-slon/immer-wiederholen/issues/352#issuecomment-7020487588)). But the phrases needed much authored content. Each phrase also had to avoid every correct translation around the target construction, because the verdict was about that one construction.

#367 lets a model write the sentences from the exercises of a lesson and check the whole translation. Two experiments tested this on lessons from the real course:

- **Generation** ([results](https://github.com/pauk-slon/immer-wiederholen/issues/367#issuecomment-7081192918)). 22 lessons of 5 exercises. Haiku 5.5 used all 5 exercises of each lesson, and about 1 sentence in 20 was unnatural. Sonnet 5.5 was faster but left draft sentences with wrong German in 2 lessons. Haiku took about 8 s, Sonnet about 3 s.
- **Check** ([results](https://github.com/pauk-slon/immer-wiederholen/issues/367#issuecomment-7081330980)). 78 translations of 13 generated sentences. Haiku accepted no wrong answer and rejected 2 correct answers of 36, both debatable. A check took about 2 s.

## Decision

After a lesson of two or more exercises, the bot offers an optional translation task. A model writes the sentences, and a model checks each translation. The task doesn't change the schedule.

### The task

1. The lesson summary gets the button "Translate sentences" next to the "Next" button. The lesson is already finished, so the task doesn't delay the streak or the next lesson.
2. On a tap, the model gets the exercises of the lesson (`topic`, `word`, `question`, `answer`, `explanation` in the interface language). It writes one short sentence in the learner's language for each exercise, with a reference translation and the numbers of the exercises that the sentence uses. Two exercises share a sentence only if it stays natural. An exercise that no natural sentence can use is skipped with a reason.
3. The bot shows the sentences one at a time. The learner types a translation.
4. The model gets the sentence, its exercises with their rules, the reference translation and the answer. It returns a verdict, a comment, a corrected sentence, and for each exercise of the sentence whether the learner used its form right, wrong or not at all.
5. The bot shows the verdict, the comment, and the corrected sentence with the changes marked by `answer_diff`, as after a wrong recall. Then comes the next sentence, or the "Next" button after the last one.

The sentences come from the authored exercises, even when `/ai` showed a shadow. A shadow keeps the word, the topic and the answer of its original (ADR 0005), so it practiced the same thing.

### The verdict

The translation is correct if it is correct German and keeps the meaning of the sentence. Other words, another word order and spoken variants are correct. A spelling typo that doesn't change a grammatical form is correct. Any grammar mistake, a changed meaning or a missing part makes it wrong.

The practiced form is never required. The reference translation is only a guide, because the generation experiment found mistakes in it. A correct translation around the practiced form is correct, and the comment names the form that the lesson practiced.

### The comment

The comment is about mistakes only, in the interface language, in one or two sentences. Mistakes in the practiced forms come first, then at most two others. It is empty if there is no mistake. It has no praise, no summary and no restated rule. In Russian it addresses the learner as "вы".

### Validation and failures

The engine drops a sentence with no exercises, an empty field, or an exercise number outside the lesson. These came from Sonnet in the experiment. If less than half of the exercises remain in the task, the generation counts as failed.

A failed generation or check shows an error message, as ADR 0006 requires. After a failed generation, the button stays and the learner can try again. After a failed check, the bot keeps the answer, and a button sends it again. A request to Anthropic times out after 30 s for generation and 15 s for a check, with no retry.

### Rollout

The task needs `ANTHROPIC_API_KEY` and a new feature flag, `lesson_translation`. A chat without the flag sees no button. The web app doesn't get the task yet, because its lessons have one exercise ([#325](https://github.com/pauk-slon/immer-wiederholen/issues/325)).

### In the code

- **A new package `wiederholen.school.translation`.** It has the two model calls, the prompts and the validation. It depends only on `wiederholen.school.curriculum`, as `authoring` does. `tutoring` never imports it, because the task doesn't change the schedule.
- **`Lesson` keeps the keys of the exercises that it gave.** `take_exercise_key()` removes a key from the list today, so after the last exercise the lesson no longer knows its exercises.
- **The task is exercise state in FSM data.** It holds the sentences with their references and a copy of their exercises, so a course reload during the task doesn't break it. It isn't in `_LASTING_CHAT_STATE_KEYS`.
- **Two new FSM states.** One for a translation, and one while the model checks it, so that a second message during the check gets a short reply and isn't checked.
- **Both calls use a tool for the result,** with `tool_choice` set to `auto`, as `shadow_exercises` does. Haiku thinks before it calls the tool. The model's output is untrusted text. The bot escapes it, and the engine validates its structure.
- **Two spans, `translation.generate` and `translation.check`.** They record the duration, the failure type, the number of sentences and of skipped exercises, the verdict, and the counts of exercises used right, wrong or not at all. They never record a sentence, an answer, a comment or a corrected sentence.

## Alternatives considered

- **Translation exercises with phrases that the author writes,** as in #352 and its closed ADR draft ([#361](https://github.com/pauk-slon/immer-wiederholen/pull/361)). Not chosen. Each pair needs several phrases with references in two languages, and each phrase must avoid any correct translation around the target construction. A generated task needs no authored content and covers every topic.
- **The task changes the schedule.** A pair that the learner translated wrong would be due again today. Not chosen for now. A model verdict would then decide the schedule, and a debatable verdict or a prompt injection in the answer would change it. The check records the result for each exercise in a span, so this decision can use real data later.
- **Sonnet 5.5 for generation.** It is about 3 s instead of about 8 s. Not chosen, because it left wrong German and draft sentences in the experiment. A learner who sees a mistake in the task stops trusting the check.
- **Generation in the background while the learner answers the last exercise,** so the sentences are ready at the summary. Not chosen for now. The result would have to land in FSM data while another handler writes it, and `check_out()` and FSM data have no protection against that (#249). It also costs a call for every lesson, used or not.
- **Generation on every lesson without a button.** Not chosen, because a lesson then takes longer, and a learner who has no time would break the habit of finishing lessons.
- **A comparison with the reference translation before the model check,** as in #352. Not chosen. The reference can be wrong, and an exact match is rare for a whole sentence, so it saves little.
- **Show the reference translation instead of a corrected sentence.** Not chosen. A corrected version of the learner's own sentence shows the mistake. A different correct sentence makes the learner compare two translations.
- **The task in the web app after every few answers.** Not chosen for now. The web app has no lesson summary to put the task in, and the web widget is small.

## Consequences

- The learner gets practice in building whole sentences after every lesson, for every topic, with no new content in the course.
- The schedule, `/progress` and the streak don't change. A wrong verdict costs the learner a confusing comment, not a review.
- The learner's text goes to Anthropic. It never goes to traces. The bot doesn't tell the learner about Anthropic yet. This is an open question before the flag is opened to everyone.
- About 1 sentence in 20 is unnatural, and a comment can repeat a wrong generalization from an exercise's `explanation`. The author fixes the second in the course.
- Only Russian was tested. An English interface needs a run before the flag opens to English chats.
- A task costs one generation call (about 1,800 input and 2,000 output tokens with Haiku) and one call for each sentence.
- The learner waits about 8 s for the task, with the "typing" action. If this is too long, the next step is Haiku without thinking, or background generation after #249.
- A model now decides a verdict that the learner sees, which ADR 0005 avoided for exercises. It stays outside the schedule, and a later decision to let it change the schedule needs its own ADR.
