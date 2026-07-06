import dataclasses

from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup

from wiederholen.bot import NEXT_EXERCISE, RECALL, UserState
from wiederholen.bot.l10n import RU
from wiederholen.exercises import School

from tests.plugins.aiogram import FeedCallbackQuery, FeedRawUpdate, FeedRawUpdateMulti
from tests.plugins.exercises import make_exercise


class TestHandleTypedAnswer:
    async def test_correct_answer_shows_success_text(
        self,
        state: FSMContext,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        exercise = make_exercise(distractors=[])
        await state.set_state(UserState.typing)
        await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

        send_message = await feed_raw_update(exercise.answer, school=School([exercise]))

        assert RU.correct in send_message.text
        assert exercise.explanation["ru"] in send_message.text

    async def test_wrong_answer_shows_correct_answer(
        self,
        state: FSMContext,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        exercise = make_exercise(distractors=[])
        await state.set_state(UserState.typing)
        await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

        send_message = await feed_raw_update("falsch", school=School([exercise]))

        assert exercise.answer in send_message.text
        assert exercise.explanation["ru"] in send_message.text

    async def test_next_button_after_correct_answer(
        self,
        state: FSMContext,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        exercise = make_exercise(distractors=[])
        await state.set_state(UserState.typing)
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
        self,
        state: FSMContext,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        exercise = make_exercise(distractors=[], recall=False)
        await state.set_state(UserState.typing)
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
        self,
        state: FSMContext,
        feed_raw_update_multi: FeedRawUpdateMulti,
    ) -> None:
        exercise = make_exercise(distractors=[], recall=True)
        await state.set_state(UserState.typing)
        await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

        requests = await feed_raw_update_multi("falsch", school=School([exercise]))

        assert requests[0].reply_markup is None

    async def test_recall_prompt_sent_after_wrong_answer(
        self,
        state: FSMContext,
        feed_raw_update_multi: FeedRawUpdateMulti,
    ) -> None:
        exercise = make_exercise(distractors=[], recall=True)
        await state.set_state(UserState.typing)
        await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

        requests = await feed_raw_update_multi("falsch", school=School([exercise]))

        assert len(requests) == 2
        assert exercise.recall is not None
        assert exercise.recall.question in requests[1].text
        assert await state.get_state() == UserState.recalling

    async def test_next_button_leads_to_input_exercise(
        self,
        state: FSMContext,
        feed_callback_query: FeedCallbackQuery,
    ) -> None:
        exercise = make_exercise(distractors=[])
        await state.update_data(language="ru", journal={})

        requests = await feed_callback_query(NEXT_EXERCISE, school=School([exercise]))

        assert requests[0].text == exercise.question
        assert await state.get_state() == UserState.typing

    async def test_recall_button_after_correct_answer_with_recall(
        self,
        state: FSMContext,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        exercise = make_exercise(distractors=[], recall=True)
        await state.set_state(UserState.typing)
        await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

        send_message = await feed_raw_update(exercise.answer, school=School([exercise]))

        assert isinstance(send_message.reply_markup, InlineKeyboardMarkup)
        buttons = [
            btn.callback_data
            for row in send_message.reply_markup.inline_keyboard
            for btn in row
        ]
        assert buttons == [RECALL, NEXT_EXERCISE]
