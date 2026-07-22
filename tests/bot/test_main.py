from typing import Generator, Protocol
from unittest.mock import AsyncMock, patch
from contextlib import contextmanager, AbstractContextManager

import pytest

from redis.asyncio import Redis

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from aiogram.fsm.storage.redis import RedisStorage

from aiogram.methods import (
    SetMyCommands,
    SetMyDescription,
    SetMyName,
    SetMyShortDescription,
    TelegramMethod,
)
from aiogram.methods.base import TelegramType

from wiederholen.bot import dispatcher
from wiederholen.bot.__main__ import main
from wiederholen.bot.l10n import LOCALES
from wiederholen.exercises import Course, Tutor

from tests.plugins.exercises import make_exercise_data, ExerciseData
from tests.conftest import TmpYamlFile


@pytest.fixture
def exercise_data() -> ExerciseData:
    return make_exercise_data(word="sprechen")


@pytest.fixture
def fsm_storage_url() -> str:
    return "redis://localhost:6379/0"


@pytest.fixture(autouse=True)
def _env(
    monkeypatch,
    bot_token: str,
    fsm_storage_url: str,
    tmp_yaml_file: TmpYamlFile,
    exercise_data: ExerciseData,
) -> Generator[None]:
    monkeypatch.setenv("BOT_TOKEN", bot_token)
    monkeypatch.setenv("FSM_STORAGE_URL", fsm_storage_url)
    with tmp_yaml_file([exercise_data], filename="exercises.yaml") as path:
        monkeypatch.setenv("COURSE_PATH", str(path.parent))
        yield None


class MakeRequest(Protocol):
    async def __call__(
        self,
        bot: Bot,
        method: TelegramMethod[TelegramType],
        timeout: int | None = None,
    ) -> TelegramType: ...


class MockMainIO(Protocol):
    def __call__(
        self,
        *,
        request_side_effect: MakeRequest | None = None,
    ) -> AbstractContextManager[tuple[AsyncMock, AsyncMock]]: ...


@pytest.fixture
def mock_main_io() -> MockMainIO:
    @contextmanager
    def factory(
        *,
        request_side_effect: MakeRequest | None = None,
    ) -> Generator[tuple[AsyncMock, AsyncMock]]:
        with (
            patch(
                "aiogram.client.session.aiohttp.AiohttpSession.make_request",
                AsyncMock(
                    side_effect=request_side_effect or (lambda *args, **kwargs: True),
                ),
            ) as mock_request,
            patch(
                "wiederholen.bot.dispatcher.start_polling", AsyncMock()
            ) as mock_polling,
        ):
            yield mock_request, mock_polling

    return factory


async def test_starts_polling_with_bot_and_dependencies(
    bot_token: str,
    exercise_data: ExerciseData,
    mock_main_io: MockMainIO,
) -> None:
    with mock_main_io() as (mock_request, mock_polling):
        await main()

    mock_polling.assert_called_once()
    args, kwargs = mock_polling.call_args
    assert isinstance(args[0], Bot)
    assert args[0].token == bot_token
    assert isinstance(kwargs["course"], Course)
    loaded_exercise = Tutor(kwargs["course"], {}).next_exercise().to_dict()
    if not loaded_exercise["recalls"]:
        del loaded_exercise["recalls"]
    if loaded_exercise["description"] is None:
        del loaded_exercise["description"]
    assert loaded_exercise == exercise_data


async def test_configures_redis_storage_from_env(
    mock_main_io: MockMainIO, fsm_storage_url: str
) -> None:
    with mock_main_io():
        await main()

    storage = dispatcher.fsm.storage
    assert isinstance(storage, RedisStorage)
    expected = Redis.from_url(fsm_storage_url).connection_pool.connection_kwargs
    assert storage.redis.connection_pool.connection_kwargs == expected


async def test_sets_name_for_all_languages(mock_main_io: MockMainIO) -> None:
    with mock_main_io() as (mock_request, mock_polling):
        await main()

    name_calls = {
        call.args[1].language_code: call.args[1].name
        for call in mock_request.call_args_list
        if isinstance(call.args[1], SetMyName)
    }
    assert name_calls == {lc: locale.bot_name for lc, locale in LOCALES.items()}


async def test_sets_description_for_all_languages(mock_main_io: MockMainIO) -> None:
    with mock_main_io() as (mock_request, mock_polling):
        await main()

    description_calls = {
        call.args[1].language_code: call.args[1].description
        for call in mock_request.call_args_list
        if isinstance(call.args[1], SetMyDescription)
    }
    assert description_calls == {
        lc: locale.bot_short_description for lc, locale in LOCALES.items()
    }


async def test_sets_short_description_for_all_languages(
    mock_main_io: MockMainIO,
) -> None:
    with mock_main_io() as (mock_request, mock_polling):
        await main()

    short_description_calls = {
        call.args[1].language_code: call.args[1].short_description
        for call in mock_request.call_args_list
        if isinstance(call.args[1], SetMyShortDescription)
    }
    assert short_description_calls == {
        lc: locale.bot_short_description for lc, locale in LOCALES.items()
    }


async def test_sets_commands_for_all_languages(mock_main_io: MockMainIO) -> None:
    with mock_main_io() as (mock_request, mock_polling):
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
async def test_does_not_crash_on_rate_limit(
    mock_main_io: MockMainIO, failing_method: type
) -> None:
    async def make_request_side_effect(bot, method, timeout=None):
        if isinstance(method, failing_method):
            raise TelegramRetryAfter(
                method=method,
                message="flood control",
                retry_after=1,
            )
        return True

    with mock_main_io(
        request_side_effect=make_request_side_effect,
    ) as (mock_request, mock_polling):
        await main()

    mock_polling.assert_called_once()
