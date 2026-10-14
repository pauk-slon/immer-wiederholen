from aiogram.fsm.context import FSMContext
from aiogram.methods import EditMessageReplyMarkup, EditMessageText
from aiogram.types import InlineKeyboardMarkup

from tests.plugins.aiogram import FeedCallbackQuery, FeedMessage
from wiederholen.bot.commands.topics import TOGGLE_TOPIC_GROUP_PREFIX, TOPICS_DONE
from wiederholen.bot.commands.wiederholen import NEXT_EXERCISE
from wiederholen.bot.l10n import EN, RU
from wiederholen.school import Course
from wiederholen.school.curriculum import TopicGroup


def _course() -> Course:
    return Course(
        [],
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


def _button_texts(markup: InlineKeyboardMarkup) -> list[str]:
    return [button.text for row in markup.inline_keyboard for button in row]


async def test_lists_every_group_unselected_by_default(
    feed_message: FeedMessage,
) -> None:
    requests = await feed_message("/topics", course=_course())

    assert len(requests) == 1
    assert requests[0].text == RU.topics_prompt
    assert _button_texts(requests[0].reply_markup) == [
        "⬜ Формы глаголов",
        "⬜ Падежи",
        RU.btn_topics_done,
    ]


async def test_marks_selected_groups(
    state: FSMContext, feed_message: FeedMessage
) -> None:
    await state.update_data(topic_groups=["cases"], language="en")

    requests = await feed_message("/topics", course=_course())

    assert requests[0].text == EN.topics_prompt
    assert _button_texts(requests[0].reply_markup) == [
        "⬜ Verb forms",
        "✅ Cases",
        EN.btn_topics_done,
    ]


async def test_says_unavailable_when_the_course_has_no_groups(
    feed_message: FeedMessage,
) -> None:
    requests = await feed_message("/topics", course=Course([]))

    assert len(requests) == 1
    assert requests[0].text == RU.topics_unavailable


async def test_clears_a_stale_button_left_from_wiederholen(
    state: FSMContext, feed_message: FeedMessage
) -> None:
    await state.update_data(last_buttoned_message_id=77)

    requests = await feed_message("/topics", course=_course())

    edits = [r for r in requests if isinstance(r, EditMessageReplyMarkup)]
    assert len(edits) == 1
    assert edits[0].message_id == 77


async def test_toggling_a_group_selects_it_and_redraws_the_buttons(
    state: FSMContext, feed_callback_query: FeedCallbackQuery
) -> None:
    requests = await feed_callback_query(
        f"{TOGGLE_TOPIC_GROUP_PREFIX}cases", course=_course()
    )

    assert (await state.get_data())["topic_groups"] == ["cases"]
    edits = [r for r in requests if isinstance(r, EditMessageReplyMarkup)]
    assert len(edits) == 1
    assert _button_texts(edits[0].reply_markup) == [
        "⬜ Формы глаголов",
        "✅ Падежи",
        RU.btn_topics_done,
    ]


async def test_toggling_a_selected_group_deselects_it(
    state: FSMContext, feed_callback_query: FeedCallbackQuery
) -> None:
    await state.update_data(topic_groups=["cases", "verb_forms"])

    await feed_callback_query(f"{TOGGLE_TOPIC_GROUP_PREFIX}cases", course=_course())

    assert (await state.get_data())["topic_groups"] == ["verb_forms"]


async def test_toggling_drops_groups_the_course_no_longer_has(
    state: FSMContext, feed_callback_query: FeedCallbackQuery
) -> None:
    await state.update_data(topic_groups=["removed_group"])

    await feed_callback_query(f"{TOGGLE_TOPIC_GROUP_PREFIX}cases", course=_course())

    assert (await state.get_data())["topic_groups"] == ["cases"]


async def test_toggling_an_unknown_group_selects_nothing(
    state: FSMContext, feed_callback_query: FeedCallbackQuery
) -> None:
    await feed_callback_query(
        f"{TOGGLE_TOPIC_GROUP_PREFIX}removed_group", course=_course()
    )

    assert (await state.get_data())["topic_groups"] == []


async def test_done_summarizes_selected_groups_in_course_order(
    state: FSMContext, feed_callback_query: FeedCallbackQuery
) -> None:
    await state.update_data(topic_groups=["cases", "verb_forms"])

    requests = await feed_callback_query(TOPICS_DONE, course=_course())

    edits = [r for r in requests if isinstance(r, EditMessageText)]
    assert len(edits) == 1
    assert edits[0].text == RU.topics_selected.format(topics="Формы глаголов, Падежи")
    assert [
        button.callback_data
        for row in edits[0].reply_markup.inline_keyboard
        for button in row
    ] == [NEXT_EXERCISE]
    assert (await state.get_data())["last_buttoned_message_id"] is not None


async def test_done_without_a_selection_says_every_topic_is_included(
    feed_callback_query: FeedCallbackQuery,
) -> None:
    requests = await feed_callback_query(TOPICS_DONE, course=_course())

    edits = [r for r in requests if isinstance(r, EditMessageText)]
    assert edits[0].text == RU.topics_all_selected
