import dataclasses

from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardRemove

from wiederholen.bot.commands.wiederholen import NEXT_EXERCISE, RECALL, UserState
from wiederholen.bot.l10n import RU
from wiederholen.exercises import School

from tests.plugins.aiogram import FeedCallbackQuery, FeedRawUpdate
from tests.plugins.exercises import make_exercise


async def test_correct_answer_shows_success_text(
    state: FSMContext,
    feed_raw_update: FeedRawUpdate,
) -> None:
    exercise = make_exercise(distractors=[])
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

    requests = await feed_raw_update(exercise.answer, school=School([exercise]))

    assert RU.correct in requests[0].text
    assert exercise.explanation["ru"] in requests[1].text


async def test_wrong_answer_shows_correct_answer(
    state: FSMContext,
    feed_raw_update: FeedRawUpdate,
) -> None:
    exercise = make_exercise(distractors=[])
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

    requests = await feed_raw_update("falsch", school=School([exercise]))

    assert exercise.answer in requests[0].text
    assert exercise.explanation["ru"] in requests[1].text


async def test_next_button_after_correct_answer(
    state: FSMContext,
    feed_raw_update: FeedRawUpdate,
) -> None:
    exercise = make_exercise(distractors=[])
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

    requests = await feed_raw_update(exercise.answer, school=School([exercise]))

    assert isinstance(requests[1].reply_markup, InlineKeyboardMarkup)
    buttons = [
        btn.callback_data
        for row in requests[1].reply_markup.inline_keyboard
        for btn in row
    ]
    assert NEXT_EXERCISE in buttons


async def test_next_button_after_wrong_answer_without_recall(
    state: FSMContext,
    feed_raw_update: FeedRawUpdate,
) -> None:
    exercise = make_exercise(distractors=[], recall=False)
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

    requests = await feed_raw_update("falsch", school=School([exercise]))

    assert isinstance(requests[1].reply_markup, InlineKeyboardMarkup)
    buttons = [
        btn.callback_data
        for row in requests[1].reply_markup.inline_keyboard
        for btn in row
    ]
    assert NEXT_EXERCISE in buttons


async def test_no_button_after_wrong_answer_with_recall(
    state: FSMContext,
    feed_raw_update: FeedRawUpdate,
) -> None:
    exercise = make_exercise(distractors=[], recall=True)
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

    requests = await feed_raw_update("falsch", school=School([exercise]))

    assert requests[0].reply_markup is None


async def test_recall_prompt_sent_after_wrong_answer(
    state: FSMContext,
    feed_raw_update: FeedRawUpdate,
) -> None:
    exercise = make_exercise(distractors=[], recall=True)
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

    requests = await feed_raw_update("falsch", school=School([exercise]))

    assert len(requests) == 3
    assert exercise.recall is not None
    assert exercise.recall.question in requests[2].text
    assert await state.get_state() == UserState.recalling


async def test_next_button_leads_to_input_exercise(
    state: FSMContext,
    feed_callback_query: FeedCallbackQuery,
) -> None:
    exercise = make_exercise(distractors=[])
    await state.update_data(language="ru", journal={})

    requests = await feed_callback_query(NEXT_EXERCISE, school=School([exercise]))

    send_message = next(
        r for r in requests if hasattr(r, "text") and exercise.question in r.text
    )
    assert isinstance(send_message.reply_markup, ReplyKeyboardRemove)
    assert await state.get_state() == UserState.answering


async def test_recall_button_after_correct_answer_with_recall(
    state: FSMContext,
    feed_raw_update: FeedRawUpdate,
) -> None:
    exercise = make_exercise(distractors=[], recall=True)
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

    requests = await feed_raw_update(exercise.answer, school=School([exercise]))

    assert isinstance(requests[1].reply_markup, InlineKeyboardMarkup)
    buttons = [
        btn.callback_data
        for row in requests[1].reply_markup.inline_keyboard
        for btn in row
    ]
    assert buttons == [RECALL, NEXT_EXERCISE]
