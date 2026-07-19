import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import SendMessage

from wiederholen.bot.reminder import POLL_INTERVAL_SECONDS, main, run, tick
from wiederholen.bot.redis_storage import ScanningRedisStorage
from wiederholen.exercises import School

from tests.conftest import TmpYamlFile
from tests.plugins.exercises import ExerciseData, make_exercise, make_exercise_data


class _ScanningMemoryStorage(MemoryStorage):
    """Test double mirroring ScanningRedisStorage.iter_fsm_data: a chat is
    "known" once anything has actually been written for it, matching what a
    real SCAN over Redis keys would find (not merely touched via a read,
    which MemoryStorage's defaultdict would otherwise auto-vivify)."""

    async def iter_fsm_data(self, bot_id: int) -> AsyncIterator[tuple[int, dict]]:
        for key, record in self.storage.items():
            if key.bot_id == bot_id and record.data:
                yield key.chat_id, record.data.copy()


def _state(bot: Bot, storage: MemoryStorage, chat_id: int) -> FSMContext:
    return FSMContext(
        storage=storage,
        key=StorageKey(bot_id=bot.id, chat_id=chat_id, user_id=chat_id),
    )


def _stale_answer() -> str:
    return (datetime.now(UTC) - timedelta(hours=25)).isoformat()


async def test_tick_sends_reminder_and_records_it(bot_token: str) -> None:
    exercise = make_exercise()
    bot = Bot(token=bot_token)
    storage = _ScanningMemoryStorage()
    state = _state(bot, storage, 1)
    await state.update_data(
        journal={"last_answered_at": _stale_answer()}, language="ru"
    )

    mock_request = AsyncMock(return_value=True)
    with patch.object(bot.session, "make_request", mock_request):
        await tick(bot, storage, School([exercise]))

    sent = [
        call.args[1]
        for call in mock_request.call_args_list
        if isinstance(call.args[1], SendMessage)
    ]
    assert len(sent) == 1
    assert sent[0].chat_id == 1
    data = await state.get_data()
    assert "last_reminded_at" in data["journal"]


async def test_tick_skips_chat_with_nothing_due(bot_token: str) -> None:
    exercise = make_exercise(topic="warten")
    bot = Bot(token=bot_token)
    storage = _ScanningMemoryStorage()
    state = _state(bot, storage, 1)
    await state.update_data(
        journal={
            "topic_schedule": {
                "warten:government": {
                    "interval_days": 30,
                    "due_date": (date.today() + timedelta(days=20)).isoformat(),
                }
            },
            "last_answered_at": _stale_answer(),
        }
    )

    mock_request = AsyncMock(return_value=True)
    with patch.object(bot.session, "make_request", mock_request):
        await tick(bot, storage, School([exercise]))

    assert mock_request.call_args_list == []


async def test_tick_does_not_crash_when_chat_blocked_the_bot(bot_token: str) -> None:
    exercise = make_exercise()
    bot = Bot(token=bot_token)
    storage = _ScanningMemoryStorage()
    state = _state(bot, storage, 1)
    await state.update_data(journal={"last_answered_at": _stale_answer()})

    async def make_request_side_effect(bot, method, timeout=None):
        if isinstance(method, SendMessage):
            raise TelegramForbiddenError(
                method=method, message="bot was blocked by the user"
            )
        return True

    mock_request = AsyncMock(side_effect=make_request_side_effect)
    with patch.object(bot.session, "make_request", mock_request):
        await tick(bot, storage, School([exercise]))

    data = await state.get_data()
    assert "last_reminded_at" not in data["journal"]


async def test_tick_continues_after_one_chat_fails(bot_token: str) -> None:
    exercise = make_exercise()
    bot = Bot(token=bot_token)
    storage = _ScanningMemoryStorage()
    await _state(bot, storage, 1).update_data(
        journal={"last_answered_at": _stale_answer()}
    )
    # malformed data for chat 2 raises while parsing, must not affect chat 1
    await _state(bot, storage, 2).update_data(
        journal={"last_answered_at": "not-a-valid-datetime"}
    )

    mock_request = AsyncMock(return_value=True)
    with patch.object(bot.session, "make_request", mock_request):
        await tick(bot, storage, School([exercise]))

    sent_chat_ids = {
        call.args[1].chat_id
        for call in mock_request.call_args_list
        if isinstance(call.args[1], SendMessage)
    }
    assert sent_chat_ids == {1}


async def test_run_ticks_then_sleeps_between_iterations(bot_token: str) -> None:
    bot = Bot(token=bot_token)
    storage = _ScanningMemoryStorage()
    school = School([make_exercise()])
    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        raise asyncio.CancelledError

    with (
        patch.object(bot.session, "make_request", AsyncMock(return_value=True)),
        patch("wiederholen.bot.reminder.asyncio.sleep", fake_sleep),
        pytest.raises(asyncio.CancelledError),
    ):
        await run(bot, storage, school)

    assert sleep_calls == [POLL_INTERVAL_SECONDS]


async def test_main_calls_run_with_constructed_dependencies(
    monkeypatch, bot_token: str, tmp_yaml_file: TmpYamlFile
) -> None:
    exercise_data: ExerciseData = make_exercise_data(topic="sprechen")
    monkeypatch.setenv("BOT_TOKEN", bot_token)
    monkeypatch.setenv("FSM_STORAGE_URL", "redis://localhost:6379/0")
    with tmp_yaml_file([exercise_data]) as path:
        monkeypatch.setenv("EXERCISES_PATH", str(path))
        mock_run = AsyncMock()
        with patch("wiederholen.bot.reminder.run", mock_run):
            await main()

    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    bot_arg, storage_arg, school_arg = args
    assert isinstance(bot_arg, Bot)
    assert bot_arg.token == bot_token
    assert isinstance(storage_arg, ScanningRedisStorage)
    assert isinstance(school_arg, School)
