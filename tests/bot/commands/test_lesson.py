from typing import Any

from aiogram.fsm.context import FSMContext
from aiogram.methods import EditMessageReplyMarkup, EditMessageText, SendMessage
from aiogram.types import InlineKeyboardMarkup

from tests.plugins.aiogram import FeedCallbackQuery, FeedMessage
from tests.plugins.curriculum import make_exercise
from wiederholen.bot.commands.lesson import SET_LESSON_SIZE_PREFIX
from wiederholen.bot.commands.wiederholen import NEXT_EXERCISE, UserState
from wiederholen.bot.l10n import EN, RU
from wiederholen.school import Course, Exercise

_WORDS = ("warten", "hoffen", "denken", "achten", "zählen", "glauben", "bitten")


def _question(requests: list[Any]) -> str:
    text = [r for r in requests if isinstance(r, SendMessage)][-1].text
    assert isinstance(text, str)
    return text


def _button_texts(markup: InlineKeyboardMarkup) -> list[str]:
    return [button.text for row in markup.inline_keyboard for button in row]


async def test_marks_the_default_size_when_never_chosen(
    feed_message: FeedMessage,
) -> None:
    requests = await feed_message("/lesson")

    assert len(requests) == 1
    assert requests[0].text == RU.lesson_size_prompt
    assert _button_texts(requests[0].reply_markup) == ["✅ 5", "7"]


async def test_marks_the_chosen_size(
    state: FSMContext, feed_message: FeedMessage
) -> None:
    await state.update_data(lesson_size=7, language="en")

    requests = await feed_message("/lesson")

    assert requests[0].text == EN.lesson_size_prompt
    assert _button_texts(requests[0].reply_markup) == ["5", "✅ 7"]


async def test_clears_a_stale_button_left_from_wiederholen(
    state: FSMContext, feed_message: FeedMessage
) -> None:
    await state.update_data(last_buttoned_message_id=77)

    requests = await feed_message("/lesson")

    edits = [r for r in requests if isinstance(r, EditMessageReplyMarkup)]
    assert len(edits) == 1
    assert edits[0].message_id == 77


async def test_choosing_a_size_saves_it_and_confirms(
    state: FSMContext, feed_callback_query: FeedCallbackQuery
) -> None:
    requests = await feed_callback_query(f"{SET_LESSON_SIZE_PREFIX}7")

    assert (await state.get_data())["lesson_size"] == 7
    edits = [r for r in requests if isinstance(r, EditMessageText)]
    assert len(edits) == 1
    assert edits[0].text == "✅ В уроке будет 7 заданий, начиная со следующего урока"
    assert edits[0].reply_markup.inline_keyboard[0][0].callback_data == NEXT_EXERCISE


async def test_an_unoffered_size_is_reported_as_the_default(
    feed_callback_query: FeedCallbackQuery,
) -> None:
    requests = await feed_callback_query(f"{SET_LESSON_SIZE_PREFIX}10")

    edits = [r for r in requests if isinstance(r, EditMessageText)]
    assert edits[0].text == "✅ В уроке будет 5 заданий, начиная со следующего урока"


async def test_choice_survives_answering_an_exercise(
    state: FSMContext, feed_message: FeedMessage
) -> None:
    exercise = make_exercise(recalls=False)
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=exercise.to_dict(), lesson_size=7)

    await feed_message(exercise.answer[0], course=Course([exercise]))

    assert (await state.get_data())["lesson_size"] == 7


async def test_the_chosen_size_sets_the_size_of_a_new_lesson(
    state: FSMContext, feed_message: FeedMessage
) -> None:
    course = Course([make_exercise(word=word, recalls=False) for word in _WORDS])
    await state.update_data(lesson_size=7)

    requests = await feed_message("/wiederholen", course=course)

    assert _question(requests).startswith("1/7")


async def test_a_new_size_applies_from_the_next_lesson(
    state: FSMContext,
    feed_message: FeedMessage,
    feed_callback_query: FeedCallbackQuery,
) -> None:
    course = Course([make_exercise(word=word, recalls=False) for word in _WORDS])
    await feed_message("/wiederholen", course=course)
    await feed_callback_query(f"{SET_LESSON_SIZE_PREFIX}7", course=course)
    counters = []
    for _ in range(6):
        shown = Exercise.from_dict((await state.get_data())["shown_exercise"])
        await feed_message(shown.answer[0], course=course)
        requests = await feed_callback_query(NEXT_EXERCISE, course=course)
        counters.append(_question(requests).split(" ")[0])

    assert counters == ["2/5", "3/5", "4/5", "5/5", "1/7", "2/7"]
