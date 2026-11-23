import re
from datetime import UTC, datetime, timedelta
from typing import Any

from aiogram.fsm.context import FSMContext
from aiogram.methods import EditMessageReplyMarkup, SendMessage
from aiogram.types import InlineKeyboardMarkup

from tests.plugins.aiogram import FeedCallbackQuery, FeedMessage
from tests.plugins.curriculum import make_exercise
from tests.plugins.student_record_book import (
    IntroducePairs,
    ReadStudentRecord,
    SeedStudentRecord,
)
from wiederholen.bot.commands.wiederholen import NEXT_EXERCISE, RECALL, UserState
from wiederholen.bot.l10n import RU
from wiederholen.school import Course, StudentID


def _strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


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
    )

    requests = await feed_message("Ich warte auf den Bus.", course=Course([exercise]))

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
    )

    requests = await feed_message(
        "Es hängt alles in der Situation ab.", course=Course([exercise])
    )

    assert len(requests) == 1
    assert "Ich warte auf den Bus." in _strip_tags(requests[0].text)


async def test_wrong_input_highlights_the_typo(
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
    )

    requests = await feed_message("Ich warte auf den Bas.", course=Course([exercise]))

    assert len(requests) == 1
    assert "<u>u</u>" in requests[0].text


async def test_wrong_input_with_extra_letters_strikes_them_through(
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
    )

    requests = await feed_message("Ich warte auf den Buss.", course=Course([exercise]))

    assert requests[0].text == (
        "🔴 Неправильно.\nIch warte auf den Bus<s>s</s>. → Ich warte auf den Bus."
    )


async def test_wrong_input_marks_neither_case_nor_end_punctuation(
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
    )

    requests = await feed_message("ich warte auf den Bas", course=Course([exercise]))

    assert requests[0].text == (
        "🔴 Неправильно. Правильный ответ:\nIch warte auf den B<u>u</u>s."
    )


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
    )

    requests = await feed_message("ich warte  auf den bus.", course=Course([exercise]))

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
    )

    requests = await feed_message(
        "Ich warte auf die Straßenbahn.", course=Course([exercise])
    )

    assert len(requests) == 1
    assert RU.recall_correct in requests[0].text


async def test_recall_prompt_sent_after_answering(
    state: FSMContext,
    feed_message: FeedMessage,
    introduce_pairs: IntroducePairs,
) -> None:
    exercise = make_exercise(
        recalls=[{"hint": {"ru": "die Rede — речь", "en": "die Rede — speech"}}],
    )
    await introduce_pairs([exercise])
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=exercise.to_dict())

    requests = await feed_message(exercise.distractors[0], course=Course([exercise]))
    recall_message = requests[2]

    assert exercise.recalls
    assert exercise.recalls[0].question in recall_message.text
    assert "<i>die Rede — речь</i>" in recall_message.text


async def test_recall_prompt_escapes_question_and_hint(
    state: FSMContext,
    feed_message: FeedMessage,
    introduce_pairs: IntroducePairs,
) -> None:
    exercise = make_exercise(
        recalls=[
            {
                "question": "Ich ___ <b>Tom & Jerry</b>.",
                "hint": {"ru": "a < b & c", "en": "a < b & c"},
            }
        ],
    )
    await introduce_pairs([exercise])
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=exercise.to_dict())

    requests = await feed_message(exercise.distractors[0], course=Course([exercise]))
    recall_message = requests[2]

    assert "Ich ___ &lt;b&gt;Tom &amp; Jerry&lt;/b&gt;." in recall_message.text
    assert "<i>a &lt; b &amp; c</i>" in recall_message.text


async def test_recall_prompt_without_hint_escapes_question(
    state: FSMContext,
    feed_message: FeedMessage,
    introduce_pairs: IntroducePairs,
) -> None:
    exercise = make_exercise(recalls=[{"question": "Ich ___ Tom & Jerry."}])
    await introduce_pairs([exercise])
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=exercise.to_dict())

    requests = await feed_message(exercise.distractors[0], course=Course([exercise]))
    recall_message = requests[2]

    assert "Ich ___ Tom &amp; Jerry." in recall_message.text
    assert "<i>" not in recall_message.text


async def test_recall_accepted_after_answering(
    state: FSMContext,
    feed_message: FeedMessage,
    introduce_pairs: IntroducePairs,
) -> None:
    exercise = make_exercise(recalls=True)
    await introduce_pairs([exercise])
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=exercise.to_dict())

    assert exercise.recalls
    await feed_message(exercise.distractors[0], course=Course([exercise]))
    requests = await feed_message(
        exercise.recalls[0].answer[0],
        course=Course([exercise]),
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
    )

    requests = await feed_message(
        "Es hängt alles in der Situation ab.", course=Course([exercise])
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
    seed_student_record: SeedStudentRecord,
    student_id: StudentID,
) -> None:
    exercise = make_exercise(
        recalls=[{"answer": ["Ich warte auf den Bus."]}],
    )
    await state.set_state(UserState.recalling)
    await state.update_data(
        shown_exercise=exercise.to_dict(),
        shown_recall=exercise.recalls[0].to_dict(),
        language="ru",
    )
    await seed_student_record(
        student_id,
        {
            "last_exercise": {
                "question": exercise.question,
                "word": exercise.word,
                "topic": exercise.topic,
                "is_recall_optional": False,
            }
        },
    )

    await feed_message("Es hängt alles in der Situation ab.", course=Course([exercise]))
    requests = await feed_callback_query(RECALL, course=Course([exercise]))
    recall_message = requests[1]

    assert exercise.recalls
    assert exercise.recalls[0].question in recall_message.text
    assert await state.get_state() == UserState.recalling


async def test_retry_avoids_repeating_last_recall_variant(
    state: FSMContext,
    feed_message: FeedMessage,
    feed_callback_query: FeedCallbackQuery,
    seed_student_record: SeedStudentRecord,
    student_id: StudentID,
) -> None:
    exercise = make_exercise(
        word="helfen",
        topic="partizip_ii",
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
    )
    await seed_student_record(
        student_id,
        {
            "last_exercise": {
                "question": exercise.question,
                "word": exercise.word,
                "topic": exercise.topic,
                "is_recall_optional": False,
                "recall_question": exercise.recalls[0].question,
            }
        },
    )

    await feed_message("das ist ganz falsch", course=Course([exercise]))
    requests = await feed_callback_query(RECALL, course=Course([exercise]))
    recall_message = requests[1]

    assert exercise.recalls[1].question in recall_message.text


async def test_requesting_recall_after_correct_answer_halves_the_interval(
    state: FSMContext,
    feed_message: FeedMessage,
    feed_callback_query: FeedCallbackQuery,
    seed_student_record: SeedStudentRecord,
    read_student_record: ReadStudentRecord,
    student_id: StudentID,
) -> None:
    exercise = make_exercise(recalls=True)
    today = datetime.now(UTC).date()
    student_record = {
        "word_schedule": {
            "warten": {
                "government": {
                    "repetition_interval": 8,
                    "due_date": today.isoformat(),
                },
            },
        }
    }
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=exercise.to_dict())
    await seed_student_record(student_id, student_record)

    await feed_message(exercise.answer[0], course=Course([exercise]))
    await feed_callback_query(RECALL, course=Course([exercise]))

    student_record = await read_student_record(student_id)
    entry = student_record["word_schedule"]["warten"]["government"]
    assert entry["repetition_interval"] == 8
    assert entry["due_date"] == (today + timedelta(days=8)).isoformat()


async def test_wiederholen_during_a_recall_shows_the_next_exercise(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(recalls=[{"answer": ["Ich warte auf den Bus."]}])
    hoffen = make_exercise(word="hoffen")
    await state.set_state(UserState.recalling)
    await state.update_data(
        shown_exercise=exercise.to_dict(),
        shown_recall=exercise.recalls[0].to_dict(),
    )

    # Only hoffen is left to show, so a repeated recall prompt would fail
    await feed_message("/wiederholen", course=Course([hoffen]))

    assert await state.get_state() == UserState.answering
    assert (await state.get_data())["shown_exercise"] == hoffen.to_dict()


def _button_data(request: Any) -> list[tuple[str, str | None]]:
    assert isinstance(request.reply_markup, InlineKeyboardMarkup)
    return [
        (button.text, button.callback_data)
        for row in request.reply_markup.inline_keyboard
        for button in row
    ]


async def test_a_recall_after_a_wrong_first_answer_can_be_skipped(
    state: FSMContext,
    feed_message: FeedMessage,
    feed_callback_query: FeedCallbackQuery,
) -> None:
    warten = make_exercise(word="warten", recalls=True)
    hoffen = make_exercise(word="hoffen")
    course = Course([warten, hoffen])
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=warten.to_dict())
    await feed_message(warten.distractors[0], course=course)

    requests = await feed_callback_query(RECALL, course=course)
    prompt = [r for r in requests if isinstance(r, SendMessage)][-1]
    assert _button_data(prompt) == [(RU.btn_recall_skip, NEXT_EXERCISE)]
    await feed_callback_query(NEXT_EXERCISE, course=course)

    assert await state.get_state() == UserState.answering
    assert (await state.get_data())["shown_exercise"] == hoffen.to_dict()


async def test_a_required_recall_has_no_skip_button(
    state: FSMContext,
    feed_message: FeedMessage,
    introduce_pairs: IntroducePairs,
) -> None:
    exercise = make_exercise(recalls=True)
    await introduce_pairs([exercise])
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=exercise.to_dict())

    requests = await feed_message(exercise.distractors[0], course=Course([exercise]))

    assert requests[-1].reply_markup is None


async def test_an_answer_to_a_skippable_recall_removes_the_skip_button(
    state: FSMContext,
    feed_message: FeedMessage,
    feed_callback_query: FeedCallbackQuery,
) -> None:
    exercise = make_exercise(recalls=True)
    course = Course([exercise])
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=exercise.to_dict())
    await feed_message(exercise.distractors[0], course=course)
    await feed_callback_query(RECALL, course=course)

    requests = await feed_message(exercise.recalls[0].answer[0], course=course)

    assert isinstance(requests[0], EditMessageReplyMarkup)
    assert requests[0].reply_markup is None
