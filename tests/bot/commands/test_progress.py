from datetime import UTC, datetime, timedelta

from aiogram.fsm.context import FSMContext

from tests.plugins.aiogram import FeedMessage
from tests.plugins.tutoring import make_exercise
from wiederholen.bot.l10n import EN, RU, format_count
from wiederholen.tutoring import Course


async def test_defaults_to_ru(feed_message: FeedMessage) -> None:
    exercises = [make_exercise(word="warten"), make_exercise(word="hoffen")]
    requests = await feed_message("/progress", course=Course(exercises))

    assert len(requests) == 1
    assert requests[0].text == RU.progress_text.format(
        remaining_today=format_count(0, "exercises", "ru"),
        new_today=format_count(0, "words", "ru"),
        learning=format_count(0, "words", "ru"),
        mastered=format_count(0, "words", "ru"),
        answered_count=0,
        correct_today=0,
    )


async def test_responds_in_current_language(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    await state.update_data(language="en")
    exercises = [make_exercise(word="warten")]
    requests = await feed_message("/progress", course=Course(exercises))

    assert len(requests) == 1
    assert requests[0].text == EN.progress_text.format(
        remaining_today=format_count(0, "exercises", "en"),
        new_today=format_count(0, "words", "en"),
        learning=format_count(0, "words", "en"),
        mastered=format_count(0, "words", "en"),
        answered_today=format_count(0, "exercises", "en"),
        correct_today=0,
    )


async def test_reflects_journal_breakdown(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    new = make_exercise(word="warten")
    learning = make_exercise(word="hoffen")
    mastered = make_exercise(word="helfen")
    journal = {
        "word_schedule": {
            "hoffen": {
                "government": {
                    "interval_days": 30,
                    "due_date": (
                        datetime.now(UTC).date() + timedelta(days=20)
                    ).isoformat(),
                },
            },
            "helfen": {
                "government": {
                    "interval_days": 60,
                    "due_date": (
                        datetime.now(UTC).date() + timedelta(days=60)
                    ).isoformat(),
                },
            },
        }
    }
    await state.update_data(journal=journal)

    requests = await feed_message("/progress", course=Course([new, learning, mastered]))

    assert len(requests) == 1
    assert requests[0].text == RU.progress_text.format(
        remaining_today=format_count(0, "exercises", "ru"),
        new_today=format_count(0, "words", "ru"),
        learning=format_count(1, "words", "ru"),
        mastered=format_count(1, "words", "ru"),
        answered_count=0,
        correct_today=0,
    )


async def test_reflects_todays_answer_count(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise(word="warten")
    today = datetime.now(UTC).date().isoformat()
    journal = {"today_answers": {"date": today, "answered": 12, "correct": 9}}
    await state.update_data(journal=journal)

    requests = await feed_message("/progress", course=Course([exercise]))

    assert len(requests) == 1
    assert requests[0].text == RU.progress_text.format(
        remaining_today=format_count(0, "exercises", "ru"),
        new_today=format_count(0, "words", "ru"),
        learning=format_count(0, "words", "ru"),
        mastered=format_count(0, "words", "ru"),
        answered_count=12,
        correct_today=9,
    )
