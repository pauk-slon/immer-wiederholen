import dataclasses

from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove

from wiederholen.bot.commands.wiederholen import UserState
from wiederholen.exercises import School

from tests.plugins.aiogram import FeedRawUpdate
from tests.plugins.exercises import make_exercise


async def test_sends_exercise_question(
    feed_raw_update: FeedRawUpdate,
) -> None:
    exercise = make_exercise()
    send_message = await feed_raw_update("/wiederholen", school=School([exercise]))

    assert exercise.question in send_message.text


async def test_sets_answering_state(
    state: FSMContext,
    feed_raw_update: FeedRawUpdate,
) -> None:
    exercise = make_exercise()
    await feed_raw_update("/wiederholen", school=School([exercise]))

    assert await state.get_state() == UserState.answering


async def test_saves_shown_exercise(
    state: FSMContext,
    feed_raw_update: FeedRawUpdate,
) -> None:
    exercise = make_exercise()
    await feed_raw_update("/wiederholen", school=School([exercise]))

    data = await state.get_data()
    assert data["shown_exercise"] == dataclasses.asdict(exercise)


async def test_reply_keyboard_contains_all_options(
    feed_raw_update: FeedRawUpdate,
) -> None:
    exercise = make_exercise()
    send_message = await feed_raw_update("/wiederholen", school=School([exercise]))

    assert isinstance(send_message.reply_markup, ReplyKeyboardMarkup)
    buttons = [btn.text for row in send_message.reply_markup.keyboard for btn in row]
    assert sorted(buttons) == sorted(exercise.distractors + [exercise.answer])


async def test_reply_keyboard_remove_for_input_exercise(
    feed_raw_update: FeedRawUpdate,
) -> None:
    exercise = make_exercise(distractors=[])
    send_message = await feed_raw_update("/wiederholen", school=School([exercise]))

    assert isinstance(send_message.reply_markup, ReplyKeyboardRemove)
