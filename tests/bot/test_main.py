import dataclasses
from typing import Generator
from unittest.mock import AsyncMock, patch

import pytest

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from aiogram.fsm.storage.redis import RedisStorage

from aiogram.methods import (
    SetMyCommands,
    SetMyDescription,
    SetMyName,
    SetMyShortDescription,
)

from wiederholen.bot import dispatcher
from wiederholen.bot.__main__ import main
from wiederholen.bot.l10n import LOCALES
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
    monkeypatch.setenv("FSM_STORAGE_URL", "redis://localhost:6379/0")
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
        patch("wiederholen.bot.dispatcher.start_polling", mock_polling),
    ):
        await main()

    mock_polling.assert_called_once()
    args, kwargs = mock_polling.call_args
    assert isinstance(args[0], Bot)
    assert args[0].token == bot_token
    assert isinstance(kwargs["school"], School)
    loaded_exercise = dataclasses.asdict(kwargs["school"]({}).next_exercise())
    if not loaded_exercise["recalls"]:
        del loaded_exercise["recalls"]
    assert loaded_exercise == exercise_data


async def test_configures_redis_storage_from_env() -> None:
    with (
        patch(
            "aiogram.client.session.aiohttp.AiohttpSession.make_request",
            AsyncMock(return_value=True),
        ),
        patch("wiederholen.bot.dispatcher.start_polling", AsyncMock()),
    ):
        await main()

    assert isinstance(dispatcher.fsm.storage, RedisStorage)


async def test_sets_name_for_all_languages() -> None:
    mock_request = AsyncMock(return_value=True)
    with (
        patch(
            "aiogram.client.session.aiohttp.AiohttpSession.make_request", mock_request
        ),
        patch("wiederholen.bot.dispatcher.start_polling", AsyncMock()),
    ):
        await main()

    name_calls = {
        call.args[1].language_code: call.args[1].name
        for call in mock_request.call_args_list
        if isinstance(call.args[1], SetMyName)
    }
    assert name_calls == {lc: locale.bot_name for lc, locale in LOCALES.items()}


async def test_sets_description_for_all_languages() -> None:
    mock_request = AsyncMock(return_value=True)
    with (
        patch(
            "aiogram.client.session.aiohttp.AiohttpSession.make_request", mock_request
        ),
        patch("wiederholen.bot.dispatcher.start_polling", AsyncMock()),
    ):
        await main()

    description_calls = {
        call.args[1].language_code: call.args[1].description
        for call in mock_request.call_args_list
        if isinstance(call.args[1], SetMyDescription)
    }
    assert description_calls == {
        lc: locale.bot_short_description for lc, locale in LOCALES.items()
    }


async def test_sets_short_description_for_all_languages() -> None:
    mock_request = AsyncMock(return_value=True)
    with (
        patch(
            "aiogram.client.session.aiohttp.AiohttpSession.make_request", mock_request
        ),
        patch("wiederholen.bot.dispatcher.start_polling", AsyncMock()),
    ):
        await main()

    short_description_calls = {
        call.args[1].language_code: call.args[1].short_description
        for call in mock_request.call_args_list
        if isinstance(call.args[1], SetMyShortDescription)
    }
    assert short_description_calls == {
        lc: locale.bot_short_description for lc, locale in LOCALES.items()
    }


async def test_sets_commands_for_all_languages() -> None:
    mock_request = AsyncMock(return_value=True)
    with (
        patch(
            "aiogram.client.session.aiohttp.AiohttpSession.make_request", mock_request
        ),
        patch("wiederholen.bot.dispatcher.start_polling", AsyncMock()),
    ):
        await main()

    language_codes = {
        call.args[1].language_code
        for call in mock_request.call_args_list
        if isinstance(call.args[1], SetMyCommands)
    }
    assert language_codes == {"ru", "en"}


@pytest.mark.parametrize(
    "failing_method",
    [SetMyName, SetMyDescription, SetMyShortDescription, SetMyCommands],
)
async def test_does_not_crash_on_rate_limit(failing_method: type) -> None:
    async def make_request_side_effect(bot, method, timeout=None):
        if isinstance(method, failing_method):
            raise TelegramRetryAfter(
                method=method, message="flood control", retry_after=1
            )
        return True

    mock_request = AsyncMock(side_effect=make_request_side_effect)
    with (
        patch(
            "aiogram.client.session.aiohttp.AiohttpSession.make_request", mock_request
        ),
        patch("wiederholen.bot.dispatcher.start_polling", AsyncMock()) as mock_polling,
    ):
        await main()

    mock_polling.assert_called_once()
