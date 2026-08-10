from unittest.mock import AsyncMock, Mock

import pytest
from anthropic import AnthropicError, AsyncAnthropic
from anthropic.types import Message, TextBlock, ToolUseBlock

from tests.plugins.tutoring import make_exercise
from wiederholen.authoring import AIGenerationError, generate_shadow_exercise
from wiederholen.authoring.shadow_exercises import _TOOL_NAME, MODEL
from wiederholen.tutoring import Course


def _make_tool_use(tool_input: dict) -> ToolUseBlock:
    return Mock(spec=ToolUseBlock, input=tool_input)


def _make_response(*blocks) -> Message:
    return Mock(spec=Message, content=list(blocks))


def _make_client(response=None, side_effect=None) -> Mock:
    client = Mock(spec=AsyncAnthropic)
    client.messages = Mock()
    client.messages.create = AsyncMock(return_value=response, side_effect=side_effect)
    return client


_VALID_INPUT = {
    "question": "Ich ___ (der Bus).",
    "explanation": {"ru": "новое объяснение", "en": "new explanation"},
}


async def test_returns_an_exercise_with_the_generated_question_and_explanation() -> (
    None
):
    exercise = make_exercise(word="warten", answer="auf")
    client = _make_client(_make_response(_make_tool_use(_VALID_INPUT)))

    shadow = await generate_shadow_exercise(client, exercise, Course([exercise]))

    assert shadow.question == _VALID_INPUT["question"]
    assert shadow.explanation == _VALID_INPUT["explanation"]


async def test_preserves_word_topic_answer_distractors_and_recalls() -> None:
    exercise = make_exercise(word="warten", answer="auf", recalls=True)
    client = _make_client(_make_response(_make_tool_use(_VALID_INPUT)))

    shadow = await generate_shadow_exercise(client, exercise, Course([exercise]))

    assert shadow.word == exercise.word
    assert shadow.topic == exercise.topic
    assert shadow.answer == exercise.answer
    assert shadow.distractors == exercise.distractors
    assert shadow.recalls == exercise.recalls


async def test_uses_the_configured_model() -> None:
    exercise = make_exercise()
    client = _make_client(_make_response(_make_tool_use(_VALID_INPUT)))

    await generate_shadow_exercise(client, exercise, Course([exercise]))

    assert client.messages.create.await_args.kwargs["model"] == MODEL


async def test_forces_the_shadow_exercise_tool() -> None:
    exercise = make_exercise()
    client = _make_client(_make_response(_make_tool_use(_VALID_INPUT)))

    await generate_shadow_exercise(client, exercise, Course([exercise]))

    kwargs = client.messages.create.await_args.kwargs
    assert kwargs["tool_choice"] == {"type": "tool", "name": _TOOL_NAME}
    assert [tool["name"] for tool in kwargs["tools"]] == [_TOOL_NAME]


async def test_sends_no_system_block_without_an_authoring_guide() -> None:
    exercise = make_exercise()
    client = _make_client(_make_response(_make_tool_use(_VALID_INPUT)))

    await generate_shadow_exercise(client, exercise, Course([exercise]))

    assert client.messages.create.await_args.kwargs["system"] == []


async def test_sends_the_authoring_guide_as_a_cached_system_block() -> None:
    exercise = make_exercise()
    client = _make_client(_make_response(_make_tool_use(_VALID_INPUT)))

    await generate_shadow_exercise(
        client, exercise, Course([exercise]), authoring_guide="the guide text"
    )

    system = client.messages.create.await_args.kwargs["system"]
    assert system == [
        {
            "type": "text",
            "text": "the guide text",
            "cache_control": {"type": "ephemeral"},
        }
    ]


async def test_includes_few_shot_examples_from_the_same_topic_only() -> None:
    target = make_exercise(word="warten", topic="government", answer="auf")
    same_topic = make_exercise(word="hoffen", topic="government", answer="auf")
    other_topic = make_exercise(word="mit", topic="preposition_case", answer="Freund")
    client = _make_client(_make_response(_make_tool_use(_VALID_INPUT)))

    await generate_shadow_exercise(
        client, target, Course([target, same_topic, other_topic])
    )

    prompt = client.messages.create.await_args.kwargs["messages"][0]["content"]
    assert same_topic.question in prompt
    assert other_topic.question not in prompt
    assert target.question not in prompt


async def test_limits_few_shot_examples_to_three() -> None:
    target = make_exercise(word="warten", topic="government", answer="auf")
    same_topic = [
        make_exercise(word=f"word{i}", topic="government", answer="auf")
        for i in range(5)
    ]
    client = _make_client(_make_response(_make_tool_use(_VALID_INPUT)))

    await generate_shadow_exercise(client, target, Course([target, *same_topic]))

    prompt = client.messages.create.await_args.kwargs["messages"][0]["content"]
    included = sum(1 for e in same_topic if e.question in prompt)
    assert included == 3


async def test_wraps_an_api_error() -> None:
    exercise = make_exercise()
    client = _make_client(side_effect=AnthropicError("boom"))

    with pytest.raises(AIGenerationError):
        await generate_shadow_exercise(client, exercise, Course([exercise]))


async def test_requires_a_tool_use_block_in_the_response() -> None:
    exercise = make_exercise()
    text_block = Mock(spec=TextBlock)
    client = _make_client(_make_response(text_block))

    with pytest.raises(AIGenerationError):
        await generate_shadow_exercise(client, exercise, Course([exercise]))


@pytest.mark.parametrize(
    "tool_input",
    [
        {"explanation": _VALID_INPUT["explanation"]},
        {"question": _VALID_INPUT["question"]},
        {"question": 123, "explanation": _VALID_INPUT["explanation"]},
        {"question": _VALID_INPUT["question"], "explanation": "not a dict"},
    ],
)
async def test_rejects_a_malformed_tool_response(tool_input: dict) -> None:
    exercise = make_exercise()
    client = _make_client(_make_response(_make_tool_use(tool_input)))

    with pytest.raises(AIGenerationError):
        await generate_shadow_exercise(client, exercise, Course([exercise]))


async def test_rejects_an_incomplete_explanation() -> None:
    exercise = make_exercise()
    tool_input = {
        "question": _VALID_INPUT["question"],
        "explanation": {"ru": "только ru"},
    }
    client = _make_client(_make_response(_make_tool_use(tool_input)))

    with pytest.raises(AIGenerationError):
        await generate_shadow_exercise(client, exercise, Course([exercise]))


async def test_does_not_require_a_description_when_the_original_has_none() -> None:
    exercise = make_exercise()
    assert exercise.description is None
    client = _make_client(_make_response(_make_tool_use(_VALID_INPUT)))

    shadow = await generate_shadow_exercise(client, exercise, Course([exercise]))

    assert shadow.description is None


async def test_replaces_the_description_with_the_generated_one() -> None:
    exercise = make_exercise(
        topic="preposition_meaning",
        distractors=[],
        description={"ru": "старое описание", "en": "old description"},
    )
    new_description = {"ru": "новое описание", "en": "new description"}
    tool_input = {**_VALID_INPUT, "description": new_description}
    client = _make_client(_make_response(_make_tool_use(tool_input)))

    shadow = await generate_shadow_exercise(client, exercise, Course([exercise]))

    assert shadow.description == new_description


async def test_rejects_a_missing_description_when_the_original_has_one() -> None:
    exercise = make_exercise(
        topic="preposition_meaning",
        distractors=[],
        description={"ru": "старое описание", "en": "old description"},
    )
    client = _make_client(_make_response(_make_tool_use(_VALID_INPUT)))

    with pytest.raises(AIGenerationError):
        await generate_shadow_exercise(client, exercise, Course([exercise]))


async def test_mentions_the_original_description_in_the_prompt_when_present() -> None:
    exercise = make_exercise(
        topic="preposition_meaning",
        distractors=[],
        description={"ru": "старое описание", "en": "old description"},
    )
    tool_input = {**_VALID_INPUT, "description": {"ru": "x", "en": "y"}}
    client = _make_client(_make_response(_make_tool_use(tool_input)))

    await generate_shadow_exercise(client, exercise, Course([exercise]))

    prompt = client.messages.create.await_args.kwargs["messages"][0]["content"]
    assert "старое описание" in prompt


async def test_omits_the_description_note_when_the_original_has_none() -> None:
    exercise = make_exercise()
    client = _make_client(_make_response(_make_tool_use(_VALID_INPUT)))

    await generate_shadow_exercise(client, exercise, Course([exercise]))

    prompt = client.messages.create.await_args.kwargs["messages"][0]["content"]
    assert "description" not in prompt.lower()
