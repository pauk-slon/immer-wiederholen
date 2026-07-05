import dataclasses
from typing import Generator
from unittest.mock import AsyncMock, patch

import pytest

from aiogram import Bot

from wiederholen.bot.__main__ import main
from wiederholen.exercises import School

from tests.plugins.exercises import make_exercise_data, ExerciseData
from tests.conftest import TmpYamlFile


@pytest.fixture
def exercise_data() -> ExerciseData:
    return make_exercise_data(topic="sprechen")


@pytest.fixture(autouse=True)
def _env(
    monkeypatch, bot_token: str, tmp_yaml_file: TmpYamlFile, exercise_data: ExerciseData
) -> Generator[None]:
    monkeypatch.setenv("BOT_TOKEN", bot_token)
    with tmp_yaml_file([exercise_data]) as path:
        monkeypatch.setenv("EXERCISES_PATH", str(path))
        yield None


async def test_starts_polling_with_bot_and_dependencies(
    bot_token: str, exercise_data: ExerciseData
) -> None:
    mock_polling = AsyncMock()
    with (
        patch(
            "aiogram.client.session.aiohttp.AiohttpSession.make_request",
            AsyncMock(return_value=True),
        ),
        patch("wiederholen.bot.__main__.dp.start_polling", mock_polling),
    ):
        await main()

    mock_polling.assert_called_once()
    args, kwargs = mock_polling.call_args
    assert isinstance(args[0], Bot)
    assert args[0].token == bot_token
    assert isinstance(kwargs["school"], School)
    loaded_exercise = dataclasses.asdict(kwargs["school"]({}).ask())
    if loaded_exercise["recall"] is None:
        del loaded_exercise["recall"]
    assert loaded_exercise == exercise_data


async def test_sets_commands_for_all_languages() -> None:
    mock_request = AsyncMock(return_value=True)
    with (
        patch(
            "aiogram.client.session.aiohttp.AiohttpSession.make_request",
            mock_request,
        ),
        patch("wiederholen.bot.__main__.dp.start_polling", AsyncMock()),
    ):
        await main()

    language_codes = {
        call.args[1].language_code for call in mock_request.call_args_list
    }
    assert language_codes == {"ru", "en"}
