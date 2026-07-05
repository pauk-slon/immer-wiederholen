import dataclasses

from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup

from wiederholen.bot import NEXT_EXERCISE, RECALL, UserState
from wiederholen.bot.l10n import RU
from wiederholen.exercises import School

from tests.plugins.aiogram import FeedCallbackQuery, FeedRawUpdate
from tests.plugins.exercises import make_exercise


class TestHandleAnswer:
    async def test_correct_answer_shows_success_text(
        self,
        state: FSMContext,
        feed_callback_query: FeedCallbackQuery,
    ) -> None:
        exercise = make_exercise()
        await state.set_state(UserState.answering)
        await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

        requests = await feed_callback_query(exercise.answer, school=School([exercise]))

        assert RU.correct in requests[0].text
        assert exercise.explanation["ru"] in requests[0].text

    async def test_wrong_answer_shows_correct_answer(
        self,
        state: FSMContext,
        feed_callback_query: FeedCallbackQuery,
    ) -> None:
        exercise = make_exercise()
        await state.set_state(UserState.answering)
        await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

        requests = await feed_callback_query(
            exercise.distractors[0], school=School([exercise])
        )

        assert exercise.answer in requests[0].text
        assert exercise.explanation["ru"] in requests[0].text


class TestNextExerciseButton:
    async def test_appears_after_correct_answer(
        self,
        state: FSMContext,
        feed_callback_query: FeedCallbackQuery,
    ) -> None:
        exercise = make_exercise()
        await state.set_state(UserState.answering)
        await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

        requests = await feed_callback_query(exercise.answer, school=School([exercise]))

        edit_message = requests[0]
        assert isinstance(edit_message.reply_markup, InlineKeyboardMarkup)
        buttons = [
            btn.callback_data
            for row in edit_message.reply_markup.inline_keyboard
            for btn in row
        ]
        assert NEXT_EXERCISE in buttons

    async def test_appears_after_wrong_answer_without_recall(
        self,
        state: FSMContext,
        feed_callback_query: FeedCallbackQuery,
    ) -> None:
        exercise = make_exercise(recall=False)
        await state.set_state(UserState.answering)
        await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

        requests = await feed_callback_query(
            exercise.distractors[0], school=School([exercise])
        )

        edit_message = requests[0]
        assert isinstance(edit_message.reply_markup, InlineKeyboardMarkup)
        buttons = [
            btn.callback_data
            for row in edit_message.reply_markup.inline_keyboard
            for btn in row
        ]
        assert NEXT_EXERCISE in buttons

    async def test_not_shown_after_wrong_answer_with_recall(
        self,
        state: FSMContext,
        feed_callback_query: FeedCallbackQuery,
    ) -> None:
        exercise = make_exercise(recall=True)
        await state.set_state(UserState.answering)
        await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

        requests = await feed_callback_query(
            exercise.distractors[0], school=School([exercise])
        )

        assert requests[0].reply_markup is None

    async def test_appears_after_recall(
        self,
        state: FSMContext,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        exercise = make_exercise(
            recall={"answer": ["Ich warte auf den Bus."]},
        )
        await state.set_state(UserState.recalling)
        await state.update_data(
            shown_exercise=dataclasses.asdict(exercise), language="ru", journal={}
        )

        send_message = await feed_raw_update(
            "Ich warte auf den Bus.", school=School([exercise])
        )

        assert isinstance(send_message.reply_markup, InlineKeyboardMarkup)
        buttons = [
            btn.callback_data
            for row in send_message.reply_markup.inline_keyboard
            for btn in row
        ]
        assert NEXT_EXERCISE in buttons

    async def test_practice_button_appears_after_correct_answer_with_recall(
        self,
        state: FSMContext,
        feed_callback_query: FeedCallbackQuery,
    ) -> None:
        exercise = make_exercise(recall=True)
        await state.set_state(UserState.answering)
        await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

        requests = await feed_callback_query(exercise.answer, school=School([exercise]))

        edit_message = requests[0]
        assert isinstance(edit_message.reply_markup, InlineKeyboardMarkup)
        buttons = [
            btn.callback_data
            for row in edit_message.reply_markup.inline_keyboard
            for btn in row
        ]
        assert buttons == [RECALL, NEXT_EXERCISE]

    async def test_clicking_practice_starts_recall(
        self,
        state: FSMContext,
        feed_callback_query: FeedCallbackQuery,
    ) -> None:
        exercise = make_exercise(recall=True)
        await state.set_state(UserState.answering)
        await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

        await feed_callback_query(exercise.answer, school=School([exercise]))
        requests = await feed_callback_query(RECALL, school=School([exercise]))
        recall_message = requests[1]

        assert exercise.recall is not None
        assert exercise.recall.question in recall_message.text
        assert await state.get_state() == UserState.recalling

    async def test_clicking_shows_new_exercise(
        self,
        state: FSMContext,
        feed_callback_query: FeedCallbackQuery,
    ) -> None:
        exercise = make_exercise()
        await state.update_data(language="ru", journal={})

        requests = await feed_callback_query(NEXT_EXERCISE, school=School([exercise]))

        assert requests[0].text == exercise.question
        assert await state.get_state() == UserState.answering
