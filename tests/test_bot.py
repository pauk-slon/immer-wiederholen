import dataclasses

from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup

from wiederholen.bot import UserState
from wiederholen.bot.l10n import EN, RU
from wiederholen.cards import Card, School

from .conftest import FeedCallbackQuery, FeedRawUpdate, make_card


class TestWiederholenCommand:
    async def test_sends_card_question(
        self,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        card = make_card()
        send_message = await feed_raw_update("/wiederholen", school=School([card]))

        assert send_message.text == card.question

    async def test_sets_answering_state(
        self,
        state: FSMContext,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        card = make_card()
        await feed_raw_update("/wiederholen", school=School([card]))

        assert await state.get_state() == UserState.answering

    async def test_saves_shown_card(
        self,
        state: FSMContext,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        card = make_card()
        await feed_raw_update("/wiederholen", school=School([card]))

        data = await state.get_data()
        assert data["shown_card"] == dataclasses.asdict(card)

    async def test_keyboard_contains_all_options(
        self,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        card = make_card()
        send_message = await feed_raw_update("/wiederholen", school=School([card]))

        assert isinstance(send_message.reply_markup, InlineKeyboardMarkup)
        buttons = [
            btn.text for row in send_message.reply_markup.inline_keyboard for btn in row
        ]
        assert sorted(buttons) == sorted(card.distractors + [card.answer])


class TestHandleAnswer:
    async def test_correct_answer_shows_success_text(
        self,
        state: FSMContext,
        feed_callback_query: FeedCallbackQuery,
    ) -> None:
        card = make_card()
        await state.set_state(UserState.answering)
        await state.update_data(shown_card=dataclasses.asdict(card), journal={})

        edit_message = await feed_callback_query(card.answer, school=School([card]))

        assert RU.correct in edit_message.text
        assert card.explanation["ru"] in edit_message.text

    async def test_wrong_answer_shows_correct_answer(
        self,
        state: FSMContext,
        feed_callback_query: FeedCallbackQuery,
    ) -> None:
        card = make_card()
        await state.set_state(UserState.answering)
        await state.update_data(shown_card=dataclasses.asdict(card), journal={})

        edit_message = await feed_callback_query(
            card.distractors[0], school=School([card])
        )

        assert card.answer in edit_message.text
        assert card.explanation["ru"] in edit_message.text


class TestHandleRecall:
    async def test_correct_input_shows_success(
        self,
        state: FSMContext,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        card = make_card(
            recall="Ich ___ (der Bus).",
            recall_answer=["Ich warte auf den Bus."],
        )
        await state.set_state(UserState.recalling)
        await state.update_data(
            shown_card=dataclasses.asdict(card), language="ru", journal={}
        )

        send_message = await feed_raw_update(
            "Ich warte auf den Bus.", school=School([card])
        )

        assert RU.recall_correct in send_message.text

    async def test_wrong_input_shows_correct_sentence(
        self,
        state: FSMContext,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        card = make_card(
            recall="Ich ___ (der Bus).",
            recall_answer=["Ich warte auf den Bus."],
        )
        await state.set_state(UserState.recalling)
        await state.update_data(
            shown_card=dataclasses.asdict(card), language="ru", journal={}
        )

        send_message = await feed_raw_update(
            "Es hängt alles in der Situation ab.", school=School([card])
        )

        assert "Ich warte auf den Bus." in send_message.text

    async def test_normalizes_case_and_whitespace(
        self,
        state: FSMContext,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        card = make_card(
            recall="Ich ___ (der Bus).",
            recall_answer=["Ich warte auf den Bus."],
        )
        await state.set_state(UserState.recalling)
        await state.update_data(
            shown_card=dataclasses.asdict(card), language="ru", journal={}
        )

        send_message = await feed_raw_update(
            "ich warte  auf den bus.", school=School([card])
        )

        assert RU.recall_correct in send_message.text

    async def test_accepts_any_of_multiple_answers(
        self,
        state: FSMContext,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        card = Card(
            question="Ich warte ___ den Bus.",
            topic="warten",
            distractors=["für", "an", "um"],
            answer="auf",
            explanation={"ru": "warten auf + Akk", "en": "warten auf + Acc"},
            recall="Ich warte ___ (der Bus).",
            recall_answer=["Ich warte auf den Bus.", "Ich warte auf die Straßenbahn."],
        )
        await state.set_state(UserState.recalling)
        await state.update_data(
            shown_card=dataclasses.asdict(card), language="ru", journal={}
        )

        send_message = await feed_raw_update(
            "Ich warte auf die Straßenbahn.", school=School([card])
        )

        assert RU.recall_correct in send_message.text

    async def test_recall_triggered_after_answering(
        self,
        state: FSMContext,
        feed_callback_query: FeedCallbackQuery,
        feed_raw_update: FeedRawUpdate,
    ) -> None:
        card = make_card(
            recall="Ich ___ (der Bus).",
            recall_answer=["Ich warte auf den Bus."],
        )
        await state.set_state(UserState.answering)
        await state.update_data(shown_card=dataclasses.asdict(card), journal={})

        assert card.recall_answer is not None
        await feed_callback_query(card.answer, school=School([card]))
        send_message = await feed_raw_update(
            card.recall_answer[0], school=School([card])
        )

        assert RU.recall_correct in send_message.text


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
