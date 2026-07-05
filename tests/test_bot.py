import dataclasses

from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup

from wiederholen.bot import NEXT_EXERCISE, RECALL, UserState
from wiederholen.bot.l10n import EN, RU
from wiederholen.exercises import Exercise, Recall, School

from .plugins.aiogram import FeedCallbackQuery, FeedRawUpdate
from .plugins.exercises import make_exercise


class TestWiederholenCommand:
    async def test_sends_exercise_question(
        self,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        exercise = make_exercise()
        send_message = await feed_raw_update("/wiederholen", school=School([exercise]))

        assert send_message.text == exercise.question

    async def test_sets_answering_state(
        self,
        state: FSMContext,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        exercise = make_exercise()
        await feed_raw_update("/wiederholen", school=School([exercise]))

        assert await state.get_state() == UserState.answering

    async def test_saves_shown_exercise(
        self,
        state: FSMContext,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        exercise = make_exercise()
        await feed_raw_update("/wiederholen", school=School([exercise]))

        data = await state.get_data()
        assert data["shown_exercise"] == dataclasses.asdict(exercise)

    async def test_keyboard_contains_all_options(
        self,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        exercise = make_exercise()
        send_message = await feed_raw_update("/wiederholen", school=School([exercise]))

        assert isinstance(send_message.reply_markup, InlineKeyboardMarkup)
        buttons = [
            btn.text for row in send_message.reply_markup.inline_keyboard for btn in row
        ]
        assert sorted(buttons) == sorted(exercise.distractors + [exercise.answer])


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


class TestHandleRecall:
    async def test_correct_input_shows_success(
        self,
        state: FSMContext,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        exercise = make_exercise(
            recall_question="Ich ___ (der Bus).",
            recall_answer=["Ich warte auf den Bus."],
        )
        await state.set_state(UserState.recalling)
        await state.update_data(
            shown_exercise=dataclasses.asdict(exercise), language="ru", journal={}
        )

        send_message = await feed_raw_update(
            "Ich warte auf den Bus.", school=School([exercise])
        )

        assert RU.recall_correct in send_message.text

    async def test_wrong_input_shows_correct_sentence(
        self,
        state: FSMContext,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        exercise = make_exercise(
            recall_question="Ich ___ (der Bus).",
            recall_answer=["Ich warte auf den Bus."],
        )
        await state.set_state(UserState.recalling)
        await state.update_data(
            shown_exercise=dataclasses.asdict(exercise), language="ru", journal={}
        )

        send_message = await feed_raw_update(
            "Es hängt alles in der Situation ab.", school=School([exercise])
        )

        assert "Ich warte auf den Bus." in send_message.text

    async def test_normalizes_case_and_whitespace(
        self,
        state: FSMContext,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        exercise = make_exercise(
            recall_question="Ich ___ (der Bus).",
            recall_answer=["Ich warte auf den Bus."],
        )
        await state.set_state(UserState.recalling)
        await state.update_data(
            shown_exercise=dataclasses.asdict(exercise), language="ru", journal={}
        )

        send_message = await feed_raw_update(
            "ich warte  auf den bus.", school=School([exercise])
        )

        assert RU.recall_correct in send_message.text

    async def test_accepts_any_of_multiple_answers(
        self,
        state: FSMContext,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        exercise = Exercise(
            question="Ich warte ___ den Bus.",
            topic="warten",
            distractors=["für", "an", "um"],
            answer="auf",
            explanation={"ru": "warten auf + Akk", "en": "warten auf + Acc"},
            recall=Recall(
                question="Ich warte ___ (der Bus).",
                answer=["Ich warte auf den Bus.", "Ich warte auf die Straßenbahn."],
            ),
        )
        await state.set_state(UserState.recalling)
        await state.update_data(
            shown_exercise=dataclasses.asdict(exercise), language="ru", journal={}
        )

        send_message = await feed_raw_update(
            "Ich warte auf die Straßenbahn.", school=School([exercise])
        )

        assert RU.recall_correct in send_message.text

    async def test_recall_prompt_sent_after_answering(
        self,
        state: FSMContext,
        feed_callback_query: FeedCallbackQuery,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        exercise = make_exercise(
            recall_question="Ich ___ (die Rede).",
            recall_answer=["Ich halte die Rede."],
            recall_hint={"ru": "die Rede — речь", "en": "die Rede — speech"},
        )
        await state.set_state(UserState.answering)
        await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

        requests = await feed_callback_query(
            exercise.distractors[0], school=School([exercise])
        )
        recall_message = requests[2]

        assert exercise.recall is not None
        assert exercise.recall.question in recall_message.text
        assert "<i>die Rede — речь</i>" in recall_message.text

    async def test_recall_accepted_after_answering(
        self,
        state: FSMContext,
        feed_callback_query: FeedCallbackQuery,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        exercise = make_exercise(
            recall_question="Ich ___ (der Bus).",
            recall_answer=["Ich warte auf den Bus."],
        )
        await state.set_state(UserState.answering)
        await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

        assert exercise.recall is not None
        await feed_callback_query(exercise.distractors[0], school=School([exercise]))
        send_message = await feed_raw_update(
            exercise.recall.answer[0], school=School([exercise])
        )

        assert RU.recall_correct in send_message.text


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
        exercise = make_exercise()
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
        exercise = make_exercise(
            recall_question="Ich ___ (der Bus).",
            recall_answer=["Ich warte auf den Bus."],
        )
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
            recall_question="Ich ___ (der Bus).",
            recall_answer=["Ich warte auf den Bus."],
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
        exercise = make_exercise(
            recall_question="Ich ___ (der Bus).",
            recall_answer=["Ich warte auf den Bus."],
        )
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
        exercise = make_exercise(
            recall_question="Ich ___ (der Bus).",
            recall_answer=["Ich warte auf den Bus."],
        )
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


class TestLanguageCommand:
    async def test_switches_ru_to_en(
        self,
        state: FSMContext,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        await state.update_data(language="ru")
        send_message = await feed_raw_update("/language")

        assert (await state.get_data())["language"] == "en"
        assert send_message.text == EN.start

    async def test_switches_en_to_ru(
        self,
        state: FSMContext,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        await state.update_data(language="en")
        send_message = await feed_raw_update("/language")

        assert (await state.get_data())["language"] == "ru"
        assert send_message.text == RU.start

    async def test_defaults_to_ru_then_switches_to_en(
        self,
        state: FSMContext,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        send_message = await feed_raw_update("/language")

        assert (await state.get_data())["language"] == "en"
        assert send_message.text == EN.start
