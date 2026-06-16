import pytest
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup

from iwh.bot import UserState
from iwh.cards import Card
from iwh.locales import EN, RU

from .conftest import FeedRawUpdate


class TestWiederholenCommand:
    @pytest.fixture
    def card(self) -> Card:
        return Card(
            question="Ich warte ___ den Bus.",
            distractors=["für", "von", "bei"],
            answer="auf",
            explanation={"ru": "warten auf + Akk", "en": "warten auf + Acc"},
        )

    async def test_sends_card_question(
        self,
        card: Card,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        send_message = await feed_raw_update("/wiederholen", card_picker=lambda: card)

        assert send_message.text == card.question

    async def test_sets_answering_state(
        self,
        card: Card,
        state: FSMContext,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        await feed_raw_update("/wiederholen", card_picker=lambda: card)

        assert await state.get_state() == UserState.answering

    async def test_saves_answer_and_explanation(
        self,
        card: Card,
        state: FSMContext,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        await feed_raw_update("/wiederholen", card_picker=lambda: card)

        data = await state.get_data()
        assert data["answer"] == card.answer
        assert data["explanation"] == card.explanation

    async def test_keyboard_contains_all_options(
        self,
        card: Card,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        send_message = await feed_raw_update("/wiederholen", card_picker=lambda: card)

        assert isinstance(send_message.reply_markup, InlineKeyboardMarkup)
        buttons = [
            btn.text for row in send_message.reply_markup.inline_keyboard for btn in row
        ]
        assert sorted(buttons) == sorted(card.distractors + [card.answer])


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
