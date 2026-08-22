import asyncio
import dataclasses
from unittest.mock import AsyncMock, Mock, patch

from aiogram.fsm.context import FSMContext
from aiogram.methods import SendChatAction

from tests.plugins.aiogram import FeedCallbackQuery, FeedMessage
from tests.plugins.tutoring import make_exercise
from wiederholen.authoring import AIGenerationError
from wiederholen.bot.commands.wiederholen import NEXT_EXERCISE, RECALL, UserState
from wiederholen.bot.l10n import RU
from wiederholen.tutoring import Course, Exercise


async def _slow_shadow_of(client, exercise: Exercise, course, *, authoring_guide=None):
    # Same signature as generate_shadow_exercise() itself, since this is
    # used as an AsyncMock side_effect standing in for it. A real API call
    # yields to the event loop many times before resolving — a plain
    # AsyncMock(return_value=...) resolves immediately, giving the
    # typing-indicator's background task no chance to actually run before
    # being cancelled. One await is enough to let it get scheduled once.
    await asyncio.sleep(0)
    return _shadow_of(exercise)


def _shadow_of(exercise: Exercise) -> Exercise:
    return dataclasses.replace(
        exercise,
        question="AI-generated question",
        explanation={"ru": "ai ru", "en": "ai en"},
    )


def _ai_course(*exercises: Exercise) -> Course:
    # Every exercise's own topic is opted in — the topic-gating tests below
    # cover the opposite case explicitly.
    return Course(
        list(exercises),
        ai_generatable_topics=frozenset(e.topic for e in exercises),
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
            "/wiederholen", course=_ai_course(exercise), anthropic_client=Mock()
        )

    assert len(requests) == 1
    assert shadow.question in requests[0].text
    assert requests[0].text.startswith("🤖")
    data = await state.get_data()
    assert data["shown_exercise"] == shadow.to_dict()
    assert await state.get_state() == UserState.answering


async def test_shows_typing_while_generating(
    state: FSMContext,
    feed_message: FeedMessage,
    chat_id: int,
) -> None:
    exercise = make_exercise()
    await state.update_data(ai_mode=True)

    with patch(
        "wiederholen.bot.commands.wiederholen.generate_shadow_exercise",
        AsyncMock(side_effect=_slow_shadow_of),
    ):
        requests = await feed_message(
            "/wiederholen", course=_ai_course(exercise), anthropic_client=Mock()
        )

    typing_requests = [r for r in requests if isinstance(r, SendChatAction)]
    assert typing_requests
    assert typing_requests[0].chat_id == chat_id
    assert typing_requests[0].action == "typing"


async def test_does_not_show_typing_when_ai_mode_is_off(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise()

    requests = await feed_message("/wiederholen", course=Course([exercise]))

    assert not [r for r in requests if isinstance(r, SendChatAction)]


async def test_clicking_next_exercise_shows_typing_while_generating(
    state: FSMContext,
    feed_callback_query: FeedCallbackQuery,
    chat_id: int,
) -> None:
    first = make_exercise(word="warten")
    second = make_exercise(word="hoffen")
    await state.update_data(language="ru", ai_mode=True)

    with patch(
        "wiederholen.bot.commands.wiederholen.generate_shadow_exercise",
        AsyncMock(side_effect=_slow_shadow_of),
    ):
        requests = await feed_callback_query(
            NEXT_EXERCISE,
            course=_ai_course(first, second),
            anthropic_client=Mock(),
        )

    typing_requests = [r for r in requests if isinstance(r, SendChatAction)]
    assert typing_requests
    assert typing_requests[0].chat_id == chat_id
    assert typing_requests[0].action == "typing"


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
            "/wiederholen", course=_ai_course(exercise), anthropic_client=Mock()
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

    requests = await feed_message("/wiederholen", course=_ai_course(exercise))

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
    await state.update_data(language="ru", ai_mode=True)

    with patch(
        "wiederholen.bot.commands.wiederholen.generate_shadow_exercise",
        AsyncMock(return_value=shadow),
    ):
        requests = await feed_callback_query(
            NEXT_EXERCISE,
            course=_ai_course(first, second),
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
    await state.update_data(language="ru", ai_mode=True)

    with patch(
        "wiederholen.bot.commands.wiederholen.generate_shadow_exercise",
        AsyncMock(side_effect=AIGenerationError("boom")),
    ):
        requests = await feed_callback_query(
            NEXT_EXERCISE, course=_ai_course(exercise), anthropic_client=Mock()
        )

    assert any(
        hasattr(r, "text") and r.text == RU.ai_generation_failed for r in requests
    )
    assert await state.get_state() is None


async def test_does_not_generate_for_a_topic_not_opted_in(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise()
    await state.update_data(ai_mode=True)

    with patch(
        "wiederholen.bot.commands.wiederholen.generate_shadow_exercise",
        AsyncMock(),
    ) as mock_generate:
        # Course([exercise]) — no ai_generatable_topics, unlike _ai_course().
        requests = await feed_message(
            "/wiederholen", course=Course([exercise]), anthropic_client=Mock()
        )

    mock_generate.assert_not_awaited()
    assert exercise.question in requests[0].text
    assert "🤖" not in requests[0].text


async def test_clicking_next_exercise_does_not_generate_for_an_unlisted_topic(
    state: FSMContext,
    feed_callback_query: FeedCallbackQuery,
) -> None:
    exercise = make_exercise()
    await state.update_data(language="ru", ai_mode=True)

    with patch(
        "wiederholen.bot.commands.wiederholen.generate_shadow_exercise",
        AsyncMock(),
    ) as mock_generate:
        requests = await feed_callback_query(
            NEXT_EXERCISE, course=Course([exercise]), anthropic_client=Mock()
        )

    mock_generate.assert_not_awaited()
    send_message = next(
        r for r in requests if hasattr(r, "text") and exercise.question in r.text
    )
    assert "🤖" not in send_message.text


async def test_ai_mode_survives_answering_an_exercise(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(recalls=False)
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=exercise.to_dict(), ai_mode=True)

    await feed_message(exercise.answer, course=Course([exercise]))

    data = await state.get_data()
    assert data["ai_mode"] is True


async def test_ai_mode_survives_a_required_recall_prompt(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(recalls=True)
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=exercise.to_dict(), ai_mode=True)

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
    await state.update_data(shown_exercise=exercise.to_dict(), ai_mode=True)
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
        ai_mode=True,
    )

    await feed_message("Ich warte auf den Bus.", course=Course([exercise]))

    data = await state.get_data()
    assert data["ai_mode"] is True
