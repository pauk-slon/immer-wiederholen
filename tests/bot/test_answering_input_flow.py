import dataclasses

from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardRemove

from wiederholen.bot import NEXT_EXERCISE, RECALL, UserState
from wiederholen.bot.l10n import RU
from wiederholen.exercises import School

from tests.plugins.aiogram import FeedCallbackQuery, FeedRawUpdate, FeedRawUpdateAll
from tests.plugins.exercises import make_exercise


async def test_correct_answer_shows_success_text(
    state: FSMContext,
    feed_raw_update: FeedRawUpdate,
) -> None:
    exercise = make_exercise(distractors=[])
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

    send_message = await feed_raw_update(exercise.answer, school=School([exercise]))

    assert RU.correct in send_message.text
    assert exercise.explanation["ru"] in send_message.text


async def test_wrong_answer_shows_correct_answer(
    state: FSMContext,
    feed_raw_update: FeedRawUpdate,
) -> None:
    exercise = make_exercise(distractors=[])
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

    send_message = await feed_raw_update("falsch", school=School([exercise]))

    assert exercise.answer in send_message.text
    assert exercise.explanation["ru"] in send_message.text


async def test_next_button_after_correct_answer(
    state: FSMContext,
    feed_raw_update: FeedRawUpdate,
) -> None:
    exercise = make_exercise(distractors=[])
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

    send_message = await feed_raw_update(exercise.answer, school=School([exercise]))

    assert isinstance(send_message.reply_markup, InlineKeyboardMarkup)
    buttons = [
        btn.callback_data
        for row in send_message.reply_markup.inline_keyboard
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

    send_message = await feed_raw_update("falsch", school=School([exercise]))

    assert isinstance(send_message.reply_markup, InlineKeyboardMarkup)
    buttons = [
        btn.callback_data
        for row in send_message.reply_markup.inline_keyboard
        for btn in row
    ]
    assert NEXT_EXERCISE in buttons


async def test_no_button_after_wrong_answer_with_recall(
    state: FSMContext,
    feed_raw_update_all: FeedRawUpdateAll,
) -> None:
    exercise = make_exercise(distractors=[], recall=True)
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

    requests = await feed_raw_update_all("falsch", school=School([exercise]))

    assert requests[0].reply_markup is None


async def test_recall_prompt_sent_after_wrong_answer(
    state: FSMContext,
    feed_raw_update_all: FeedRawUpdateAll,
) -> None:
    exercise = make_exercise(distractors=[], recall=True)
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

    requests = await feed_raw_update_all("falsch", school=School([exercise]))

    assert len(requests) == 2
    assert exercise.recall is not None
    assert exercise.recall.question in requests[1].text
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

    send_message = await feed_raw_update(exercise.answer, school=School([exercise]))

    assert isinstance(send_message.reply_markup, InlineKeyboardMarkup)
    buttons = [
        btn.callback_data
        for row in send_message.reply_markup.inline_keyboard
        for btn in row
    ]
    assert buttons == [RECALL, NEXT_EXERCISE]
