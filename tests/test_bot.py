import dataclasses

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup

from wiederholen.bot import UserState
from wiederholen.bot.l10n import EN, RU
from wiederholen.cards import Card, School

from .conftest import FeedCallbackQuery, FeedRawUpdate


class TestWiederholenCommand:
    @pytest.fixture
    def card(self) -> Card:
        return Card(
            question="Ich warte ___ den Bus.",
            topic="warten",
            distractors=["für", "von", "bei"],
            answer="auf",
            explanation={"ru": "warten auf + Akk", "en": "warten auf + Acc"},
        )

    async def test_sends_card_question(
        self,
        card: Card,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        send_message = await feed_raw_update("/wiederholen", school=School([card]))

        assert send_message.text == card.question

    async def test_sets_answering_state(
        self,
        card: Card,
        state: FSMContext,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        await feed_raw_update("/wiederholen", school=School([card]))

        assert await state.get_state() == UserState.answering

    async def test_saves_shown_card(
        self,
        card: Card,
        state: FSMContext,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        await feed_raw_update("/wiederholen", school=School([card]))

        data = await state.get_data()
        assert data["shown_card"] == dataclasses.asdict(card)

    async def test_keyboard_contains_all_options(
        self,
        card: Card,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        send_message = await feed_raw_update("/wiederholen", school=School([card]))

        assert isinstance(send_message.reply_markup, InlineKeyboardMarkup)
        buttons = [
            btn.text for row in send_message.reply_markup.inline_keyboard for btn in row
        ]
        assert sorted(buttons) == sorted(card.distractors + [card.answer])


class TestHandleAnswer:
    @pytest.fixture
    def card(self) -> Card:
        return Card(
            question="Ich warte ___ den Bus.",
            topic="warten",
            distractors=["für", "an", "um"],
            answer="auf",
            explanation={"ru": "warten auf + Akk", "en": "warten auf + Acc"},
        )

    async def test_correct_answer_shows_success_text(
        self,
        card: Card,
        state: FSMContext,
        feed_callback_query: FeedCallbackQuery,
    ) -> None:
        await state.set_state(UserState.answering)
        await state.update_data(shown_card=dataclasses.asdict(card), card_picker_state={})

        edit_message = await feed_callback_query(card.answer, school=School([card]))

        assert RU.correct in edit_message.text
        assert card.explanation["ru"] in edit_message.text

    async def test_wrong_answer_shows_correct_answer(
        self,
        card: Card,
        state: FSMContext,
        feed_callback_query: FeedCallbackQuery,
    ) -> None:
        await state.set_state(UserState.answering)
        await state.update_data(shown_card=dataclasses.asdict(card), card_picker_state={})

        edit_message = await feed_callback_query(card.distractors[0], school=School([card]))

        assert card.answer in edit_message.text
        assert card.explanation["ru"] in edit_message.text


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
