import dataclasses

from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup

from wiederholen.bot.commands.wiederholen import NEXT_EXERCISE, RECALL, UserState
from wiederholen.bot.l10n import RU
from wiederholen.exercises import Exercise, School

from tests.plugins.aiogram import FeedCallbackQuery, FeedMessage
from tests.plugins.exercises import make_exercise


class TestHandleAnswer:
    async def test_correct_answer_shows_success_text(
        self,
        state: FSMContext,
        feed_message: FeedMessage,
    ) -> None:
        exercise = make_exercise()
        await state.set_state(UserState.answering)
        await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

        requests = await feed_message(exercise.answer, school=School([exercise]))

        assert RU.correct in requests[0].text
        assert exercise.explanation["ru"] in requests[1].text

    async def test_wrong_answer_shows_correct_answer(
        self,
        state: FSMContext,
        feed_message: FeedMessage,
    ) -> None:
        exercise = make_exercise()
        await state.set_state(UserState.answering)
        await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

        requests = await feed_message(
            exercise.distractors[0], school=School([exercise])
        )

        assert exercise.answer in requests[0].text
        assert exercise.explanation["ru"] in requests[1].text


class TestNextExerciseButton:
    async def test_appears_after_correct_answer(
        self,
        state: FSMContext,
        feed_message: FeedMessage,
    ) -> None:
        exercise = make_exercise()
        await state.set_state(UserState.answering)
        await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

        requests = await feed_message(exercise.answer, school=School([exercise]))

        assert isinstance(requests[1].reply_markup, InlineKeyboardMarkup)
        buttons = [
            btn.callback_data
            for row in requests[1].reply_markup.inline_keyboard
            for btn in row
        ]
        assert NEXT_EXERCISE in buttons

    async def test_appears_after_wrong_answer_without_recall(
        self,
        state: FSMContext,
        feed_message: FeedMessage,
    ) -> None:
        exercise = make_exercise(recalls=False)
        await state.set_state(UserState.answering)
        await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

        requests = await feed_message(
            exercise.distractors[0], school=School([exercise])
        )

        assert isinstance(requests[1].reply_markup, InlineKeyboardMarkup)
        buttons = [
            btn.callback_data
            for row in requests[1].reply_markup.inline_keyboard
            for btn in row
        ]
        assert NEXT_EXERCISE in buttons

    async def test_not_shown_after_wrong_answer_with_recall(
        self,
        state: FSMContext,
        feed_message: FeedMessage,
    ) -> None:
        exercise = make_exercise(recalls=True)
        await state.set_state(UserState.answering)
        await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

        requests = await feed_message(
            exercise.distractors[0], school=School([exercise])
        )

        assert not isinstance(requests[0].reply_markup, InlineKeyboardMarkup)

    async def test_appears_after_recall(
        self,
        state: FSMContext,
        feed_message: FeedMessage,
    ) -> None:
        exercise = make_exercise(
            recalls=[{"answer": ["Ich warte auf den Bus."]}],
        )
        await state.set_state(UserState.recalling)
        await state.update_data(
            shown_exercise=dataclasses.asdict(exercise),
            shown_recall=dataclasses.asdict(exercise.recalls[0]),
            language="ru",
            journal={},
        )

        requests = await feed_message(
            "Ich warte auf den Bus.", school=School([exercise])
        )

        assert len(requests) == 1
        assert isinstance(requests[0].reply_markup, InlineKeyboardMarkup)
        buttons = [
            btn.callback_data
            for row in requests[0].reply_markup.inline_keyboard
            for btn in row
        ]
        assert NEXT_EXERCISE in buttons

    async def test_practice_button_appears_after_correct_answer_with_recall(
        self,
        state: FSMContext,
        feed_message: FeedMessage,
    ) -> None:
        exercise = make_exercise(recalls=True)
        await state.set_state(UserState.answering)
        await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

        requests = await feed_message(exercise.answer, school=School([exercise]))

        assert isinstance(requests[1].reply_markup, InlineKeyboardMarkup)
        buttons = [
            btn.callback_data
            for row in requests[1].reply_markup.inline_keyboard
            for btn in row
        ]
        assert buttons == [RECALL, NEXT_EXERCISE]

    async def test_clicking_practice_starts_recall(
        self,
        state: FSMContext,
        feed_message: FeedMessage,
        feed_callback_query: FeedCallbackQuery,
    ) -> None:
        exercise = make_exercise(recalls=True)
        await state.set_state(UserState.answering)
        await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

        await feed_message(exercise.answer, school=School([exercise]))
        requests = await feed_callback_query(RECALL, school=School([exercise]))
        recall_message = requests[1]

        assert exercise.recalls
        assert exercise.recalls[0].question in recall_message.text
        assert await state.get_state() == UserState.recalling

    async def test_clicking_shows_new_exercise(
        self,
        state: FSMContext,
        feed_callback_query: FeedCallbackQuery,
    ) -> None:
        exercise = make_exercise()
        await state.update_data(language="ru", journal={})

        requests = await feed_callback_query(NEXT_EXERCISE, school=School([exercise]))

        send_message = next(
            r for r in requests if hasattr(r, "text") and exercise.question in r.text
        )
        assert isinstance(send_message.reply_markup, ReplyKeyboardMarkup)
        assert await state.get_state() == UserState.answering

    async def test_avoids_repeating_previously_shown_question(
        self,
        state: FSMContext,
        feed_callback_query: FeedCallbackQuery,
    ) -> None:
        mit = Exercise(
            topic="sprechen",
            category="government",
            question="Ich spreche ___ meiner Mutter.",
            answer="mit",
            distractors=["über", "an", "für"],
            explanation={"ru": "x", "en": "y"},
        )
        ueber = Exercise(
            topic="sprechen",
            category="government",
            question="Wir sprechen ___ das Problem.",
            answer="über",
            distractors=["mit", "an", "für"],
            explanation={"ru": "x", "en": "y"},
        )
        await state.update_data(
            language="ru", journal={"last_answered_question": mit.question}
        )

        requests = await feed_callback_query(NEXT_EXERCISE, school=School([mit, ueber]))

        send_message = next(
            r for r in requests if hasattr(r, "text") and ueber.question in r.text
        )
        assert ueber.question in send_message.text
