import dataclasses
from unittest.mock import AsyncMock, Mock, patch

from aiogram.fsm.context import FSMContext

from tests.plugins.aiogram import FeedCallbackQuery, FeedMessage
from tests.plugins.tutoring import make_exercise
from wiederholen.authoring import AIGenerationError
from wiederholen.bot.commands.wiederholen import NEXT_EXERCISE, RECALL, UserState
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
    assert requests[0].text.startswith("🤖")
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
    assert "🤖" not in requests[0].text


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
    assert send_message.text.startswith("🤖")


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


async def test_ai_mode_survives_answering_an_exercise(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(recalls=False)
    await state.set_state(UserState.answering)
    await state.update_data(
        shown_exercise=exercise.to_dict(), journal={}, ai_mode=True
    )

    await feed_message(exercise.answer, course=Course([exercise]))

    data = await state.get_data()
    assert data["ai_mode"] is True


async def test_ai_mode_survives_a_required_recall_prompt(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(recalls=True)
    await state.set_state(UserState.answering)
    await state.update_data(
        shown_exercise=exercise.to_dict(), journal={}, ai_mode=True
    )

    await feed_message(exercise.distractors[0], course=Course([exercise]))

    assert await state.get_state() == UserState.recalling
    data = await state.get_data()
    assert data["ai_mode"] is True


async def test_ai_mode_survives_clicking_retry_after_a_wrong_recall(
    state: FSMContext,
    feed_message: FeedMessage,
    feed_callback_query: FeedCallbackQuery,
) -> None:
    exercise = make_exercise(recalls=True)
    await state.set_state(UserState.answering)
    await state.update_data(
        shown_exercise=exercise.to_dict(), journal={}, ai_mode=True
    )
    await feed_message(exercise.distractors[0], course=Course([exercise]))

    await feed_callback_query(RECALL, course=Course([exercise]))

    data = await state.get_data()
    assert data["ai_mode"] is True


async def test_ai_mode_survives_completing_a_recall(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(recalls=[{"answer": ["Ich warte auf den Bus."]}])
    await state.set_state(UserState.recalling)
    await state.update_data(
        shown_exercise=exercise.to_dict(),
        shown_recall=exercise.recalls[0].to_dict(),
        journal={},
        ai_mode=True,
    )

    await feed_message("Ich warte auf den Bus.", course=Course([exercise]))

    data = await state.get_data()
    assert data["ai_mode"] is True
