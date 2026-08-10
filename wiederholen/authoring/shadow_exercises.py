"""AI-generated "shadow" exercises (see GitHub issue #122): given a real
`Exercise` already picked by `Tutor.next_exercise()`, generate an alternate
`question`/`explanation` for the same `word`/`topic`/`answer`/`distractors`/
`recalls`, so the learner answers exactly the pair the scheduler would have
shown them, just with AI-written wording instead of the human-authored one.

Deliberately outside `wiederholen.tutoring`: that package imports nothing
beyond the standard library and its own sibling modules, which is what keeps
`Tutor`/`Journal` testable without mocking a network call. This module is the
one place in the codebase that talks to an LLM, and neither `session.py` nor
`journal.py` import it.
"""

import dataclasses
from typing import Final

from anthropic import AnthropicError, AsyncAnthropic
from anthropic.types import MessageParam, TextBlockParam, ToolParam, ToolUseBlock

from wiederholen.tutoring import Course, Exercise

MODEL: Final = "claude-haiku-4-5-20251001"
_MAX_TOKENS: Final = 1024
_FEW_SHOT_COUNT: Final = 3
_TOOL_NAME: Final = "submit_shadow_exercise"

_TOOL: Final[ToolParam] = {
    "name": _TOOL_NAME,
    "description": "Submit the generated question and explanation for the exercise.",
    "input_schema": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": (
                    "The exercise's question, in the same format the topic uses."
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
        "required": ["question", "explanation"],
    },
}


class AIGenerationError(Exception):
    """Generating a shadow exercise failed — the API call itself, or a
    malformed/incomplete tool response."""


def _few_shot_examples(course: Course, exercise: Exercise) -> list[Exercise]:
    return [
        candidate
        for candidate in course.exercises
        if candidate.topic == exercise.topic and candidate is not exercise
    ][:_FEW_SHOT_COUNT]


def _build_prompt(exercise: Exercise, few_shot: list[Exercise]) -> str:
    examples = "\n".join(f"- {candidate.question!r}" for candidate in few_shot)
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
    return (
        "Write a new question and a ru/en explanation for this German "
        "exercise, keeping the same word, topic, answer, and distractors — "
        "only the wording of the question and explanation should change.\n\n"
        f"word: {exercise.word!r}\n"
        f"topic: {exercise.topic!r}\n"
        f"answer: {exercise.answer!r}\n"
        f"distractors: {exercise.distractors!r}\n\n"
        f"Existing questions for this topic, for format/style reference:\n"
        f"{examples}"
        f"{description_note}"
    )


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
            tool_choice={"type": "tool", "name": _TOOL_NAME},
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
    raw_explanation = tool_use.input.get("explanation")
    if not isinstance(raw_question, str) or not isinstance(raw_explanation, dict):
        raise AIGenerationError("model returned a malformed response")

    changes: dict = {"question": raw_question, "explanation": raw_explanation}
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
