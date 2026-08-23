from unittest.mock import AsyncMock, Mock

import pytest
import yaml
from anthropic import AnthropicError, AsyncAnthropic
from anthropic.types import Message, TextBlock, ToolUseBlock

from tests.plugins.curriculum import RecallKwargs, make_exercise
from wiederholen.school.authoring import (
    _TOOL_NAME,
    MODEL,
    AIGenerationError,
    generate_shadow_exercise,
)
from wiederholen.school.curriculum import Course


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
    "distractors": ["für", "an", "um"],
    "explanation": {"ru": "новое объяснение", "en": "new explanation"},
    "recalls": [],
}


def _without(key: str) -> dict:
    data = dict(_VALID_INPUT)
    del data[key]
    return data


async def test_returns_a_fully_generated_exercise() -> None:
    exercise = make_exercise(word="warten", answer="auf")
    client = _make_client(_make_response(_make_tool_use(_VALID_INPUT)))

    shadow = await generate_shadow_exercise(client, exercise, Course([exercise]))

    assert shadow.question == _VALID_INPUT["question"]
    assert shadow.distractors == _VALID_INPUT["distractors"]
    assert shadow.explanation == _VALID_INPUT["explanation"]
    assert shadow.recalls == []


async def test_preserves_word_topic_and_answer_but_replaces_everything_else() -> None:
    exercise = make_exercise(
        word="warten", topic="government", answer="auf", recalls=True
    )
    tool_input = {**_VALID_INPUT, "distractors": ["hilft", "für", "um"]}
    client = _make_client(_make_response(_make_tool_use(tool_input)))

    shadow = await generate_shadow_exercise(client, exercise, Course([exercise]))

    assert shadow.word == exercise.word
    assert shadow.topic == exercise.topic
    # The model's response has no "answer" key at all (see _VALID_INPUT) —
    # this is what actually proves it's carried over, not just coincidentally
    # equal to something the tool happened to return.
    assert shadow.answer == exercise.answer
    assert shadow.distractors == ["hilft", "für", "um"]
    assert shadow.question != exercise.question


async def test_builds_recalls_from_the_generated_variants() -> None:
    exercise = make_exercise()
    tool_input = {
        **_VALID_INPUT,
        "recalls": [
            {
                "question": "Ich warte ___ (der Bus).",
                "answer": ["Ich warte auf den Bus."],
                "hint": {"ru": "der Bus — автобус"},
            },
            {
                "question": "Er wartet ___ (die Antwort).",
                "answer": ["Er wartet auf die Antwort."],
            },
        ],
    }
    client = _make_client(_make_response(_make_tool_use(tool_input)))

    shadow = await generate_shadow_exercise(client, exercise, Course([exercise]))

    assert len(shadow.recalls) == 2
    assert shadow.recalls[0].question == "Ich warte ___ (der Bus)."
    assert shadow.recalls[0].answer == ["Ich warte auf den Bus."]
    assert shadow.recalls[0].hint == {"ru": "der Bus — автобус"}
    assert shadow.recalls[1].hint is None


async def test_uses_the_configured_model() -> None:
    exercise = make_exercise()
    client = _make_client(_make_response(_make_tool_use(_VALID_INPUT)))

    await generate_shadow_exercise(client, exercise, Course([exercise]))

    assert client.messages.create.await_args.kwargs["model"] == MODEL


async def test_lets_the_model_reason_before_calling_the_tool() -> None:
    exercise = make_exercise()
    client = _make_client(_make_response(_make_tool_use(_VALID_INPUT)))

    await generate_shadow_exercise(client, exercise, Course([exercise]))

    kwargs = client.messages.create.await_args.kwargs
    assert kwargs["tool_choice"] == {"type": "auto"}
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


async def test_shows_the_scheduled_exercise_as_the_primary_reference_example() -> None:
    target = make_exercise(word="warten", topic="government", answer="auf")
    client = _make_client(_make_response(_make_tool_use(_VALID_INPUT)))

    await generate_shadow_exercise(client, target, Course([target]))

    prompt = client.messages.create.await_args.kwargs["messages"][0]["content"]
    assert target.question in prompt
    assert f"answer: {target.answer}" in prompt
    assert all(distractor in prompt for distractor in target.distractors)


async def test_reference_example_is_valid_yaml_matching_the_scheduled_exercise() -> (
    None
):
    target = make_exercise(
        word="warten", topic="government", answer="auf", recalls=True
    )
    client = _make_client(_make_response(_make_tool_use(_VALID_INPUT)))

    await generate_shadow_exercise(client, target, Course([target]))

    prompt = client.messages.create.await_args.kwargs["messages"][0]["content"]
    reference_yaml = prompt.split("```yaml\n", 1)[1].split("\n```", 1)[0]
    parsed = yaml.safe_load(reference_yaml)

    assert parsed == [
        {
            "word": target.word,
            "topic": target.topic,
            "question": target.question,
            "answer": target.answer,
            "distractors": target.distractors,
            "explanation": target.explanation,
            "recalls": [
                {"question": recall.question, "answer": recall.answer}
                for recall in target.recalls
            ],
        }
    ]


async def test_reference_example_includes_the_original_recalls_hint() -> None:
    target = make_exercise(
        recalls=[RecallKwargs(hint={"ru": "der Bus — автобус"})],
    )
    client = _make_client(_make_response(_make_tool_use(_VALID_INPUT)))

    await generate_shadow_exercise(client, target, Course([target]))

    prompt = client.messages.create.await_args.kwargs["messages"][0]["content"]
    assert "der Bus — автобус" in prompt


async def test_includes_additional_few_shot_examples_from_the_same_topic_only() -> None:
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
        _without("question"),
        _without("distractors"),
        _without("explanation"),
        _without("recalls"),
        {**_VALID_INPUT, "question": 123},
        {**_VALID_INPUT, "distractors": "not a list"},
        {**_VALID_INPUT, "distractors": [1, 2]},
        {**_VALID_INPUT, "explanation": "not a dict"},
        {**_VALID_INPUT, "recalls": "not a list"},
        {**_VALID_INPUT, "recalls": ["not a dict"]},
        {**_VALID_INPUT, "recalls": [{"question": "x"}]},
        {**_VALID_INPUT, "recalls": [{"question": "x", "answer": "not a list"}]},
        {**_VALID_INPUT, "recalls": [{"question": "x", "answer": [1]}]},
        {
            **_VALID_INPUT,
            "recalls": [{"question": "x", "answer": ["y"], "hint": "not a dict"}],
        },
        {**_VALID_INPUT, "recalls": [{"question": "x", "answer": []}]},
    ],
)
async def test_rejects_a_malformed_tool_response(tool_input: dict) -> None:
    exercise = make_exercise()
    client = _make_client(_make_response(_make_tool_use(tool_input)))

    with pytest.raises(AIGenerationError):
        await generate_shadow_exercise(client, exercise, Course([exercise]))


async def test_rejects_distractors_that_include_the_fixed_answer() -> None:
    exercise = make_exercise(answer="auf")
    tool_input = {**_VALID_INPUT, "distractors": ["auf", "an", "um"]}
    client = _make_client(_make_response(_make_tool_use(tool_input)))

    with pytest.raises(AIGenerationError):
        await generate_shadow_exercise(client, exercise, Course([exercise]))


async def test_rejects_an_incomplete_explanation() -> None:
    exercise = make_exercise()
    tool_input = {**_VALID_INPUT, "explanation": {"ru": "только ru"}}
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
    tool_input = {**_VALID_INPUT, "distractors": [], "description": new_description}
    client = _make_client(_make_response(_make_tool_use(tool_input)))

    shadow = await generate_shadow_exercise(client, exercise, Course([exercise]))

    assert shadow.description == new_description


async def test_rejects_a_missing_description_when_the_original_has_one() -> None:
    exercise = make_exercise(
        topic="preposition_meaning",
        distractors=[],
        description={"ru": "старое описание", "en": "old description"},
    )
    tool_input = {**_VALID_INPUT, "distractors": []}
    client = _make_client(_make_response(_make_tool_use(tool_input)))

    with pytest.raises(AIGenerationError):
        await generate_shadow_exercise(client, exercise, Course([exercise]))


async def test_mentions_the_original_description_in_the_prompt_when_present() -> None:
    exercise = make_exercise(
        topic="preposition_meaning",
        distractors=[],
        description={"ru": "старое описание", "en": "old description"},
    )
    tool_input = {
        **_VALID_INPUT,
        "distractors": [],
        "description": {"ru": "x", "en": "y"},
    }
    client = _make_client(_make_response(_make_tool_use(tool_input)))

    await generate_shadow_exercise(client, exercise, Course([exercise]))

    prompt = client.messages.create.await_args.kwargs["messages"][0]["content"]
    assert "старое описание" in prompt


async def test_omits_the_description_note_when_the_original_has_none() -> None:
    exercise = make_exercise()
    client = _make_client(_make_response(_make_tool_use(_VALID_INPUT)))

    await generate_shadow_exercise(client, exercise, Course([exercise]))

    prompt = client.messages.create.await_args.kwargs["messages"][0]["content"]
    assert "This exercise also has a description" not in prompt
