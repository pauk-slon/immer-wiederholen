from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove

from wiederholen.bot.commands.wiederholen import UserState
from wiederholen.bot.l10n import EN, RU
from wiederholen.exercises import Exercise, Course

from tests.plugins.aiogram import FeedMessage
from tests.plugins.exercises import make_exercise


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
    expected = RU.description_prompt.format(description="Поезд едет через туннель.")
    assert expected in requests[0].text


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
    expected = EN.description_prompt.format(
        description="The train goes through the tunnel."
    )
    assert expected in requests[0].text


async def test_avoids_repeating_previously_shown_question(
    state: FSMContext,
    feed_message: FeedMessage,
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
    await state.update_data(journal={"last_answered_question": mit.question})

    requests = await feed_message("/wiederholen", course=Course([mit, ueber]))

    assert len(requests) == 1
    assert ueber.question in requests[0].text
