from collections.abc import Generator
from contextlib import AbstractContextManager, contextmanager
from typing import Protocol
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
    TelegramMethod,
)
from aiogram.methods.base import TelegramType
from anthropic import AsyncAnthropic
from redis.asyncio import Redis

from tests.conftest import TmpYamlFile
from tests.plugins.curriculum import ExerciseData, make_exercise_data
from wiederholen.bot import dispatcher
from wiederholen.bot.__main__ import main
from wiederholen.bot.l10n import LOCALES
from wiederholen.school import Course, CueStore, StudentRecordBook, Tutor


@pytest.fixture
def exercise_data() -> ExerciseData:
    return make_exercise_data(word="sprechen")


@pytest.fixture
def fsm_storage_url() -> str:
    return "redis://localhost:6379/1"


@pytest.fixture
def student_record_storage_url() -> str:
    return "redis://localhost:6379/0"


@pytest.fixture(autouse=True)
def _env(
    monkeypatch,
    bot_token: str,
    fsm_storage_url: str,
    student_record_storage_url: str,
    tmp_yaml_file: TmpYamlFile,
    exercise_data: ExerciseData,
) -> Generator[None]:
    monkeypatch.setenv("BOT_TOKEN", bot_token)
    monkeypatch.setenv("BOT_FSM_STORAGE_URL", fsm_storage_url)
    monkeypatch.setenv("STUDENT_RECORD_STORAGE_URL", student_record_storage_url)
    # All optional and unrelated to most tests here — pinned absent so a
    # real value set on the host running these tests (e.g. compose.override.
    # yaml's local dev config) can't leak in.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("AUTHORING_GUIDE_PATH", raising=False)
    monkeypatch.delenv("BOT_FEATURE_FLAGS", raising=False)
    monkeypatch.delenv("R2_ACCOUNT_ID", raising=False)
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
    with mock_main_io() as (_mock_request, mock_polling):
        await main()

    mock_polling.assert_called_once()
    args, kwargs = mock_polling.call_args
    assert isinstance(args[0], Bot)
    assert args[0].token == bot_token
    assert isinstance(kwargs["course"], Course)
    assert isinstance(kwargs["student_record_book"], StudentRecordBook)
    assert kwargs["feature_flags"] == {}
    assert kwargs["anthropic_client"] is None
    assert kwargs["authoring_guide"] is None
    assert kwargs["cue_store"] is None
    exercise = Tutor(kwargs["course"], {}).next_exercise()
    assert exercise is not None
    loaded_exercise = exercise.to_dict()
    if not loaded_exercise["recalls"]:
        del loaded_exercise["recalls"]
    if loaded_exercise["description"] is None:
        del loaded_exercise["description"]
    if loaded_exercise["word_bank"] is None:
        del loaded_exercise["word_bank"]
    assert loaded_exercise == exercise_data


async def test_starts_polling_with_feature_flags_from_env(
    monkeypatch, mock_main_io: MockMainIO
) -> None:
    monkeypatch.setenv("BOT_FEATURE_FLAGS", "ai_exercises:1,2")

    with mock_main_io() as (_mock_request, mock_polling):
        await main()

    _args, kwargs = mock_polling.call_args
    assert kwargs["feature_flags"] == {"ai_exercises": frozenset({1, 2})}


async def test_starts_polling_with_anthropic_client_and_guide_from_env(
    monkeypatch, tmp_path, mock_main_io: MockMainIO
) -> None:
    guide_path = tmp_path / "CLAUDE.md"
    guide_path.write_text("guide text")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("AUTHORING_GUIDE_PATH", str(guide_path))

    with mock_main_io() as (_mock_request, mock_polling):
        await main()

    _args, kwargs = mock_polling.call_args
    assert isinstance(kwargs["anthropic_client"], AsyncAnthropic)
    assert kwargs["authoring_guide"] == "guide text"


async def test_starts_polling_with_cue_store_from_env(
    monkeypatch, mock_main_io: MockMainIO
) -> None:
    monkeypatch.setenv("R2_ACCOUNT_ID", "acc")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("R2_BUCKET", "images")
    monkeypatch.setenv("R2_PUBLIC_URL_BASE", "https://images.example.com")

    with mock_main_io() as (_mock_request, mock_polling):
        await main()

    _args, kwargs = mock_polling.call_args
    assert isinstance(kwargs["cue_store"], CueStore)


async def test_configures_redis_storage_from_env(
    mock_main_io: MockMainIO, fsm_storage_url: str
) -> None:
    with mock_main_io():
        await main()

    storage = dispatcher.fsm.storage
    assert isinstance(storage, RedisStorage)
    expected = Redis.from_url(fsm_storage_url).connection_pool.connection_kwargs
    assert storage.redis.connection_pool.connection_kwargs == expected


async def test_configures_student_record_book_from_its_own_env_var(
    mock_main_io: MockMainIO, student_record_storage_url: str
) -> None:
    # A distinct DB number from fsm_storage_url (see the fixtures above) is
    # what makes this test actually prove student_record_book reads
    # STUDENT_RECORD_STORAGE_URL, rather than accidentally still sharing
    # BOT_FSM_STORAGE_URL's connection.
    with mock_main_io() as (_mock_request, mock_polling):
        await main()

    _args, kwargs = mock_polling.call_args
    student_record_book = kwargs["student_record_book"]
    expected = Redis.from_url(
        student_record_storage_url
    ).connection_pool.connection_kwargs
    assert student_record_book.redis.connection_pool.connection_kwargs == expected


async def test_sets_name_for_all_languages(mock_main_io: MockMainIO) -> None:
    with mock_main_io() as (mock_request, _mock_polling):
        await main()

    name_calls = {
        call.args[1].language_code: call.args[1].name
        for call in mock_request.call_args_list
        if isinstance(call.args[1], SetMyName)
    }
    assert name_calls == {lc: locale.bot_name for lc, locale in LOCALES.items()}


async def test_sets_description_for_all_languages(mock_main_io: MockMainIO) -> None:
    with mock_main_io() as (mock_request, _mock_polling):
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
    with mock_main_io() as (mock_request, _mock_polling):
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
    with mock_main_io() as (mock_request, _mock_polling):
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
    ) as (_mock_request, mock_polling):
        await main()

    mock_polling.assert_called_once()
