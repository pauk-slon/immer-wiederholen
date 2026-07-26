from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardRemove

from tests.plugins.aiogram import FeedCallbackQuery, FeedMessage
from tests.plugins.tutoring import make_exercise
from wiederholen.bot.commands.wiederholen import NEXT_EXERCISE, RECALL, UserState
from wiederholen.bot.l10n import RU
from wiederholen.tutoring import Course


async def test_correct_answer_shows_success_text(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(distractors=[])
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=exercise.to_dict(), journal={})

    requests = await feed_message(exercise.answer, course=Course([exercise]))

    assert RU.correct in requests[0].text
    assert exercise.explanation["ru"] in requests[1].text


async def test_wrong_answer_shows_correct_answer(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(distractors=[])
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=exercise.to_dict(), journal={})

    requests = await feed_message("falsch", course=Course([exercise]))

    assert exercise.answer in requests[0].text
    assert exercise.explanation["ru"] in requests[1].text


async def test_next_button_after_correct_answer(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(distractors=[])
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=exercise.to_dict(), journal={})

    requests = await feed_message(exercise.answer, course=Course([exercise]))

    assert isinstance(requests[1].reply_markup, InlineKeyboardMarkup)
    buttons = [
        btn.callback_data
        for row in requests[1].reply_markup.inline_keyboard
        for btn in row
    ]
    assert NEXT_EXERCISE in buttons


async def test_next_button_after_wrong_answer_without_recall(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(distractors=[], recalls=False)
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=exercise.to_dict(), journal={})

    requests = await feed_message("falsch", course=Course([exercise]))

    assert isinstance(requests[1].reply_markup, InlineKeyboardMarkup)
    buttons = [
        btn.callback_data
        for row in requests[1].reply_markup.inline_keyboard
        for btn in row
    ]
    assert NEXT_EXERCISE in buttons


async def test_no_button_after_wrong_answer_with_recall(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(distractors=[], recalls=True)
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=exercise.to_dict(), journal={})

    requests = await feed_message("falsch", course=Course([exercise]))

    assert requests[0].reply_markup is None


async def test_recall_prompt_sent_after_wrong_answer(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(distractors=[], recalls=True)
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=exercise.to_dict(), journal={})

    requests = await feed_message("falsch", course=Course([exercise]))

    assert len(requests) == 3
    assert exercise.recalls
    assert exercise.recalls[0].question in requests[2].text
    assert await state.get_state() == UserState.recalling


async def test_next_button_leads_to_input_exercise(
    state: FSMContext,
    feed_callback_query: FeedCallbackQuery,
) -> None:
    exercise = make_exercise(distractors=[])
    await state.update_data(language="ru", journal={})

    requests = await feed_callback_query(NEXT_EXERCISE, course=Course([exercise]))

    send_message = next(
        r for r in requests if hasattr(r, "text") and exercise.question in r.text
    )
    assert isinstance(send_message.reply_markup, ReplyKeyboardRemove)
    assert await state.get_state() == UserState.answering


async def test_recall_button_after_correct_answer_with_recall(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(distractors=[], recalls=True)
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=exercise.to_dict(), journal={})

    requests = await feed_message(exercise.answer, course=Course([exercise]))

    assert isinstance(requests[1].reply_markup, InlineKeyboardMarkup)
    buttons = [
        btn.callback_data
        for row in requests[1].reply_markup.inline_keyboard
        for btn in row
    ]
    assert buttons == [RECALL, NEXT_EXERCISE]
