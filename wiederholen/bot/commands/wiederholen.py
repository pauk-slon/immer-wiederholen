import dataclasses
import random
from typing import Final

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from wiederholen.exercises import Exercise, RecallMode, School
from wiederholen.i18n import Language
from wiederholen.bot.l10n import LOCALES, Locale, get_language

router = Router()

NEXT_EXERCISE: Final = "__next__"
RECALL: Final = "__recall__"


class UserState(StatesGroup):
    answering = State()
    recalling = State()


def _make_reply_keyboard(exercise: Exercise) -> ReplyKeyboardMarkup:
    options = list(exercise.distractors) + [exercise.answer]
    random.shuffle(options)
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=opt)] for opt in options],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _make_next_button(locale: Locale) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=locale.cmd_wiederholen,
                    callback_data=NEXT_EXERCISE,
                )
            ]
        ]
    )


def _make_recall_buttons(locale: Locale) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=locale.btn_recall, callback_data=RECALL),
                InlineKeyboardButton(
                    text=locale.cmd_wiederholen,
                    callback_data=NEXT_EXERCISE,
                ),
            ]
        ]
    )


async def _start_recall(
    state: FSMContext,
    language: Language,
    journal: dict,
    shown_exercise_dict: dict,
    shown_exercise: Exercise,
    message: Message,
    locale: Locale,
) -> None:
    assert shown_exercise.recall is not None
    await state.set_state(UserState.recalling)
    await state.update_data(
        language=language,
        journal=journal,
        shown_exercise=shown_exercise_dict,
    )
    hint = (
        shown_exercise.recall.hint.get(language) if shown_exercise.recall.hint else None
    )
    recall_text = locale.recall_prompt.format(recall=shown_exercise.recall.question)
    if hint:
        await message.answer(f"{recall_text}\n<i>{hint}</i>", parse_mode="HTML")
    else:
        await message.answer(recall_text)


def _format_question(exercise: Exercise) -> str:
    return f"❓ {exercise.question}"


def _show_exercise_kwargs(exercise: Exercise) -> dict:
    if exercise.distractors:
        return {"reply_markup": _make_reply_keyboard(exercise)}
    return {"reply_markup": ReplyKeyboardRemove()}


@router.message(Command("wiederholen"))
async def command_wiederholen(
    message: Message,
    state: FSMContext,
    school: School,
) -> None:
    data = await state.get_data()
    journal = data.get("journal", {})
    teacher = school(journal)
    exercise = teacher.next_exercise()
    await state.set_state(UserState.answering)
    await state.update_data(
        shown_exercise=dataclasses.asdict(exercise),
        journal=journal,
    )
    await message.answer(_format_question(exercise), **_show_exercise_kwargs(exercise))


@router.message(UserState.answering)
async def handle_answer(
    message: Message,
    state: FSMContext,
    school: School,
) -> None:
    state_data = await state.get_data()
    await state.clear()
    language = get_language(state_data)
    shown_exercise = Exercise.from_dict(state_data["shown_exercise"])
    journal = state_data.get("journal", {})
    locale = LOCALES[language]
    explanation = shown_exercise.explanation[language]
    teacher = school(journal)
    mark = teacher.check_answer(shown_exercise, message.text or "")
    result_line = (
        locale.correct
        if mark.correct
        else locale.wrong.format(answer=shown_exercise.answer)
    )
    if mark.recall == RecallMode.optional:
        reply_markup = _make_recall_buttons(locale)
    elif mark.recall == RecallMode.none:
        reply_markup = _make_next_button(locale)
    else:
        reply_markup = None
    first_reply_markup = ReplyKeyboardRemove() if shown_exercise.distractors else None
    await message.answer(result_line, reply_markup=first_reply_markup)
    await message.answer(explanation, reply_markup=reply_markup)
    if mark.recall == RecallMode.required:
        await _start_recall(
            state,
            language,
            journal,
            state_data["shown_exercise"],
            shown_exercise,
            message,
            locale,
        )
    else:
        await state.update_data(
            language=language,
            journal=journal,
            shown_exercise=state_data["shown_exercise"],
        )


@router.message(UserState.recalling)
async def handle_recall(message: Message, state: FSMContext, school: School) -> None:
    state_data = await state.get_data()
    await state.clear()
    language = get_language(state_data)
    journal = state_data.get("journal", {})
    shown_exercise = Exercise.from_dict(state_data["shown_exercise"])
    await state.update_data(language=language, journal=journal)
    locale = LOCALES[language]
    teacher = school(journal)
    next_button = _make_next_button(locale)
    if teacher.check_recall(shown_exercise, message.text or ""):
        await message.answer(locale.recall_correct, reply_markup=next_button)
    else:
        assert shown_exercise.recall is not None
        await message.answer(
            locale.recall_wrong.format(answer=shown_exercise.recall.answer[0]),
            reply_markup=next_button,
        )


@router.callback_query(F.data == NEXT_EXERCISE)
async def handle_next_exercise(
    callback: CallbackQuery,
    state: FSMContext,
    school: School,
) -> None:
    state_data = await state.get_data()
    journal = state_data.get("journal", {})
    teacher = school(journal)
    exercise = teacher.next_exercise()
    await state.set_state(UserState.answering)
    await state.update_data(
        shown_exercise=dataclasses.asdict(exercise), journal=journal
    )
    if isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            _format_question(exercise), **_show_exercise_kwargs(exercise)
        )
    await callback.answer()


@router.callback_query(F.data == RECALL)
async def handle_recall_request(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    state_data = await state.get_data()
    language = get_language(state_data)
    journal = state_data.get("journal", {})
    shown_exercise = Exercise.from_dict(state_data["shown_exercise"])
    locale = LOCALES[language]
    if isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(reply_markup=None)
        await _start_recall(
            state,
            language,
            journal,
            state_data["shown_exercise"],
            shown_exercise,
            callback.message,
            locale,
        )
    await callback.answer()
