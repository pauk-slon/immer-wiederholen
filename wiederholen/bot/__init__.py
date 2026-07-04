import dataclasses
import random
from typing import Final, Any

from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from wiederholen.exercises import Exercise, School
from wiederholen.i18n import Language, LANGUAGES
from .l10n import DEFAULT_LANGUAGE, LOCALES

dp: Final = Dispatcher()


class UserState(StatesGroup):
    answering = State()
    recalling = State()


def _get_language(state: dict[str, Any]) -> Language:
    raw_language = state.get("language")
    return raw_language if raw_language in LANGUAGES else DEFAULT_LANGUAGE


def _make_keyboard(exercise: Exercise) -> InlineKeyboardMarkup:
    options = list(exercise.distractors) + [exercise.answer]
    random.shuffle(options)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=opt, callback_data=opt)] for opt in options
        ]
    )


@dp.message(Command("start"))
async def command_start(message: Message, state: FSMContext) -> None:
    language = _get_language(await state.get_data())
    await message.answer(LOCALES[language].start)


@dp.message(Command("language"))
async def command_language(message: Message, state: FSMContext) -> None:
    language = _get_language(await state.get_data())
    new_language = "en" if language == "ru" else "ru"
    await state.update_data(language=new_language)
    await message.answer(LOCALES[new_language].start)


@dp.message(Command("wiederholen"))
async def command_wiederholen(
    message: Message,
    state: FSMContext,
    school: School,
) -> None:
    data = await state.get_data()
    journal = data.get("journal", {})
    teacher = school(journal)
    exercise = teacher.ask()
    await state.set_state(UserState.answering)
    await state.update_data(
        shown_exercise=dataclasses.asdict(exercise),
        journal=journal,
    )
    await message.answer(exercise.question, reply_markup=_make_keyboard(exercise))


@dp.callback_query(UserState.answering)
async def handle_answer(
    callback: CallbackQuery,
    state: FSMContext,
    school: School,
) -> None:
    if callback.data is None:
        await callback.answer()
        return
    state_data = await state.get_data()
    await state.clear()
    language = _get_language(state_data)
    shown_exercise = Exercise(**state_data["shown_exercise"])
    journal = state_data.get("journal", {})
    locale = LOCALES[language]
    explanation = shown_exercise.explanation[language]
    teacher = school(journal)
    if teacher.check_answer(shown_exercise, callback.data):
        text = f"{locale.correct}\n\n{explanation}"
    else:
        text = f"{locale.wrong.format(answer=shown_exercise.answer)}\n\n{explanation}"
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text)
    await callback.answer()
    if shown_exercise.recall and isinstance(callback.message, Message):
        await state.set_state(UserState.recalling)
        await state.update_data(
            language=language,
            journal=journal,
            shown_exercise=state_data["shown_exercise"],
        )
        await callback.message.answer(
            locale.recall_prompt.format(recall=shown_exercise.recall)
        )
    else:
        await state.update_data(language=language, journal=journal)


@dp.message(UserState.recalling)
async def handle_recall(message: Message, state: FSMContext, school: School) -> None:
    state_data = await state.get_data()
    await state.clear()
    language = _get_language(state_data)
    journal = state_data.get("journal", {})
    shown_exercise = Exercise(**state_data["shown_exercise"])
    await state.update_data(language=language, journal=journal)
    locale = LOCALES[language]
    teacher = school(journal)
    if teacher.check_recall(shown_exercise, message.text or ""):
        await message.answer(locale.recall_correct)
    else:
        assert shown_exercise.recall_answer is not None
        await message.answer(
            locale.recall_wrong.format(answer=shown_exercise.recall_answer[0])
        )
