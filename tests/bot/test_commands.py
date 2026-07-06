import dataclasses

import pytest

from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup

from wiederholen.bot import UserState
from wiederholen.bot.l10n import EN, RU
from wiederholen.exercises import School

from tests.plugins.aiogram import FeedRawUpdate
from tests.plugins.exercises import make_exercise


class TestStartCommand:
    async def test_defaults_to_ru(
        self,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        send_message = await feed_raw_update("/start")

        assert send_message.text == RU.start

    @pytest.mark.parametrize("language,expected", [("ru", RU.start), ("en", EN.start)])
    async def test_responds_in_current_language(
        self,
        state: FSMContext,
        feed_raw_update: FeedRawUpdate,
        language: str,
        expected: str,
    ) -> None:
        await state.update_data(language=language)
        send_message = await feed_raw_update("/start")

        assert send_message.text == expected


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

        assert await state.get_state() == UserState.answering_choice

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

    async def test_sets_typing_state_for_input_exercise(
        self,
        state: FSMContext,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        exercise = make_exercise(distractors=[])
        await feed_raw_update("/wiederholen", school=School([exercise]))

        assert await state.get_state() == UserState.answering_input

    async def test_no_keyboard_for_input_exercise(
        self,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        exercise = make_exercise(distractors=[])
        send_message = await feed_raw_update("/wiederholen", school=School([exercise]))

        assert send_message.reply_markup is None


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
