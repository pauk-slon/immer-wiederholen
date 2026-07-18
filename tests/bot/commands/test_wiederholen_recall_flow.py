from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup

from wiederholen.bot.commands.wiederholen import NEXT_EXERCISE, RECALL, UserState
from wiederholen.bot.l10n import RU
from wiederholen.exercises import School

from tests.plugins.aiogram import FeedCallbackQuery, FeedMessage
from tests.plugins.exercises import make_exercise


async def test_correct_input_shows_success(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(
        recalls=[{"answer": ["Ich warte auf den Bus."]}],
    )
    await state.set_state(UserState.recalling)
    await state.update_data(
        shown_exercise=exercise.to_dict(),
        shown_recall=exercise.recalls[0].to_dict(),
        language="ru",
        journal={},
    )

    requests = await feed_message("Ich warte auf den Bus.", school=School([exercise]))

    assert len(requests) == 1
    assert RU.recall_correct in requests[0].text


async def test_wrong_input_shows_correct_sentence(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(
        recalls=[{"answer": ["Ich warte auf den Bus."]}],
    )
    await state.set_state(UserState.recalling)
    await state.update_data(
        shown_exercise=exercise.to_dict(),
        shown_recall=exercise.recalls[0].to_dict(),
        language="ru",
        journal={},
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
        recalls=[{"answer": ["Ich warte auf den Bus."]}],
    )
    await state.set_state(UserState.recalling)
    await state.update_data(
        shown_exercise=exercise.to_dict(),
        shown_recall=exercise.recalls[0].to_dict(),
        language="ru",
        journal={},
    )

    requests = await feed_message("ich warte  auf den bus.", school=School([exercise]))

    assert len(requests) == 1
    assert RU.recall_correct in requests[0].text


async def test_accepts_any_of_multiple_answers(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(
        recalls=[
            {"answer": ["Ich warte auf den Bus.", "Ich warte auf die Straßenbahn."]},
        ],
    )
    await state.set_state(UserState.recalling)
    await state.update_data(
        shown_exercise=exercise.to_dict(),
        shown_recall=exercise.recalls[0].to_dict(),
        language="ru",
        journal={},
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
        recalls=[{"hint": {"ru": "die Rede — речь", "en": "die Rede — speech"}}],
    )
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=exercise.to_dict(), journal={})

    requests = await feed_message(exercise.distractors[0], school=School([exercise]))
    recall_message = requests[2]

    assert exercise.recalls
    assert exercise.recalls[0].question in recall_message.text
    assert "<i>die Rede — речь</i>" in recall_message.text


async def test_recall_accepted_after_answering(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(recalls=True)
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=exercise.to_dict(), journal={})

    assert exercise.recalls
    await feed_message(exercise.distractors[0], school=School([exercise]))
    requests = await feed_message(
        exercise.recalls[0].answer[0],
        school=School([exercise]),
    )

    assert len(requests) == 1
    assert RU.recall_correct in requests[0].text


async def test_retry_button_appears_after_wrong_recall(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(
        recalls=[{"answer": ["Ich warte auf den Bus."]}],
    )
    await state.set_state(UserState.recalling)
    await state.update_data(
        shown_exercise=exercise.to_dict(),
        shown_recall=exercise.recalls[0].to_dict(),
        language="ru",
        journal={},
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
        recalls=[{"answer": ["Ich warte auf den Bus."]}],
    )
    await state.set_state(UserState.recalling)
    await state.update_data(
        shown_exercise=exercise.to_dict(),
        shown_recall=exercise.recalls[0].to_dict(),
        language="ru",
        journal={},
    )

    await feed_message("Es hängt alles in der Situation ab.", school=School([exercise]))
    requests = await feed_callback_query(RECALL, school=School([exercise]))
    recall_message = requests[1]

    assert exercise.recalls
    assert exercise.recalls[0].question in recall_message.text
    assert await state.get_state() == UserState.recalling


async def test_retry_avoids_repeating_last_recall_variant(
    state: FSMContext,
    feed_message: FeedMessage,
    feed_callback_query: FeedCallbackQuery,
) -> None:
    exercise = make_exercise(
        topic="helfen",
        category="partizip_ii",
        answer="geholfen",
        distractors=[],
        recalls=[
            {"question": "Er hat mir ___.", "answer": ["Er hat mir geholfen."]},
            {"question": "Sie hat ihr ___.", "answer": ["Sie hat ihr geholfen."]},
        ],
    )
    await state.set_state(UserState.recalling)
    await state.update_data(
        shown_exercise=exercise.to_dict(),
        shown_recall=exercise.recalls[0].to_dict(),
        language="ru",
        journal={"last_recall_question": exercise.recalls[0].question},
    )

    await feed_message("das ist ganz falsch", school=School([exercise]))
    requests = await feed_callback_query(RECALL, school=School([exercise]))
    recall_message = requests[1]

    assert exercise.recalls[1].question in recall_message.text
