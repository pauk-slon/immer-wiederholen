import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.methods import SendMessage

from tests.conftest import TmpYamlFile
from tests.plugins.journal_backend import seed_journal
from tests.plugins.tutoring import ExerciseData, make_exercise, make_exercise_data
from wiederholen.bot.reminder import POLL_INTERVAL_SECONDS, main, run, tick
from wiederholen.journal_backend import JournalBackend
from wiederholen.tutoring import Course


def _stale_answer() -> str:
    return (datetime.now(UTC) - timedelta(hours=25)).isoformat()


async def test_tick_sends_reminder_and_records_it(
    bot_token: str,
    redis_storage: RedisStorage,
    journal_backend: JournalBackend,
) -> None:
    exercise = make_exercise()
    bot = Bot(token=bot_token)
    await seed_journal(
        journal_backend, "1", {"last_exercise": {"answered_at": _stale_answer()}}
    )

    mock_request = AsyncMock(return_value=True)
    with patch.object(bot.session, "make_request", mock_request):
        await tick(bot, redis_storage, journal_backend, Course([exercise]))

    sent = [
        call.args[1]
        for call in mock_request.call_args_list
        if isinstance(call.args[1], SendMessage)
    ]
    assert len(sent) == 1
    assert sent[0].chat_id == 1
    async with journal_backend.open("1") as journal:
        assert "last_reminded_at" in journal


async def test_tick_skips_chat_with_nothing_due(
    bot_token: str,
    redis_storage: RedisStorage,
    journal_backend: JournalBackend,
) -> None:
    exercise = make_exercise(word="warten")
    bot = Bot(token=bot_token)
    await seed_journal(
        journal_backend,
        "1",
        {
            "word_schedule": {
                "warten": {
                    "government": {
                        "repetition_interval": 30,
                        "due_date": (
                            datetime.now(UTC).date() + timedelta(days=20)
                        ).isoformat(),
                    },
                },
            },
            "last_exercise": {"answered_at": _stale_answer()},
        },
    )

    mock_request = AsyncMock(return_value=True)
    with patch.object(bot.session, "make_request", mock_request):
        await tick(bot, redis_storage, journal_backend, Course([exercise]))

    assert mock_request.call_args_list == []


async def test_tick_does_not_crash_when_chat_blocked_the_bot(
    bot_token: str,
    redis_storage: RedisStorage,
    journal_backend: JournalBackend,
) -> None:
    exercise = make_exercise()
    bot = Bot(token=bot_token)
    await seed_journal(
        journal_backend, "1", {"last_exercise": {"answered_at": _stale_answer()}}
    )

    async def make_request_side_effect(bot, method, timeout=None):
        if isinstance(method, SendMessage):
            raise TelegramForbiddenError(
                method=method, message="bot was blocked by the user"
            )
        return True

    mock_request = AsyncMock(side_effect=make_request_side_effect)
    with patch.object(bot.session, "make_request", mock_request):
        await tick(bot, redis_storage, journal_backend, Course([exercise]))

    async with journal_backend.open("1") as journal:
        assert "last_reminded_at" not in journal


async def test_tick_continues_after_one_chat_fails(
    bot_token: str,
    redis_storage: RedisStorage,
    journal_backend: JournalBackend,
) -> None:
    exercise = make_exercise()
    bot = Bot(token=bot_token)
    await seed_journal(
        journal_backend, "1", {"last_exercise": {"answered_at": _stale_answer()}}
    )
    # malformed data for chat 2 raises while parsing, must not affect chat 1
    await seed_journal(
        journal_backend, "2", {"last_exercise": {"answered_at": "not-a-valid-datetime"}}
    )

    mock_request = AsyncMock(return_value=True)
    with patch.object(bot.session, "make_request", mock_request):
        await tick(bot, redis_storage, journal_backend, Course([exercise]))

    sent_chat_ids = {
        call.args[1].chat_id
        for call in mock_request.call_args_list
        if isinstance(call.args[1], SendMessage)
    }
    assert sent_chat_ids == {1}


async def test_run_ticks_then_sleeps_between_iterations(
    bot_token: str,
    redis_storage: RedisStorage,
    journal_backend: JournalBackend,
) -> None:
    bot = Bot(token=bot_token)
    course = Course([make_exercise()])
    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        raise asyncio.CancelledError

    with (
        patch.object(bot.session, "make_request", AsyncMock(return_value=True)),
        patch("wiederholen.bot.reminder.asyncio.sleep", fake_sleep),
        pytest.raises(asyncio.CancelledError),
    ):
        await run(bot, redis_storage, journal_backend, course)

    assert sleep_calls == [POLL_INTERVAL_SECONDS]


async def test_main_calls_run_with_constructed_dependencies(
    monkeypatch, bot_token: str, tmp_yaml_file: TmpYamlFile
) -> None:
    exercise_data: ExerciseData = make_exercise_data(word="sprechen")
    monkeypatch.setenv("BOT_TOKEN", bot_token)
    monkeypatch.setenv("FSM_STORAGE_URL", "redis://localhost:6379/0")
    with tmp_yaml_file([exercise_data], filename="exercises.yaml") as path:
        monkeypatch.setenv("COURSE_PATH", str(path.parent))
        mock_run = AsyncMock()
        with patch("wiederholen.bot.reminder.run", mock_run):
            await main()

    mock_run.assert_called_once()
    args, _kwargs = mock_run.call_args
    bot_arg, fsm_storage_arg, journal_backend_arg, course_arg = args
    assert isinstance(bot_arg, Bot)
    assert bot_arg.token == bot_token
    assert isinstance(fsm_storage_arg, RedisStorage)
    assert isinstance(journal_backend_arg, JournalBackend)
    assert isinstance(course_arg, Course)
