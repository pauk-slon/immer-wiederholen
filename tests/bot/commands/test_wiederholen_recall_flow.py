import dataclasses

from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup

from wiederholen.bot.commands.wiederholen import NEXT_EXERCISE, RECALL, UserState
from wiederholen.bot.l10n import RU
from wiederholen.exercises import Exercise, Recall, School

from tests.plugins.aiogram import FeedCallbackQuery, FeedMessage
from tests.plugins.exercises import make_exercise


async def test_correct_input_shows_success(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(
        recall={"answer": ["Ich warte auf den Bus."]},
    )
    await state.set_state(UserState.recalling)
    await state.update_data(
        shown_exercise=dataclasses.asdict(exercise), language="ru", journal={}
    )

    requests = await feed_message("Ich warte auf den Bus.", school=School([exercise]))

    assert len(requests) == 1
    assert RU.recall_correct in requests[0].text


async def test_wrong_input_shows_correct_sentence(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(
        recall={"answer": ["Ich warte auf den Bus."]},
    )
    await state.set_state(UserState.recalling)
    await state.update_data(
        shown_exercise=dataclasses.asdict(exercise), language="ru", journal={}
    )

    requests = await feed_message(
        "Es hängt alles in der Situation ab.", school=School([exercise])
    )

    assert len(requests) == 1
    assert "Ich warte auf den Bus." in requests[0].text


async def test_normalizes_case_and_whitespace(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(
        recall={"answer": ["Ich warte auf den Bus."]},
    )
    await state.set_state(UserState.recalling)
    await state.update_data(
        shown_exercise=dataclasses.asdict(exercise), language="ru", journal={}
    )

    requests = await feed_message("ich warte  auf den bus.", school=School([exercise]))

    assert len(requests) == 1
    assert RU.recall_correct in requests[0].text


async def test_accepts_any_of_multiple_answers(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = Exercise(
        question="Ich warte ___ den Bus.",
        topic="warten",
        category="government",
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

    requests = await feed_message(
        "Ich warte auf die Straßenbahn.", school=School([exercise])
    )

    assert len(requests) == 1
    assert RU.recall_correct in requests[0].text


async def test_recall_prompt_sent_after_answering(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(
        recall={"hint": {"ru": "die Rede — речь", "en": "die Rede — speech"}},
    )
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

    requests = await feed_message(exercise.distractors[0], school=School([exercise]))
    recall_message = requests[2]

    assert exercise.recall is not None
    assert exercise.recall.question in recall_message.text
    assert "<i>die Rede — речь</i>" in recall_message.text


async def test_recall_accepted_after_answering(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(recall=True)
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

    assert exercise.recall is not None
    await feed_message(exercise.distractors[0], school=School([exercise]))
    requests = await feed_message(exercise.recall.answer[0], school=School([exercise]))

    assert len(requests) == 1
    assert RU.recall_correct in requests[0].text


async def test_retry_button_appears_after_wrong_recall(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(
        recall={"answer": ["Ich warte auf den Bus."]},
    )
    await state.set_state(UserState.recalling)
    await state.update_data(
        shown_exercise=dataclasses.asdict(exercise), language="ru", journal={}
    )

    requests = await feed_message(
        "Es hängt alles in der Situation ab.", school=School([exercise])
    )

    assert isinstance(requests[0].reply_markup, InlineKeyboardMarkup)
    buttons = [
        btn.callback_data
        for row in requests[0].reply_markup.inline_keyboard
        for btn in row
    ]
    assert buttons == [RECALL, NEXT_EXERCISE]


async def test_clicking_retry_starts_recall_again(
    state: FSMContext,
    feed_message: FeedMessage,
    feed_callback_query: FeedCallbackQuery,
) -> None:
    exercise = make_exercise(
        recall={"answer": ["Ich warte auf den Bus."]},
    )
    await state.set_state(UserState.recalling)
    await state.update_data(
        shown_exercise=dataclasses.asdict(exercise), language="ru", journal={}
    )

    await feed_message("Es hängt alles in der Situation ab.", school=School([exercise]))
    requests = await feed_callback_query(RECALL, school=School([exercise]))
    recall_message = requests[1]

    assert exercise.recall is not None
    assert exercise.recall.question in recall_message.text
    assert await state.get_state() == UserState.recalling
