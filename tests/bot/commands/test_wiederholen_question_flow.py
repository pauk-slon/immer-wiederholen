from datetime import UTC, datetime, timedelta

from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from tests.plugins.aiogram import FeedMessage
from tests.plugins.curriculum import make_exercise
from tests.plugins.student_record_book import SeedStudentRecord
from wiederholen.bot.commands.wiederholen import STUDY_MORE, UserState
from wiederholen.bot.l10n import RU
from wiederholen.school import Course, Exercise, Language, Tutor


async def test_sends_exercise_question(
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise()
    requests = await feed_message("/wiederholen", course=Course([exercise]))

    assert len(requests) == 1
    assert exercise.question in requests[0].text


async def test_sets_answering_state(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise()
    requests = await feed_message("/wiederholen", course=Course([exercise]))

    assert len(requests) == 1
    assert await state.get_state() == UserState.answering


async def test_saves_shown_exercise(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise()
    requests = await feed_message("/wiederholen", course=Course([exercise]))

    assert len(requests) == 1
    data = await state.get_data()
    assert data["shown_exercise"] == exercise.to_dict()


async def test_reply_keyboard_contains_all_options(
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise()
    requests = await feed_message("/wiederholen", course=Course([exercise]))

    assert len(requests) == 1
    assert isinstance(requests[0].reply_markup, ReplyKeyboardMarkup)
    buttons = [btn.text for row in requests[0].reply_markup.keyboard for btn in row]
    assert sorted(buttons) == sorted(exercise.distractors + [exercise.answer])


async def test_reply_keyboard_remove_for_input_exercise(
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(distractors=[])
    requests = await feed_message("/wiederholen", course=Course([exercise]))

    assert len(requests) == 1
    assert isinstance(requests[0].reply_markup, ReplyKeyboardRemove)


async def test_omits_description_block_when_absent(
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise()
    requests = await feed_message("/wiederholen", course=Course([exercise]))

    assert len(requests) == 1
    assert "💭" not in requests[0].text


async def test_shows_description_in_ru_by_default(
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(
        topic="preposition_meaning",
        distractors=[],
        description={
            "ru": "Поезд едет через туннель.",
            "en": "The train goes through the tunnel.",
        },
    )
    requests = await feed_message("/wiederholen", course=Course([exercise]))

    assert len(requests) == 1
    assert "💭 Поезд едет через туннель." in requests[0].text


async def test_shows_description_in_current_language(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    await state.update_data(language="en")
    exercise = make_exercise(
        topic="preposition_meaning",
        distractors=[],
        description={
            "ru": "Поезд едет через туннель.",
            "en": "The train goes through the tunnel.",
        },
    )
    requests = await feed_message("/wiederholen", course=Course([exercise]))

    assert len(requests) == 1
    assert "💭 The train goes through the tunnel." in requests[0].text


async def test_omits_topic_instruction_when_topic_has_none(
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise()
    requests = await feed_message("/wiederholen", course=Course([exercise]))

    assert len(requests) == 1
    assert "ℹ️" not in requests[0].text


async def test_shows_topic_instruction_in_current_language(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    await state.update_data(language="en")
    exercise = make_exercise(topic="konjunktion_wortstellung", distractors=[])
    topic_instructions: dict[str, dict[Language, str]] = {
        "konjunktion_wortstellung": {
            "ru": "Заполни пропуски в правильном порядке.",
            "en": "Fill in the blank with the words in the correct order.",
        },
    }
    requests = await feed_message(
        "/wiederholen",
        course=Course([exercise], topic_instructions=topic_instructions),
    )

    assert len(requests) == 1
    assert (
        "ℹ️ Fill in the blank with the words in the correct order." in requests[0].text
    )


async def test_shows_both_description_and_topic_instruction_independently(
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(
        topic="preposition_meaning",
        distractors=[],
        description={"ru": "Поезд едет через туннель.", "en": "..."},
    )
    topic_instructions: dict[str, dict[Language, str]] = {
        "preposition_meaning": {"ru": "Введи пропущенное слово.", "en": "..."},
    }
    requests = await feed_message(
        "/wiederholen",
        course=Course([exercise], topic_instructions=topic_instructions),
    )

    assert len(requests) == 1
    assert "💭 Поезд едет через туннель." in requests[0].text
    assert "ℹ️ Введи пропущенное слово." in requests[0].text


async def test_avoids_repeating_previously_shown_question(
    state: FSMContext,
    feed_message: FeedMessage,
    seed_student_record: SeedStudentRecord,
    chat_id: int,
) -> None:
    mit = Exercise(
        word="sprechen",
        topic="government",
        question="Ich spreche ___ meiner Mutter.",
        answer="mit",
        distractors=["über", "an", "für"],
        explanation={"ru": "x", "en": "y"},
    )
    ueber = Exercise(
        word="sprechen",
        topic="government",
        question="Wir sprechen ___ das Problem.",
        answer="über",
        distractors=["mit", "an", "für"],
        explanation={"ru": "x", "en": "y"},
    )
    await seed_student_record(
        str(chat_id), {"last_exercise": {"question": mit.question}}
    )

    requests = await feed_message("/wiederholen", course=Course([mit, ueber]))

    assert len(requests) == 1
    assert ueber.question in requests[0].text


async def test_shows_nothing_due_message_once_daily_new_word_cap_is_reached(
    state: FSMContext,
    feed_message: FeedMessage,
    seed_student_record: SeedStudentRecord,
    chat_id: int,
) -> None:
    exercise = make_exercise(word="warten")
    today = datetime.now(UTC).date()
    capped_exercises = [
        make_exercise(word=f"introduced{i}") for i in range(Tutor.NEW_WORDS_PER_DAY)
    ]
    word_schedule = {
        f"introduced{i}": {
            "government": {
                "repetition_interval": 1,
                "due_date": (today + timedelta(days=30)).isoformat(),
                "introduced_at": today.isoformat(),
            },
        }
        for i in range(Tutor.NEW_WORDS_PER_DAY)
    }
    await seed_student_record(str(chat_id), {"word_schedule": word_schedule})

    requests = await feed_message(
        "/wiederholen", course=Course([exercise, *capped_exercises])
    )

    assert len(requests) == 1
    assert requests[0].text == RU.nothing_due_text
    assert await state.get_state() is None
    assert isinstance(requests[0].reply_markup, InlineKeyboardMarkup)
    buttons = [
        btn.callback_data
        for row in requests[0].reply_markup.inline_keyboard
        for btn in row
    ]
    assert STUDY_MORE in buttons
