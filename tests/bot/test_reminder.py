import asyncio
from datetime import UTC, datetime, timedelta
from itertools import count
from unittest.mock import AsyncMock, patch

import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.methods import EditMessageReplyMarkup, SendMessage, TelegramMethod
from aiogram.types import Chat, Message

from tests.conftest import TmpYamlFile
from tests.plugins.curriculum import ExerciseData, make_exercise, make_exercise_data
from tests.plugins.student_record_book import ReadStudentRecord, SeedStudentRecord
from wiederholen.bot.commands.wiederholen import NEXT_EXERCISE
from wiederholen.bot.reminder import POLL_INTERVAL_SECONDS, main, run, tick
from wiederholen.bot.telegram_student_id import TelegramStudentID
from wiederholen.school import Course, StudentRecordBook


def _stale_answer() -> str:
    return (datetime.now(UTC) - timedelta(hours=25)).isoformat()


def _make_request_mock() -> AsyncMock:
    # A realistic SendMessage response, mirroring tests/plugins/aiogram.py's
    # own feed_raw_update fixture (see its comment): the reminder now reads
    # the sent message's own message_id back (to track it via
    # remember_buttoned_message()), so the bare `True` every other method
    # still gets here isn't enough for SendMessage specifically. tick() has
    # no incoming update to feed the way feed_raw_update does, so this
    # builds an equivalent mock directly rather than reusing that fixture.
    message_ids = count(1000)

    def make_fake_response(method: TelegramMethod) -> object:
        if isinstance(method, SendMessage):
            assert isinstance(method.chat_id, int)
            return Message(
                message_id=next(message_ids),
                date=datetime.now(tz=UTC),
                chat=Chat(id=method.chat_id, type="private"),
            )
        return True

    return AsyncMock(
        side_effect=lambda bot, method, timeout=None: make_fake_response(method)
    )


async def test_tick_sends_reminder_and_records_it(
    bot_token: str,
    redis_storage: RedisStorage,
    student_record_book: StudentRecordBook,
    seed_student_record: SeedStudentRecord,
    read_student_record: ReadStudentRecord,
) -> None:
    exercise = make_exercise()
    bot = Bot(token=bot_token)
    await seed_student_record(
        TelegramStudentID.encode(1), {"last_exercise": {"answered_at": _stale_answer()}}
    )

    mock_request = _make_request_mock()
    with patch.object(bot.session, "make_request", mock_request):
        await tick(bot, redis_storage, student_record_book, Course([exercise]))

    sent = [
        call.args[1]
        for call in mock_request.call_args_list
        if isinstance(call.args[1], SendMessage)
    ]
    assert len(sent) == 1
    assert sent[0].chat_id == 1
    assert "last_reminded_at" in await read_student_record(TelegramStudentID.encode(1))


async def test_tick_sends_reminder_with_a_next_exercise_button(
    bot_token: str,
    redis_storage: RedisStorage,
    student_record_book: StudentRecordBook,
    seed_student_record: SeedStudentRecord,
) -> None:
    exercise = make_exercise()
    bot = Bot(token=bot_token)
    await seed_student_record(
        TelegramStudentID.encode(1), {"last_exercise": {"answered_at": _stale_answer()}}
    )

    mock_request = _make_request_mock()
    with patch.object(bot.session, "make_request", mock_request):
        await tick(bot, redis_storage, student_record_book, Course([exercise]))

    sent = [
        call.args[1]
        for call in mock_request.call_args_list
        if isinstance(call.args[1], SendMessage)
    ]
    assert len(sent) == 1
    assert sent[0].reply_markup is not None
    assert sent[0].reply_markup.inline_keyboard[0][0].callback_data == NEXT_EXERCISE


async def test_tick_clears_a_stale_button_before_reminding(
    bot_token: str,
    redis_storage: RedisStorage,
    student_record_book: StudentRecordBook,
    seed_student_record: SeedStudentRecord,
) -> None:
    exercise = make_exercise()
    bot = Bot(token=bot_token)
    await seed_student_record(
        TelegramStudentID.encode(1), {"last_exercise": {"answered_at": _stale_answer()}}
    )
    state = FSMContext(
        storage=redis_storage, key=StorageKey(bot_id=bot.id, chat_id=1, user_id=1)
    )
    await state.update_data(last_buttoned_message_id=77)

    mock_request = _make_request_mock()
    with patch.object(bot.session, "make_request", mock_request):
        await tick(bot, redis_storage, student_record_book, Course([exercise]))

    edits = [
        call.args[1]
        for call in mock_request.call_args_list
        if isinstance(call.args[1], EditMessageReplyMarkup)
    ]
    assert len(edits) == 1
    assert edits[0].message_id == 77
    assert edits[0].reply_markup is None


async def test_tick_remembers_the_reminder_message_as_the_new_buttoned_message(
    bot_token: str,
    redis_storage: RedisStorage,
    student_record_book: StudentRecordBook,
    seed_student_record: SeedStudentRecord,
) -> None:
    exercise = make_exercise()
    bot = Bot(token=bot_token)
    await seed_student_record(
        TelegramStudentID.encode(1), {"last_exercise": {"answered_at": _stale_answer()}}
    )
    state = FSMContext(
        storage=redis_storage, key=StorageKey(bot_id=bot.id, chat_id=1, user_id=1)
    )

    mock_request = _make_request_mock()
    with patch.object(bot.session, "make_request", mock_request):
        await tick(bot, redis_storage, student_record_book, Course([exercise]))

    data = await state.get_data()
    assert data["last_buttoned_message_id"] is not None


async def test_tick_skips_chat_with_nothing_due(
    bot_token: str,
    redis_storage: RedisStorage,
    student_record_book: StudentRecordBook,
    seed_student_record: SeedStudentRecord,
) -> None:
    exercise = make_exercise(word="warten")
    bot = Bot(token=bot_token)
    await seed_student_record(
        TelegramStudentID.encode(1),
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
        await tick(bot, redis_storage, student_record_book, Course([exercise]))

    assert mock_request.call_args_list == []


async def test_tick_does_not_crash_when_chat_blocked_the_bot(
    bot_token: str,
    redis_storage: RedisStorage,
    student_record_book: StudentRecordBook,
    seed_student_record: SeedStudentRecord,
    read_student_record: ReadStudentRecord,
) -> None:
    exercise = make_exercise()
    bot = Bot(token=bot_token)
    await seed_student_record(
        TelegramStudentID.encode(1), {"last_exercise": {"answered_at": _stale_answer()}}
    )

    async def make_request_side_effect(bot, method, timeout=None):
        if isinstance(method, SendMessage):
            raise TelegramForbiddenError(
                method=method, message="bot was blocked by the user"
            )
        return True

    mock_request = AsyncMock(side_effect=make_request_side_effect)
    with patch.object(bot.session, "make_request", mock_request):
        await tick(bot, redis_storage, student_record_book, Course([exercise]))

    assert "last_reminded_at" not in await read_student_record(
        TelegramStudentID.encode(1)
    )


async def test_tick_continues_after_one_chat_fails(
    bot_token: str,
    redis_storage: RedisStorage,
    student_record_book: StudentRecordBook,
    seed_student_record: SeedStudentRecord,
) -> None:
    exercise = make_exercise()
    bot = Bot(token=bot_token)
    await seed_student_record(
        TelegramStudentID.encode(1), {"last_exercise": {"answered_at": _stale_answer()}}
    )
    # malformed data for chat 2 raises while parsing, must not affect chat 1
    await seed_student_record(
        TelegramStudentID.encode(2),
        {"last_exercise": {"answered_at": "not-a-valid-datetime"}},
    )

    mock_request = _make_request_mock()
    with patch.object(bot.session, "make_request", mock_request):
        await tick(bot, redis_storage, student_record_book, Course([exercise]))

    sent_chat_ids = {
        call.args[1].chat_id
        for call in mock_request.call_args_list
        if isinstance(call.args[1], SendMessage)
    }
    assert sent_chat_ids == {1}


async def test_tick_skips_a_student_id_from_a_different_frontend(
    bot_token: str,
    redis_storage: RedisStorage,
    student_record_book: StudentRecordBook,
    seed_student_record: SeedStudentRecord,
) -> None:
    # Not this worker's concern to remind — e.g. a future web frontend
    # sharing this same store, addressed by its own id scheme.
    exercise = make_exercise()
    bot = Bot(token=bot_token)
    await seed_student_record(
        "web:1", {"last_exercise": {"answered_at": _stale_answer()}}
    )

    mock_request = AsyncMock(return_value=True)
    with patch.object(bot.session, "make_request", mock_request):
        await tick(bot, redis_storage, student_record_book, Course([exercise]))

    assert mock_request.call_args_list == []


async def test_run_ticks_then_sleeps_between_iterations(
    bot_token: str,
    redis_storage: RedisStorage,
    student_record_book: StudentRecordBook,
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
        await run(bot, redis_storage, student_record_book, course)

    assert sleep_calls == [POLL_INTERVAL_SECONDS]


async def test_main_calls_run_with_constructed_dependencies(
    monkeypatch, bot_token: str, tmp_yaml_file: TmpYamlFile
) -> None:
    exercise_data: ExerciseData = make_exercise_data(word="sprechen")
    monkeypatch.setenv("BOT_TOKEN", bot_token)
    monkeypatch.setenv("BOT_FSM_STORAGE_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("STUDENT_RECORD_STORAGE_URL", "redis://localhost:6379/0")
    with tmp_yaml_file([exercise_data], filename="exercises.yaml") as path:
        monkeypatch.setenv("COURSE_PATH", str(path.parent))
        mock_run = AsyncMock()
        with patch("wiederholen.bot.reminder.run", mock_run):
            await main()

    mock_run.assert_called_once()
    args, _kwargs = mock_run.call_args
    bot_arg, fsm_storage_arg, student_record_book_arg, course_arg = args
    assert isinstance(bot_arg, Bot)
    assert bot_arg.token == bot_token
    assert isinstance(fsm_storage_arg, RedisStorage)
    assert isinstance(student_record_book_arg, StudentRecordBook)
    assert isinstance(course_arg, Course)
