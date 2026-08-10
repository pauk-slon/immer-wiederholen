import dataclasses
from unittest.mock import AsyncMock, Mock, patch

from aiogram.fsm.context import FSMContext

from tests.plugins.aiogram import FeedCallbackQuery, FeedMessage
from tests.plugins.tutoring import make_exercise
from wiederholen.authoring import AIGenerationError
from wiederholen.bot.commands.wiederholen import NEXT_EXERCISE, UserState
from wiederholen.bot.l10n import RU
from wiederholen.tutoring import Course, Exercise


def _shadow_of(exercise: Exercise) -> Exercise:
    return dataclasses.replace(
        exercise,
        question="AI-generated question",
        explanation={"ru": "ai ru", "en": "ai en"},
    )


async def test_shows_the_ai_generated_question_when_ai_mode_is_on(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise()
    shadow = _shadow_of(exercise)
    await state.update_data(ai_mode=True)

    with patch(
        "wiederholen.bot.commands.wiederholen.generate_shadow_exercise",
        AsyncMock(return_value=shadow),
    ):
        requests = await feed_message(
            "/wiederholen", course=Course([exercise]), anthropic_client=Mock()
        )

    assert len(requests) == 1
    assert shadow.question in requests[0].text
    data = await state.get_data()
    assert data["shown_exercise"] == shadow.to_dict()
    assert await state.get_state() == UserState.answering


async def test_does_not_generate_when_ai_mode_is_off(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise()

    with patch(
        "wiederholen.bot.commands.wiederholen.generate_shadow_exercise",
        AsyncMock(),
    ) as mock_generate:
        requests = await feed_message(
            "/wiederholen", course=Course([exercise]), anthropic_client=Mock()
        )

    mock_generate.assert_not_awaited()
    assert exercise.question in requests[0].text


async def test_shows_an_error_when_generation_fails(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise()
    await state.update_data(ai_mode=True)

    with patch(
        "wiederholen.bot.commands.wiederholen.generate_shadow_exercise",
        AsyncMock(side_effect=AIGenerationError("boom")),
    ):
        requests = await feed_message(
            "/wiederholen", course=Course([exercise]), anthropic_client=Mock()
        )

    assert len(requests) == 1
    assert requests[0].text == RU.ai_generation_failed
    assert await state.get_state() is None


async def test_shows_an_error_when_no_anthropic_client_is_configured(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise()
    await state.update_data(ai_mode=True)

    requests = await feed_message("/wiederholen", course=Course([exercise]))

    assert len(requests) == 1
    assert requests[0].text == RU.ai_generation_failed
    assert await state.get_state() is None


async def test_clicking_next_exercise_uses_ai_mode_too(
    state: FSMContext,
    feed_message: FeedMessage,
    feed_callback_query: FeedCallbackQuery,
) -> None:
    first = make_exercise(word="warten")
    second = make_exercise(word="hoffen")
    shadow = _shadow_of(second)
    await state.update_data(language="ru", journal={}, ai_mode=True)

    with patch(
        "wiederholen.bot.commands.wiederholen.generate_shadow_exercise",
        AsyncMock(return_value=shadow),
    ):
        requests = await feed_callback_query(
            NEXT_EXERCISE,
            course=Course([first, second]),
            anthropic_client=Mock(),
        )

    send_message = next(
        r for r in requests if hasattr(r, "text") and shadow.question in r.text
    )
    assert shadow.question in send_message.text


async def test_clicking_next_exercise_shows_an_error_when_generation_fails(
    state: FSMContext,
    feed_callback_query: FeedCallbackQuery,
) -> None:
    exercise = make_exercise()
    await state.update_data(language="ru", journal={}, ai_mode=True)

    with patch(
        "wiederholen.bot.commands.wiederholen.generate_shadow_exercise",
        AsyncMock(side_effect=AIGenerationError("boom")),
    ):
        requests = await feed_callback_query(
            NEXT_EXERCISE, course=Course([exercise]), anthropic_client=Mock()
        )

    assert any(
        hasattr(r, "text") and r.text == RU.ai_generation_failed for r in requests
    )
    assert await state.get_state() is None
