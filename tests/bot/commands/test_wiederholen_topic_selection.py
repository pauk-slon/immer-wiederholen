from aiogram.fsm.context import FSMContext

from tests.plugins.aiogram import FeedCallbackQuery, FeedMessage
from tests.plugins.curriculum import make_exercise
from wiederholen.bot.commands.wiederholen import NEXT_EXERCISE, RECALL, UserState
from wiederholen.bot.l10n import RU
from wiederholen.school import Course, Exercise
from wiederholen.school.curriculum import TopicGroup

_PARTIZIP = make_exercise(word="sprechen", topic="partizip_ii")
_CASE = make_exercise(word="helfen", topic="verb_case")


def _course(*exercises: Exercise) -> Course:
    return Course(
        list(exercises),
        topic_groups={
            "verb_forms": TopicGroup(
                title={"ru": "Формы глаголов", "en": "Verb forms"},
                topics=frozenset({"partizip_ii"}),
            ),
            "cases": TopicGroup(
                title={"ru": "Падежи", "en": "Cases"},
                topics=frozenset({"verb_case"}),
            ),
        },
    )


def _sent_texts(requests: list) -> list[str]:
    return [r.text for r in requests if hasattr(r, "text")]


async def test_shows_only_exercises_from_selected_groups(
    state: FSMContext, feed_message: FeedMessage
) -> None:
    await state.update_data(topic_groups=["cases"])

    for _ in range(5):
        await state.set_state(None)
        requests = await feed_message("/wiederholen", course=_course(_PARTIZIP, _CASE))
        assert any(_CASE.question in text for text in _sent_texts(requests))


async def test_without_a_selection_shows_any_group(
    state: FSMContext, feed_message: FeedMessage
) -> None:
    requests = await feed_message("/wiederholen", course=_course(_PARTIZIP))

    assert any(_PARTIZIP.question in text for text in _sent_texts(requests))


async def test_ignores_a_selection_the_course_no_longer_has(
    state: FSMContext, feed_message: FeedMessage
) -> None:
    await state.update_data(topic_groups=["removed_group"])

    requests = await feed_message("/wiederholen", course=_course(_PARTIZIP))

    assert any(_PARTIZIP.question in text for text in _sent_texts(requests))


async def test_says_nothing_due_when_only_unselected_groups_have_exercises(
    state: FSMContext, feed_message: FeedMessage
) -> None:
    await state.update_data(topic_groups=["cases"])

    requests = await feed_message("/wiederholen", course=_course(_PARTIZIP))

    assert RU.nothing_due_text in _sent_texts(requests)


async def test_clicking_next_exercise_respects_the_selection(
    state: FSMContext, feed_callback_query: FeedCallbackQuery
) -> None:
    await state.update_data(topic_groups=["cases"])

    requests = await feed_callback_query(NEXT_EXERCISE, course=_course(_PARTIZIP))

    assert RU.nothing_due_text in _sent_texts(requests)


async def test_selection_survives_answering_an_exercise(
    state: FSMContext, feed_message: FeedMessage
) -> None:
    exercise = make_exercise(recalls=False)
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=exercise.to_dict(), topic_groups=["cases"])

    await feed_message(exercise.answer, course=Course([exercise]))

    assert (await state.get_data())["topic_groups"] == ["cases"]


async def test_selection_survives_a_recall_round_trip(
    state: FSMContext,
    feed_message: FeedMessage,
    feed_callback_query: FeedCallbackQuery,
) -> None:
    exercise = make_exercise(recalls=True)
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=exercise.to_dict(), topic_groups=["cases"])
    await feed_message(exercise.distractors[0], course=Course([exercise]))
    await feed_message("wrong", course=Course([exercise]))

    await feed_callback_query(RECALL, course=Course([exercise]))

    assert (await state.get_data())["topic_groups"] == ["cases"]
