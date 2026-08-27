import base64
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from tests.plugins.curriculum import make_exercise
from wiederholen.school.authoring.cues import (
    build_cue_prompt,
    generate_exercise_cue,
)


def test_build_cue_prompt_returns_none_without_a_description() -> None:
    exercise = make_exercise()

    assert build_cue_prompt(exercise) is None


def test_build_cue_prompt_uses_the_english_description() -> None:
    exercise = make_exercise(
        description={
            "ru": "Поезд едет через туннель.",
            "en": "The train goes through the tunnel.",
        }
    )

    prompt = build_cue_prompt(exercise)

    assert prompt is not None
    assert prompt.startswith("The train goes through the tunnel.")


def _make_client(
    *, json_body: dict | None = None, side_effect=None, status_error=None
) -> Mock:
    client = Mock(spec=httpx.AsyncClient)
    if side_effect is not None:
        client.post = AsyncMock(side_effect=side_effect)
        return client
    response = Mock(spec=httpx.Response)
    response.raise_for_status = Mock(side_effect=status_error)
    response.json = Mock(return_value=json_body)
    client.post = AsyncMock(return_value=response)
    return client


async def test_generate_exercise_cue_returns_none_without_a_description() -> None:
    exercise = make_exercise()
    client = _make_client()

    image = await generate_exercise_cue(
        client, exercise, account_id="acc", api_token="token"
    )

    assert image is None
    client.post.assert_not_called()


async def test_generate_exercise_cue_decodes_the_result_envelope() -> None:
    exercise = make_exercise(
        description={"ru": "x", "en": "A steam train in a tunnel."}
    )
    encoded = base64.b64encode(b"fake-png-bytes").decode()
    client = _make_client(json_body={"result": {"image": encoded}, "success": True})

    image = await generate_exercise_cue(
        client, exercise, account_id="acc", api_token="token"
    )

    assert image == b"fake-png-bytes"
    client.post.assert_awaited_once()
    _, kwargs = client.post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer token"
    assert "acc" in client.post.call_args[0][0]


async def test_generate_exercise_cue_decodes_the_bare_shape() -> None:
    exercise = make_exercise(description={"ru": "x", "en": "y"})
    encoded = base64.b64encode(b"fake-png-bytes").decode()
    client = _make_client(json_body={"image": encoded})

    image = await generate_exercise_cue(
        client, exercise, account_id="acc", api_token="token"
    )

    assert image == b"fake-png-bytes"


async def test_generate_exercise_cue_raises_on_unexpected_shape() -> None:
    exercise = make_exercise(description={"ru": "x", "en": "y"})
    client = _make_client(json_body={"unexpected": True})

    with pytest.raises(httpx.HTTPError):
        await generate_exercise_cue(
            client, exercise, account_id="acc", api_token="token"
        )


async def test_generate_exercise_cue_propagates_connection_errors() -> None:
    exercise = make_exercise(description={"ru": "x", "en": "y"})
    client = _make_client(side_effect=httpx.ConnectError("boom"))

    with pytest.raises(httpx.HTTPError):
        await generate_exercise_cue(
            client, exercise, account_id="acc", api_token="token"
        )


async def test_generate_exercise_cue_propagates_a_failed_status() -> None:
    exercise = make_exercise(description={"ru": "x", "en": "y"})
    request = Mock(spec=httpx.Request)
    response = Mock(spec=httpx.Response)
    status_error = httpx.HTTPStatusError("401", request=request, response=response)
    client = _make_client(status_error=status_error)

    with pytest.raises(httpx.HTTPStatusError):
        await generate_exercise_cue(
            client, exercise, account_id="acc", api_token="token"
        )
