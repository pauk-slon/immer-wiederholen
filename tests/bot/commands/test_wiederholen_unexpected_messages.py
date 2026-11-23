import pytest
from aiogram.fsm.context import FSMContext
from aiogram.methods import SendMessage

from tests.plugins.aiogram import FeedCallbackQuery, FeedMessage, FeedRawUpdate
from tests.plugins.curriculum import make_exercise
from tests.plugins.student_record_book import ReadStudentRecord
from tests.plugins.telegram import MessageFactory
from wiederholen.bot.commands.wiederholen import NEXT_EXERCISE, UserState
from wiederholen.bot.l10n import RU
from wiederholen.school import Course, StudentID

EXERCISE = make_exercise(recalls=[{"answer": ["Ich warte auf den Bus."]}])
COURSE = Course([EXERCISE])


def _sticker(message_factory: MessageFactory) -> dict:
    raw_update = message_factory("")
    message = raw_update["message"]
    del message["text"]
    message["sticker"] = {
        "file_id": "x",
        "file_unique_id": "x",
        "type": "regular",
        "width": 512,
        "height": 512,
        "is_animated": False,
        "is_video": False,
    }
    return raw_update


def _texts(requests: list) -> list[str]:
    return [request.text for request in requests if isinstance(request, SendMessage)]


async def test_a_sticker_during_an_exercise_isnt_an_answer(
    state: FSMContext,
    feed_message: FeedMessage,
    feed_raw_update: FeedRawUpdate,
    message_factory: MessageFactory,
    read_student_record: ReadStudentRecord,
    student_id: StudentID,
) -> None:
    await feed_message("/wiederholen", course=COURSE)

    requests = await feed_raw_update(_sticker(message_factory), course=COURSE)

    assert _texts(requests) == [RU.unexpected_message]
    assert await state.get_state() == UserState.answering
    assert not (await read_student_record(student_id)).get("word_schedule")


async def test_an_unknown_command_during_an_exercise_keeps_the_exercise(
    state: FSMContext,
    feed_message: FeedMessage,
    feed_callback_query: FeedCallbackQuery,
) -> None:
    await feed_message("/wiederholen", course=COURSE)

    requests = await feed_message("/help", course=COURSE)
    shown_again = await feed_callback_query(NEXT_EXERCISE, course=COURSE)

    assert RU.unexpected_message in _texts(requests)
    assert any(EXERCISE.question in text for text in _texts(shown_again))
    assert await state.get_state() == UserState.answering


@pytest.mark.parametrize("message", ["sticker", "/help"])
async def test_a_message_during_a_recall_shows_the_recall_again(
    state: FSMContext,
    feed_message: FeedMessage,
    feed_raw_update: FeedRawUpdate,
    message_factory: MessageFactory,
    message: str,
) -> None:
    await state.set_state(UserState.recalling)
    await state.update_data(
        shown_exercise=EXERCISE.to_dict(),
        shown_recall=EXERCISE.recalls[0].to_dict(),
    )

    if message == "sticker":
        requests = await feed_raw_update(_sticker(message_factory), course=COURSE)
    else:
        requests = await feed_message(message, course=COURSE)

    recall = EXERCISE.recalls[0]
    assert _texts(requests) == [RU.recall_prompt.format(recall=recall.question)]
    assert requests[-1].reply_markup is None
    assert await state.get_state() == UserState.recalling
