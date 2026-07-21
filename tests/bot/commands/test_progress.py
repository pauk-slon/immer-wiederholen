from datetime import date, timedelta

from aiogram.fsm.context import FSMContext

from wiederholen.bot.l10n import EN, RU
from wiederholen.exercises import Course

from tests.plugins.aiogram import FeedMessage
from tests.plugins.exercises import make_exercise


async def test_defaults_to_ru(feed_message: FeedMessage) -> None:
    exercises = [make_exercise(topic="warten"), make_exercise(topic="hoffen")]
    requests = await feed_message("/progress", course=Course(exercises))

    assert len(requests) == 1
    assert requests[0].text == RU.progress_text.format(
        due=2, new=2, learning=0, mastered=0, total=2
    )


async def test_responds_in_current_language(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    await state.update_data(language="en")
    exercises = [make_exercise(topic="warten")]
    requests = await feed_message("/progress", course=Course(exercises))

    assert len(requests) == 1
    assert requests[0].text == EN.progress_text.format(
        due=1, new=1, learning=0, mastered=0, total=1
    )


async def test_reflects_journal_breakdown(
    state: FSMContext,
    feed_message: FeedMessage,
) -> None:
    new = make_exercise(topic="warten")
    learning = make_exercise(topic="hoffen")
    mastered = make_exercise(topic="helfen")
    journal = {
        "topic_schedule": {
            "hoffen:government": {
                "interval_days": 30,
                "due_date": (date.today() + timedelta(days=20)).isoformat(),
            },
            "helfen:government": {
                "interval_days": 60,
                "due_date": (date.today() + timedelta(days=60)).isoformat(),
            },
        }
    }
    await state.update_data(journal=journal)

    requests = await feed_message("/progress", course=Course([new, learning, mastered]))

    assert len(requests) == 1
    assert requests[0].text == RU.progress_text.format(
        due=1, new=1, learning=1, mastered=1, total=3
    )
