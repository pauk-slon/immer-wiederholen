from datetime import UTC, datetime, timedelta

from aiogram.fsm.context import FSMContext

from tests.plugins.aiogram import FeedMessage
from tests.plugins.curriculum import make_exercise
from wiederholen.school import Course


async def test_showing_an_exercise_saves_the_lesson(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise()

    await feed_message("/wiederholen", course=Course([exercise]))

    lesson = (await state.get_data())["lesson"]
    active_at = datetime.fromisoformat(lesson["active_at"])
    assert datetime.now(UTC) - active_at < timedelta(minutes=1)
    assert lesson["exercise_keys"] == []


async def test_the_lesson_outlives_the_answer(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(answer="auf")
    course = Course([exercise])

    await feed_message("/wiederholen", course=course)
    await feed_message("auf", course=course)

    assert (await state.get_data())["lesson"]["finished"] is True
