import dataclasses

from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove

from wiederholen.bot.commands.wiederholen import UserState
from wiederholen.exercises import Exercise, School

from tests.plugins.aiogram import FeedMessage
from tests.plugins.exercises import make_exercise


async def test_sends_exercise_question(
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise()
    requests = await feed_message("/wiederholen", school=School([exercise]))

    assert len(requests) == 1
    assert exercise.question in requests[0].text


async def test_sets_answering_state(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise()
    requests = await feed_message("/wiederholen", school=School([exercise]))

    assert len(requests) == 1
    assert await state.get_state() == UserState.answering


async def test_saves_shown_exercise(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise()
    requests = await feed_message("/wiederholen", school=School([exercise]))

    assert len(requests) == 1
    data = await state.get_data()
    assert data["shown_exercise"] == dataclasses.asdict(exercise)


async def test_reply_keyboard_contains_all_options(
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise()
    requests = await feed_message("/wiederholen", school=School([exercise]))

    assert len(requests) == 1
    assert isinstance(requests[0].reply_markup, ReplyKeyboardMarkup)
    buttons = [btn.text for row in requests[0].reply_markup.keyboard for btn in row]
    assert sorted(buttons) == sorted(exercise.distractors + [exercise.answer])


async def test_reply_keyboard_remove_for_input_exercise(
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(distractors=[])
    requests = await feed_message("/wiederholen", school=School([exercise]))

    assert len(requests) == 1
    assert isinstance(requests[0].reply_markup, ReplyKeyboardRemove)


async def test_avoids_repeating_previously_shown_question(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    mit = Exercise(
        topic="sprechen",
        category="government",
        question="Ich spreche ___ meiner Mutter.",
        answer="mit",
        distractors=["über", "an", "für"],
        explanation={"ru": "x", "en": "y"},
    )
    ueber = Exercise(
        topic="sprechen",
        category="government",
        question="Wir sprechen ___ das Problem.",
        answer="über",
        distractors=["mit", "an", "für"],
        explanation={"ru": "x", "en": "y"},
    )
    await state.update_data(journal={"last_answered_question": mit.question})

    requests = await feed_message("/wiederholen", school=School([mit, ueber]))

    assert len(requests) == 1
    assert ueber.question in requests[0].text
