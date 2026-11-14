from typing import Any

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.methods import SendMessage
from aiogram.types import InlineKeyboardMarkup

from tests.plugins.aiogram import FeedCallbackQuery, FeedMessage
from tests.plugins.curriculum import make_exercise
from wiederholen.bot.commands.wiederholen import (
    NEXT_EXERCISE,
    RECALL,
    STUDY_MORE,
    UserState,
)
from wiederholen.bot.l10n import RU
from wiederholen.school import Course, Exercise

_WORDS = ("warten", "hoffen", "denken", "achten", "zählen")


@pytest.fixture
def feature_flags(chat_id: int) -> dict[str, frozenset[int]]:
    return {"lessons": frozenset({chat_id})}


def _course(*words: str, recalls: bool = False) -> Course:
    return Course([make_exercise(word=word, recalls=recalls) for word in words])


def _button_texts(request: Any) -> list[str]:
    assert isinstance(request.reply_markup, InlineKeyboardMarkup)
    return [btn.text for row in request.reply_markup.inline_keyboard for btn in row]


def _last_text(requests: list[Any]) -> str:
    text = [r for r in requests if isinstance(r, SendMessage)][-1].text
    assert isinstance(text, str)
    return text


async def _shown_exercise(state: FSMContext) -> Exercise:
    return Exercise.from_dict((await state.get_data())["shown_exercise"])


async def test_a_flagged_chat_gets_a_lesson_of_five_with_a_counter(
    state: FSMContext,
    feed_message: FeedMessage,
    feed_callback_query: FeedCallbackQuery,
    feature_flags: dict[str, frozenset[int]],
) -> None:
    course = _course(*_WORDS, "glauben")
    questions = []
    for position in range(1, 6):
        if position == 1:
            requests = await feed_message(
                "/wiederholen", course=course, feature_flags=feature_flags
            )
        else:
            requests = await feed_callback_query(
                NEXT_EXERCISE, course=course, feature_flags=feature_flags
            )
        questions.append(_last_text(requests))
        exercise = await _shown_exercise(state)
        await feed_message(exercise.answer[0], course=course)

    assert [question.split(" ")[0] for question in questions] == [
        "1/5",
        "2/5",
        "3/5",
        "4/5",
        "5/5",
    ]


async def test_a_chat_without_the_flag_gets_no_counter(
    feed_message: FeedMessage,
) -> None:
    requests = await feed_message("/wiederholen", course=_course(*_WORDS))

    assert requests[-1].text.startswith("❓")


async def test_the_last_answer_of_a_lesson_shows_the_summary(
    state: FSMContext,
    feed_message: FeedMessage,
    feed_callback_query: FeedCallbackQuery,
    feature_flags: dict[str, frozenset[int]],
) -> None:
    course = _course("warten", "hoffen")
    await feed_message("/wiederholen", course=course, feature_flags=feature_flags)
    first = await feed_message("auf", course=course)
    await feed_callback_query(NEXT_EXERCISE, course=course, feature_flags=feature_flags)

    last = await feed_message("an", course=course)

    assert RU.lesson_summary.split("!")[0] not in first[-1].text
    assert _button_texts(first[-1]) == [RU.cmd_wiederholen]
    assert last[-1].text.endswith(
        RU.lesson_summary.format(correct=1, size=2)
        + "\n"
        + RU.streak_text.format(days="1 день")
    )
    assert _button_texts(last[-1]) == ["Ещё 5 заданий"]


async def test_a_lesson_that_adds_no_streak_day_shows_no_streak_line(
    state: FSMContext,
    feed_message: FeedMessage,
    feed_callback_query: FeedCallbackQuery,
    feature_flags: dict[str, frozenset[int]],
) -> None:
    # The first lesson gives both new words. Their answers make them due
    # again today, so the second lesson reviews them on the same day
    course = _course("warten", "hoffen")
    await feed_message("/wiederholen", course=course, feature_flags=feature_flags)
    for _ in range(3):
        await feed_message("auf", course=course)
        await feed_callback_query(
            NEXT_EXERCISE, course=course, feature_flags=feature_flags
        )

    last = await feed_message("auf", course=course)

    assert _last_text(last).endswith(RU.lesson_summary.format(correct=2, size=2))


async def test_after_a_required_recall_the_summary_comes_with_the_recall_result(
    state: FSMContext,
    feed_message: FeedMessage,
    feed_callback_query: FeedCallbackQuery,
    feature_flags: dict[str, frozenset[int]],
) -> None:
    course = _course("warten", "hoffen", recalls=True)
    await feed_message("/wiederholen", course=course, feature_flags=feature_flags)
    await feed_message("an", course=course)
    await feed_message("Ich warte auf den Bus.", course=course)
    await feed_callback_query(NEXT_EXERCISE, course=course, feature_flags=feature_flags)

    answer = await feed_message("an", course=course)
    assert await state.get_state() == UserState.recalling
    assert RU.lesson_summary.split("!")[0] not in answer[-2].text
    recall_result = await feed_message("nonsense", course=course)

    assert RU.lesson_summary.format(correct=0, size=2) in recall_result[-1].text
    assert _button_texts(recall_result[-1]) == [
        RU.btn_recall_retry,
        "Ещё 5 заданий",
    ]


async def test_after_an_optional_recall_the_summary_comes_with_the_explanation(
    feed_message: FeedMessage,
    feed_callback_query: FeedCallbackQuery,
    feature_flags: dict[str, frozenset[int]],
) -> None:
    course = _course("warten", "hoffen", recalls=True)
    await feed_message("/wiederholen", course=course, feature_flags=feature_flags)
    await feed_message("auf", course=course)
    await feed_callback_query(NEXT_EXERCISE, course=course, feature_flags=feature_flags)

    last = await feed_message("auf", course=course)
    await feed_callback_query(RECALL, course=course)
    recall_result = await feed_message("Ich warte auf den Bus.", course=course)

    assert RU.lesson_summary.format(correct=2, size=2) in last[-1].text
    assert _button_texts(last[-1]) == [RU.btn_recall, "Ещё 5 заданий"]
    assert _button_texts(recall_result[-1]) == ["Ещё 5 заданий"]


@pytest.mark.parametrize("button", [NEXT_EXERCISE, STUDY_MORE])
async def test_a_next_button_shows_the_exercise_that_waits_for_an_answer(
    button: str,
    state: FSMContext,
    feed_message: FeedMessage,
    feed_callback_query: FeedCallbackQuery,
    feature_flags: dict[str, frozenset[int]],
) -> None:
    course = _course(*_WORDS)
    first = await feed_message(
        "/wiederholen", course=course, feature_flags=feature_flags
    )
    data = await state.get_data()

    again = await feed_callback_query(
        button, course=course, feature_flags=feature_flags
    )

    assert again[-2].text == first[-1].text
    assert first[-1].text.startswith("1/5")
    assert await state.get_data() == data | {"last_buttoned_message_id": None}
