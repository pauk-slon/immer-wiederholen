"""AI-generated "shadow" exercises (see GitHub issue #122): given a real
`Exercise` already picked by `Tutor.next_exercise()` for its `(word, topic)`
scheduling pair, generate a full alternate `Exercise` for that same pair —
`question`, `distractors`, `explanation`, and `recalls` written fresh by an
LLM, plus `word`/`topic`/`answer` carried over unchanged from the reference
— so the learner practices the same scheduled `(word, topic)` (and the same
specific `answer` within it) the scheduler picked, with entirely new
surrounding content instead of the human-authored one in `exercises.yaml`.

`answer` is deliberately *not* model-generated, unlike an earlier version of
this design that let the model choose any answer genuinely correct for its
own sentence. That flexibility was meant for word+topic pairs that legally
admit more than one correct answer (see the authoring guide) — but a shadow
exercise isn't authoring a new independent entry for the pair, it's standing
in for the *one specific* `Exercise` `next_exercise()` already selected, so
letting the model pick a different-but-also-valid answer would silently
swap what's actually being tested rather than just rewording it. Pinning
`answer` (and `word`/`topic`) to the reference exactly is what makes them
correct by construction again, the same guarantee the original narrower
design had for all of `answer`/`distractors`/`recalls` — only
`distractors`/`recalls`, generated fresh around the fixed `answer`, still
depend on the model getting it right.

Deliberately a sibling of `wiederholen.school.tutoring`, not a dependency of
it or a part of it: that package imports nothing beyond the standard library
and its own sibling modules, which is what keeps `Tutor`/`StudentRecord`
testable without mocking a network call. This module is the one place in the
school that talks to an LLM (`authoring.cues` is its sibling for the other
kind of generative AI call the school makes, visual cue generation — see
its own module docstring), and neither `session.py` nor `student_record.py` import
it — it only needs `Course`/`Exercise`/`Recall`, the shared curriculum model
both this module and `tutoring` depend on independently, so it reaches for
`wiederholen.school.curriculum` directly rather than through `tutoring`.
"""

import dataclasses
from typing import Final

import yaml
from anthropic import AnthropicError, AsyncAnthropic
from anthropic.types import MessageParam, TextBlockParam, ToolParam, ToolUseBlock

from wiederholen.school.curriculum import Course, Exercise, Recall

MODEL: Final = "claude-haiku-4-5-20251001"
_MAX_TOKENS: Final = 3072
_FEW_SHOT_COUNT: Final = 3
_TOOL_NAME: Final = "submit_shadow_exercise"

_TOOL: Final[ToolParam] = {
    "name": _TOOL_NAME,
    "description": "Submit the generated exercise.",
    "input_schema": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": (
                    "The exercise's question, in the same format the topic uses. "
                    "Its blank must be correctly and unambiguously filled by the "
                    "fixed answer given in the prompt — not a different, "
                    "also-plausible completion."
                ),
            },
            "distractors": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Plausible-but-wrong alternatives — each one must make the "
                    "sentence ungrammatical or clearly incorrect if substituted "
                    "in place of the blank. Same count as the reference "
                    "example below (empty for a topic that uses typed input "
                    "instead of multiple choice)."
                ),
            },
            "explanation": {
                "type": "object",
                "properties": {
                    "ru": {"type": "string"},
                    "en": {"type": "string"},
                },
                "required": ["ru", "en"],
            },
            "recalls": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "answer": {"type": "array", "items": {"type": "string"}},
                        "hint": {
                            "type": "object",
                            "properties": {
                                "ru": {"type": "string"},
                                "en": {"type": "string"},
                            },
                        },
                    },
                    "required": ["question", "answer"],
                },
                "description": (
                    "Recall-step variant(s) for your new question, following "
                    "the authoring guide's Recall section — same variant count "
                    "and hint conventions as the reference example below "
                    "(empty if the topic has none)."
                ),
            },
            "description": {
                "type": "object",
                "properties": {
                    "ru": {"type": "string"},
                    "en": {"type": "string"},
                },
                "required": ["ru", "en"],
                "description": (
                    "Only include this if the prompt shows an original description "
                    "below — a ru/en translation of *your new* question's sentence, "
                    "playing the same disambiguating role for it that the original "
                    "description played for the original sentence."
                ),
            },
        },
        "required": ["question", "distractors", "explanation", "recalls"],
    },
}


class AIGenerationError(Exception):
    """Generating a shadow exercise failed — the API call itself, or a
    malformed/incomplete tool response."""


def _few_shot_examples(course: Course, exercise: Exercise) -> list[Exercise]:
    same_topic = [
        candidate
        for candidate in course.exercises
        if candidate.topic == exercise.topic and candidate is not exercise
    ]
    # Same-word examples first, same-topic-only ones as filler — these are
    # style/format reference only (the target's own exercise, shown
    # separately in _build_prompt() as the primary reference, already covers
    # the "does `word` have to survive verbatim" concern for this exact
    # word).
    same_word = [
        candidate for candidate in same_topic if candidate.word == exercise.word
    ]
    other_word = [
        candidate for candidate in same_topic if candidate.word != exercise.word
    ]
    return (same_word + other_word)[:_FEW_SHOT_COUNT]


def _recall_to_dict(recall: Recall) -> dict:
    # dataclasses.asdict() (Recall.to_dict()) would include `hint: None`
    # when absent — real exercises.yaml entries simply omit the key instead
    # (see the authoring guide's own YAML examples), so build the dict by
    # hand to match that convention rather than showing the model a shape
    # real course data never actually has.
    data: dict = {"question": recall.question, "answer": recall.answer}
    if recall.hint is not None:
        data["hint"] = recall.hint
    return data


def _exercise_to_dict(exercise: Exercise) -> dict:
    data: dict = {
        "word": exercise.word,
        "topic": exercise.topic,
        "question": exercise.question,
        "answer": exercise.answer,
        "distractors": exercise.distractors,
        "explanation": exercise.explanation,
    }
    if exercise.recalls:
        data["recalls"] = [_recall_to_dict(recall) for recall in exercise.recalls]
    if exercise.description is not None:
        data["description"] = exercise.description
    return data


def _dump_exercises_yaml(exercises: list[Exercise]) -> str:
    # Same shape as exercises.yaml itself (a plain list of entries) — this
    # is deliberately real YAML, not a Python repr of the fields, so both
    # the reference example and the few-shot examples below look exactly
    # like what the model already saw quoted in the authoring guide's own
    # examples, and exactly like what a human author sees when pointed at
    # "the examples in exercises.yaml" for the same task (see PR discussion).
    return yaml.safe_dump(
        [_exercise_to_dict(exercise) for exercise in exercises],
        allow_unicode=True,
        sort_keys=False,
    )


def _build_prompt(exercise: Exercise, few_shot: list[Exercise]) -> str:
    description_note = ""
    if exercise.description is not None:
        description_note = (
            "\n\nThis exercise also has a description shown to the learner "
            "before answering, translating the *original* sentence to "
            "disambiguate it (several answers could otherwise fit "
            "grammatically) — original description: "
            f"{exercise.description!r}. Your new question is a different "
            "sentence, so also submit a new description that plays the same "
            "disambiguating role for it; don't reuse the original wording."
        )
    # Deliberately short: the authoring guide above (system prompt) already
    # covers topic conventions, per-topic grammar, and the Recall section's
    # rules in full — restating them here would just be an uncached
    # paraphrase of the same content, with its own risk of drifting from the
    # guide over time. This mirrors how a human author (or Claude Code
    # authoring exercises.yaml directly) is prompted: "write an exercise for
    # this word+topic, examples in exercises.yaml" — the guide plus a couple
    # of concrete examples, not a restatement of every rule inline.
    #
    # The one thing spelled out here rather than left to the guide is that
    # `answer` is fixed, not the model's to choose (see the module
    # docstring for why) — that's specific to this generation flow, not a
    # fact about German or about authoring exercises in general, so it has
    # no natural home in a guide written for a human author.
    return (
        "Write a new exercise for the given word and topic, following the "
        "authoring guide above. The answer is fixed at the value below — "
        "write a question whose blank is correctly and unambiguously "
        "filled by exactly this answer, and distractors that are wrong "
        "for it.\n\n"
        f"word: {exercise.word!r}\n"
        f"topic: {exercise.topic!r}\n"
        f"answer: {exercise.answer!r}\n\n"
        "Here is the exercise currently scheduled for this exact word and "
        "topic, as your example (same YAML shape as exercises.yaml):\n\n"
        "```yaml\n"
        f"{_dump_exercises_yaml([exercise])}"
        "```\n\n"
        "A few more examples of this topic:\n\n"
        "```yaml\n"
        f"{_dump_exercises_yaml(few_shot)}"
        "```"
        f"{description_note}"
    )


def _parse_recalls(raw_recalls: list) -> list[Recall]:
    recalls: list[Recall] = []
    for raw in raw_recalls:
        if not isinstance(raw, dict):
            raise AIGenerationError("model returned a malformed response")
        raw_question = raw.get("question")
        raw_answer = raw.get("answer")
        if (
            not isinstance(raw_question, str)
            or not isinstance(raw_answer, list)
            or not all(isinstance(item, str) for item in raw_answer)
        ):
            raise AIGenerationError("model returned a malformed response")
        raw_hint = raw.get("hint")
        if raw_hint is not None and not isinstance(raw_hint, dict):
            raise AIGenerationError("model returned a malformed response")
        try:
            recalls.append(
                Recall(question=raw_question, answer=raw_answer, hint=raw_hint)
            )
        except ValueError as e:
            raise AIGenerationError("model returned a malformed response") from e
    return recalls


async def generate_shadow_exercise(
    client: AsyncAnthropic,
    exercise: Exercise,
    course: Course,
    *,
    authoring_guide: str | None = None,
) -> Exercise:
    system: list[TextBlockParam] = []
    if authoring_guide:
        system.append(
            {
                "type": "text",
                "text": authoring_guide,
                "cache_control": {"type": "ephemeral"},
            }
        )
    messages: list[MessageParam] = [
        {
            "role": "user",
            "content": _build_prompt(exercise, _few_shot_examples(course, exercise)),
        }
    ]
    try:
        response = await client.messages.create(
            model=MODEL,
            max_tokens=_MAX_TOKENS,
            system=system,
            tools=[_TOOL],
            # Not forced to the tool — letting the model reason in free text
            # first (the prompt asks it to) gives it room to work through
            # the fixed answer's grammatical requirements before committing
            # to a sentence/distractors, instead of jumping straight to the
            # tool call with no chance to catch a mismatch.
            tool_choice={"type": "auto"},
            messages=messages,
        )
    except AnthropicError as e:
        raise AIGenerationError("Anthropic API call failed") from e

    tool_use = next(
        (block for block in response.content if isinstance(block, ToolUseBlock)),
        None,
    )
    if tool_use is None:
        raise AIGenerationError("model did not call the expected tool")

    raw_question = tool_use.input.get("question")
    raw_distractors = tool_use.input.get("distractors")
    raw_explanation = tool_use.input.get("explanation")
    raw_recalls = tool_use.input.get("recalls")
    if (
        not isinstance(raw_question, str)
        or not isinstance(raw_distractors, list)
        or not all(isinstance(item, str) for item in raw_distractors)
        or not isinstance(raw_explanation, dict)
        or not isinstance(raw_recalls, list)
    ):
        raise AIGenerationError("model returned a malformed response")

    # `answer` is deliberately absent here — not read off the model's
    # response at all, so dataclasses.replace() below leaves the original
    # (reference) exercise's own `answer` untouched. See the module
    # docstring for why.
    changes: dict = {
        "question": raw_question,
        "distractors": raw_distractors,
        "explanation": raw_explanation,
        "recalls": _parse_recalls(raw_recalls),
    }
    if exercise.description is not None:
        # The original had a disambiguating description tied to its own
        # sentence — carrying it over unchanged would describe a sentence
        # that no longer exists once the question is rewritten, so a new
        # question always needs a new matching description too.
        raw_description = tool_use.input.get("description")
        if not isinstance(raw_description, dict):
            raise AIGenerationError("model returned a malformed response")
        changes["description"] = raw_description

    try:
        return dataclasses.replace(exercise, **changes)
    except ValueError as e:
        raise AIGenerationError("model returned a malformed response") from e
