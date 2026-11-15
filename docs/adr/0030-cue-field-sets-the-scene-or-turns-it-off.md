# 0030. An exercise's `cue` field sets the scene of its illustration or turns it off

**Status:** Accepted, 2026-11-15. Amends [ADR 0017](0017-cues-keyed-by-question-hash.md). The problem is described in [#349](https://github.com/pauk-slon/immer-wiederholen/issues/349).

## Context

The generator draws each illustration from `description.en`, the translation that the learner sees with the question. A third of the illustrations don't help the learner. Some show a scene that misses the sentence, because the model can't draw absence, duration, thoughts or invisible events from a translation. A course author can't fix this in the content. A translation that is easier to draw is a worse translation, and a duration such as `seit` has no picture at all. An illustration that the author removes from R2 comes back on the next run of the generator.

## Decision

An exercise gets an optional field `cue` with three modes:

- **No `cue`.** The generator draws from `description.en`, as before.
- **A scene in English,** for example `cue: a woman staring in shock at a blank laptop screen`. The generator draws this scene instead of the description. The learner never sees the text.
- **`cue: false`.** The exercise has no illustration. The generator skips it, and the bot doesn't look up its illustration.

A scene is part of the key. `Exercise.cue_key` is the SHA-256 of `question` without a scene, as in ADR 0017, and of `question` and the scene with one. So a new or changed scene gets a new illustration on the next run of the generator, and the other illustrations keep their keys.

`Exercise.to_dict()` leaves out an unset `cue`. So `Exercise.content_key` doesn't change for an exercise without the field, and lessons that learners started before it keep their keys. A version before the field can also read the exercises that the bot and the web app store, so a rollback is safe while no exercise sets `cue`.

`Course.load()` fails if an exercise has `cue` in a topic without `cue_generation`, because the generator never looks at such an exercise.

## Alternatives considered

- **Two fields, `cue_prompt` and `cue: false`,** as #349 proposed. Not chosen, because the three modes exclude each other, and two fields allow a contradiction such as a prompt with `cue: false`.
- **The name `cue_prompt` or `cue_scene`.** Not chosen. The text isn't the whole prompt, because the generator adds the style suffix, and `cue_prompt: false` reads badly. `cue` matches the topic setting `cue_generation`, so the topic turns illustrations on and the exercise sets or turns off its own.
- **The name `picture` or `illustration`.** Not chosen, because the format and the code call it a cue everywhere, and an author would have to know two names for one thing.
- **A separate file for the generator,** such as `cues.yaml` with a scene or `false` for each question, and the prompt in the metadata of each R2 object. Not chosen, because the scene then lives away from its exercise, and an edit of the question must also change the file.
- **A scene from an LLM.** The generator would ask Claude for a scene that can be drawn, or for "can't be drawn". Not chosen, because the author couldn't correct a bad result, and it adds a second model and a call for each illustration.
- **Keep the key and add a command that regenerates one illustration.** Not chosen, because the author would have to remember to run it after each new scene. With the scene in the key, the generator finds the new scene by itself.
- **Turn off illustrations for a whole topic.** Not chosen, because the topics also have good illustrations of concrete scenes.

## Consequences

- An author fixes a bad illustration by adding a scene or `cue: false` to its exercise, then runs the generator.
- The old illustration of an exercise with a new scene stays in R2 unused, as after an edit of the question (ADR 0017).
- An illustration of an exercise with `cue: false` also stays in R2, but the bot doesn't show it.
- Once a course sets `cue`, a version before the field can't load it, because `Exercise.from_dict()` passes every key to the constructor. The same goes for the stored exercises that have the field. After that, rolling back the image also means rolling back the course.
- A shadow exercise drops a scene of its original, because the scene describes the original's sentence, as its old `description` does. It keeps `cue: false`.
- This doesn't fix the garbled text in the images. Its cause is still unknown (#349).
