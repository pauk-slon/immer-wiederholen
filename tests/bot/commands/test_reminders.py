from aiogram.fsm.context import FSMContext
from aiogram.methods import EditMessageReplyMarkup, EditMessageText
from aiogram.types import InlineKeyboardMarkup

from tests.plugins.aiogram import FeedCallbackQuery, FeedMessage
from tests.plugins.curriculum import make_exercise
from wiederholen.bot.commands.reminders import SET_REMIND_AFTER_PREFIX
from wiederholen.bot.commands.wiederholen import NEXT_EXERCISE, UserState
from wiederholen.bot.l10n import EN, RU
from wiederholen.school import Course


def _button_texts(markup: InlineKeyboardMarkup) -> list[str]:
    return [button.text for row in markup.inline_keyboard for button in row]


async def test_marks_the_default_interval_when_never_chosen(
    feed_message: FeedMessage,
) -> None:
    requests = await feed_message("/reminders")

    assert len(requests) == 1
    assert requests[0].text == RU.reminders_prompt
    assert _button_texts(requests[0].reply_markup) == [
        "4 ч",
        "8 ч",
        "12 ч",
        "✅ 24 ч",
        RU.btn_reminders_off,
    ]


async def test_marks_the_chosen_option(
    state: FSMContext, feed_message: FeedMessage
) -> None:
    await state.update_data(remind_after_hours=0, language="en")

    requests = await feed_message("/reminders")

    assert requests[0].text == EN.reminders_prompt
    assert _button_texts(requests[0].reply_markup) == [
        "4 h",
        "8 h",
        "12 h",
        "24 h",
        f"✅ {EN.btn_reminders_off}",
    ]


async def test_clears_a_stale_button_left_from_wiederholen(
    state: FSMContext, feed_message: FeedMessage
) -> None:
    await state.update_data(last_buttoned_message_id=77)

    requests = await feed_message("/reminders")

    edits = [r for r in requests if isinstance(r, EditMessageReplyMarkup)]
    assert len(edits) == 1
    assert edits[0].message_id == 77


async def test_choosing_an_interval_saves_it_and_confirms(
    state: FSMContext, feed_callback_query: FeedCallbackQuery
) -> None:
    requests = await feed_callback_query(f"{SET_REMIND_AFTER_PREFIX}8")

    assert (await state.get_data())["remind_after_hours"] == 8
    edits = [r for r in requests if isinstance(r, EditMessageText)]
    assert len(edits) == 1
    assert edits[0].text == RU.reminders_set.format(hours=8)
    assert edits[0].reply_markup.inline_keyboard[0][0].callback_data == NEXT_EXERCISE


async def test_turning_reminders_off_confirms_it(
    state: FSMContext, feed_callback_query: FeedCallbackQuery
) -> None:
    requests = await feed_callback_query(f"{SET_REMIND_AFTER_PREFIX}0")

    assert (await state.get_data())["remind_after_hours"] == 0
    edits = [r for r in requests if isinstance(r, EditMessageText)]
    assert edits[0].text == RU.reminders_off


async def test_choice_survives_answering_an_exercise(
    state: FSMContext, feed_message: FeedMessage
) -> None:
    exercise = make_exercise(recalls=False)
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=exercise.to_dict(), remind_after_hours=4)

    await feed_message(exercise.answer, course=Course([exercise]))

    assert (await state.get_data())["remind_after_hours"] == 4
