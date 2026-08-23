from aiogram.fsm.context import FSMContext
from aiogram.methods import EditMessageReplyMarkup

from tests.plugins.aiogram import FeedCallbackQuery, FeedMessage
from tests.plugins.curriculum import make_exercise
from wiederholen.bot.commands.wiederholen import NEXT_EXERCISE, UserState
from wiederholen.school import Course


async def test_command_clears_a_stale_button_before_responding(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    await state.update_data(last_buttoned_message_id=77)
    exercise = make_exercise()

    requests = await feed_message("/wiederholen", course=Course([exercise]))

    edits = [r for r in requests if isinstance(r, EditMessageReplyMarkup)]
    assert len(edits) == 1
    assert edits[0].message_id == 77
    assert edits[0].reply_markup is None
    data = await state.get_data()
    assert data.get("last_buttoned_message_id") is None


async def test_no_stale_button_means_no_extra_request(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise()

    requests = await feed_message("/wiederholen", course=Course([exercise]))

    assert not any(isinstance(r, EditMessageReplyMarkup) for r in requests)


async def test_next_button_left_pending_after_answer_is_remembered(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(word="warten", recalls=False)
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=exercise.to_dict())

    await feed_message(exercise.answer, course=Course([exercise]))

    data = await state.get_data()
    assert data["last_buttoned_message_id"] is not None


async def test_typing_a_command_instead_of_tapping_next_clears_it(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(word="warten", recalls=False)
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=exercise.to_dict())
    other_exercise = make_exercise(word="hoffen")

    await feed_message(exercise.answer, course=Course([exercise, other_exercise]))
    requests = await feed_message(
        "/wiederholen", course=Course([exercise, other_exercise])
    )

    edits = [r for r in requests if isinstance(r, EditMessageReplyMarkup)]
    assert len(edits) == 1
    data = await state.get_data()
    assert data.get("last_buttoned_message_id") is None


async def test_clicking_the_button_itself_leaves_nothing_pending(
    state: FSMContext,
    feed_message: FeedMessage,
    feed_callback_query: FeedCallbackQuery,
) -> None:
    exercise = make_exercise(word="warten", recalls=False)
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=exercise.to_dict())
    other_exercise = make_exercise(word="hoffen")
    course = Course([exercise, other_exercise])

    await feed_message(exercise.answer, course=course)
    await feed_callback_query(NEXT_EXERCISE, course=course)

    data = await state.get_data()
    assert data.get("last_buttoned_message_id") is None
