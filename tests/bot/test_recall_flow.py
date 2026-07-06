import dataclasses

from aiogram.fsm.context import FSMContext

from wiederholen.bot import UserState
from wiederholen.bot.l10n import RU
from wiederholen.exercises import Exercise, Recall, School

from tests.plugins.aiogram import FeedRawUpdate, FeedRawUpdateAll
from tests.plugins.exercises import make_exercise


async def test_correct_input_shows_success(
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

    assert RU.recall_correct in send_message.text


async def test_wrong_input_shows_correct_sentence(
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
        "Es hängt alles in der Situation ab.", school=School([exercise])
    )

    assert "Ich warte auf den Bus." in send_message.text


async def test_normalizes_case_and_whitespace(
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
        "ich warte  auf den bus.", school=School([exercise])
    )

    assert RU.recall_correct in send_message.text


async def test_accepts_any_of_multiple_answers(
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
    state: FSMContext,
    feed_raw_update_all: FeedRawUpdateAll,
) -> None:
    exercise = make_exercise(
        recall={"hint": {"ru": "die Rede — речь", "en": "die Rede — speech"}},
    )
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

    requests = await feed_raw_update_all(
        exercise.distractors[0], school=School([exercise])
    )
    recall_message = requests[1]

    assert exercise.recall is not None
    assert exercise.recall.question in recall_message.text
    assert "<i>die Rede — речь</i>" in recall_message.text


async def test_recall_accepted_after_answering(
    state: FSMContext,
    feed_raw_update_all: FeedRawUpdateAll,
    feed_raw_update: FeedRawUpdate,
) -> None:
    exercise = make_exercise(recall=True)
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=dataclasses.asdict(exercise), journal={})

    assert exercise.recall is not None
    await feed_raw_update_all(exercise.distractors[0], school=School([exercise]))
    send_message = await feed_raw_update(
        exercise.recall.answer[0], school=School([exercise])
    )

    assert RU.recall_correct in send_message.text
