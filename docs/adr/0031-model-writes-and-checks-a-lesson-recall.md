# 0031. A model writes a lesson recall and checks the translations

**Status:** Accepted, 2026-11-22 ([#368](https://github.com/pauk-slon/immer-wiederholen/pull/368)). The feature and the implementation notes are in [#367](https://github.com/pauk-slon/immer-wiederholen/issues/367).

## Context

Every exercise checks one form in a sentence that the author wrote. Nothing makes the learner build new German sentences with what a lesson practiced. Translation from the learner's language does this, but a translation has many correct answers, so only a model can check it. Until now a model only wrote content (ADR 0005, ADR 0014), and the verdict always came from the authored answer.

[#352](https://github.com/pauk-slon/immer-wiederholen/issues/352) tried translations of phrases that the author writes. Haiku checked them reliably, but each phrase needed much authored content. Runs in [#367](https://github.com/pauk-slon/immer-wiederholen/issues/367) then let Claude Haiku 5.5 write the sentences from the exercises of real lessons. The sentences were natural, and the check accepted no wrong answer of 78.

## Decision

A lesson recall is a short task after a lesson. In the first version it is a translation from the learner's language into the language of the course. After a lesson of two or more exercises, the bot offers a lesson recall. Claude Haiku 5.5 writes the task from the exercises of the lesson, the learner's results in them, and the course's guide. The learner translates, and the model checks each translation by the same guide. The check gives a verdict, correct or wrong, and an optional explanation.

- **The course owns the method.** The guide is `lesson_recall.md` in the course directory. It says how to write the task and how to check it, such as the language, the number of sentences, and when a translation is correct. The engine's prompts in `wiederholen.school.authoring.lesson_recall` have only the flow and the structure of the replies, and the engine checks only that structure.
- **A lesson recall changes nothing else.** The schedule, `/progress` and the streak stay the same, and `tutoring` doesn't import the module.
- **A failure is visible** (ADR 0006). The learner gets an error message and can try again.
- **A model call doesn't block the chat.** The lesson recall is state in the FSM data with its own id. After a call, the handler writes only its own keys, and only if the same lesson recall is still there.
- **A feature flag, `lesson_recall`, turns it on.** If the flag has a chat but the API key or the guide is missing, the bot fails at startup. A chat in the flag doesn't get the optional recall after a correct answer, because two kinds of recall would confuse the learner.

## Alternatives considered

- **Translations of phrases that the author writes,** as in #352 and its closed draft [#361](https://github.com/pauk-slon/immer-wiederholen/pull/361). Not chosen, because each pair needs several authored phrases.
- **The method in the engine's prompts.** Not chosen. The method names the topics and the language of one course, and the author changes it without a release of the engine.
- **The guide in an environment variable, as `AUTHORING_GUIDE_PATH`.** Not chosen. The guide refers to the course's topics, so it deploys and rolls back with the course.
- **Sonnet 5.5.** It is faster, but it left wrong German in the task.
- **Event isolation for each chat** (`RedisEventIsolation`). Not chosen, because a model call would block every other update of the chat.
- **A lesson recall that changes the schedule.** Not chosen for now. A debatable verdict or a prompt injection would then change the schedule.

## Consequences

- The learner practices whole sentences after every lesson with no new exercises in the course. The course adds one guide.
- The quality of the tasks depends on the guide. The engine doesn't check the language or the content of a sentence, so a bad sentence costs the learner a skip.
- The learner's text goes to Anthropic, never to traces.
- A lesson recall costs one generation call and one call for each sentence. The learner waits about 8 s for the task.
- If lesson recalls work, they can replace the recalls of single exercises and `/ai`. Each replacement, and a verdict that changes the schedule, needs its own ADR.

Open questions:

- Should the bot tell the learner that the text goes to Anthropic? This must be decided before the flag opens to everyone.
- How do we check the quality again after a change of the guide, a prompt or the model?
- How do we limit the cost?
