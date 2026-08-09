import difflib
import html
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
from opentelemetry import trace

from wiederholen.bot.feature_flags import has_feature
from wiederholen.bot.l10n import LOCALES, Locale, get_language
from wiederholen.bot.pending_buttons import (
    clear_stale_buttons,
    forget_buttoned_message,
    remember_buttoned_message,
)
from wiederholen.bot.tracing import record_tutoring_events
from wiederholen.i18n import Language
from wiederholen.tutoring import Course, Exercise, Recall, RecallMode, Tutor

router = Router()

NEXT_EXERCISE: Final = "__next__"
RECALL: Final = "__recall__"
STUDY_MORE: Final = "__study_more__"


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


def _make_study_more_button(locale: Locale) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=locale.btn_study_more,
                    callback_data=STUDY_MORE,
                )
            ]
        ]
    )


def _make_recall_buttons(locale: Locale, label: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=label, callback_data=RECALL),
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
    course: Course,
) -> None:
    tutor = Tutor(course, journal)
    recall = tutor.request_recall(shown_exercise)
    await state.set_state(UserState.recalling)
    await state.update_data(
        language=language,
        journal=journal,
        shown_exercise=shown_exercise_dict,
        shown_recall=recall.to_dict(),
    )
    hint = recall.hint.get(language) if recall.hint else None
    recall_text = locale.recall_prompt.format(recall=recall.question)
    if hint:
        await message.answer(f"{recall_text}\n<i>{hint}</i>", parse_mode="HTML")
    else:
        await message.answer(recall_text)


def _format_question(exercise: Exercise, language: Language, course: Course) -> str:
    text = f"❓ {exercise.question}"
    if exercise.description:
        text += f"\n💭 {exercise.description[language]}"
    instruction = course.topic_instructions.get(exercise.topic, {}).get(language)
    if instruction:
        text += f"\nℹ️ {instruction}"
    return text


def _highlight_diff(user_text: str, correct_text: str) -> str:
    matcher = difflib.SequenceMatcher(a=user_text, b=correct_text)
    correct_parts: list[str] = []
    for tag, _, _, j1, j2 in matcher.get_opcodes():
        correct_chunk = html.escape(correct_text[j1:j2])
        if tag == "equal":
            correct_parts.append(correct_chunk)
        elif correct_chunk:
            correct_parts.append(f"<u>{correct_chunk}</u>")
    return "".join(correct_parts)


def _show_exercise_kwargs(exercise: Exercise) -> dict:
    if exercise.distractors:
        return {"reply_markup": _make_reply_keyboard(exercise)}
    return {"reply_markup": ReplyKeyboardRemove()}


@router.message(Command("wiederholen"))
async def command_wiederholen(
    message: Message,
    state: FSMContext,
    course: Course,
    feature_flags: dict[str, frozenset[int]] | None = None,
) -> None:
    await clear_stale_buttons(message, state)
    # An example check point for #121's flag mechanism — no visible effect
    # yet, just a span attribute for whoever's testing the flag right now.
    if has_feature(feature_flags or {}, "ai_exercises", message.chat.id):
        trace.get_current_span().set_attribute("feature.ai_exercises", True)
    data = await state.get_data()
    language = get_language(data)
    journal = data.get("journal", {})
    locale = LOCALES[language]
    tutor = Tutor(course, journal)
    exercise, events = tutor.next_exercise()
    record_tutoring_events(events)
    if exercise is None:
        await state.update_data(journal=journal)
        sent = await message.answer(
            locale.nothing_due_text, reply_markup=_make_study_more_button(locale)
        )
        await remember_buttoned_message(state, sent)
        return
    await state.set_state(UserState.answering)
    await state.update_data(
        shown_exercise=exercise.to_dict(),
        journal=journal,
    )
    question_text = _format_question(exercise, language, course)
    await message.answer(question_text, **_show_exercise_kwargs(exercise))


@router.message(UserState.answering)
async def handle_answer(
    message: Message,
    state: FSMContext,
    course: Course,
) -> None:
    state_data = await state.get_data()
    await state.clear()
    language = get_language(state_data)
    shown_exercise = Exercise.from_dict(state_data["shown_exercise"])
    journal = state_data.get("journal", {})
    locale = LOCALES[language]
    explanation = shown_exercise.explanation[language]
    tutor = Tutor(course, journal)
    mark, events = tutor.check_answer(shown_exercise, message.text or "")
    record_tutoring_events(events)
    result_line = (
        locale.correct
        if mark.is_correct
        else locale.wrong.format(answer=shown_exercise.answer)
    )
    if mark.recall == RecallMode.optional:
        reply_markup = _make_recall_buttons(locale, locale.btn_recall)
    elif mark.recall == RecallMode.none:
        reply_markup = _make_next_button(locale)
    else:
        reply_markup = None
    first_reply_markup = ReplyKeyboardRemove() if shown_exercise.distractors else None
    await message.answer(result_line, reply_markup=first_reply_markup)
    sent_explanation = await message.answer(explanation, reply_markup=reply_markup)
    if mark.recall == RecallMode.required:
        await _start_recall(
            state,
            language,
            journal,
            state_data["shown_exercise"],
            shown_exercise,
            message,
            locale,
            course,
        )
    else:
        await state.update_data(
            language=language,
            journal=journal,
            shown_exercise=state_data["shown_exercise"],
        )
        if reply_markup is not None:
            await remember_buttoned_message(state, sent_explanation)


@router.message(UserState.recalling)
async def handle_recall(message: Message, state: FSMContext, course: Course) -> None:
    state_data = await state.get_data()
    await state.clear()
    language = get_language(state_data)
    journal = state_data.get("journal", {})
    shown_recall = Recall.from_dict(state_data["shown_recall"])
    await state.update_data(
        language=language,
        journal=journal,
        shown_exercise=state_data["shown_exercise"],
        shown_recall=state_data["shown_recall"],
    )
    locale = LOCALES[language]
    tutor = Tutor(course, journal)
    if tutor.check_recall(shown_recall, message.text or ""):
        sent = await message.answer(
            locale.recall_correct,
            reply_markup=_make_next_button(locale),
        )
    else:
        correct_answer = _highlight_diff(message.text or "", shown_recall.answer[0])
        sent = await message.answer(
            locale.recall_wrong.format(answer=correct_answer),
            reply_markup=_make_recall_buttons(locale, locale.btn_recall_retry),
            parse_mode="HTML",
        )
    await remember_buttoned_message(state, sent)


async def _respond_with_next_exercise(
    callback: CallbackQuery,
    state: FSMContext,
    course: Course,
    tutor: Tutor,
    journal: dict,
    language: Language,
    locale: Locale,
) -> None:
    exercise, events = tutor.next_exercise()
    record_tutoring_events(events)
    if exercise is None:
        await state.update_data(journal=journal)
        if isinstance(callback.message, Message):
            await callback.message.edit_reply_markup(reply_markup=None)
            sent = await callback.message.answer(
                locale.nothing_due_text, reply_markup=_make_study_more_button(locale)
            )
            await remember_buttoned_message(state, sent)
        await callback.answer()
        return
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=exercise.to_dict(), journal=journal)
    if isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(reply_markup=None)
        await forget_buttoned_message(state)
        question_text = _format_question(exercise, language, course)
        await callback.message.answer(question_text, **_show_exercise_kwargs(exercise))
    await callback.answer()


@router.callback_query(F.data == NEXT_EXERCISE)
async def handle_next_exercise(
    callback: CallbackQuery,
    state: FSMContext,
    course: Course,
) -> None:
    state_data = await state.get_data()
    language = get_language(state_data)
    journal = state_data.get("journal", {})
    locale = LOCALES[language]
    tutor = Tutor(course, journal)
    await _respond_with_next_exercise(
        callback, state, course, tutor, journal, language, locale
    )


@router.callback_query(F.data == STUDY_MORE)
async def handle_study_more(
    callback: CallbackQuery,
    state: FSMContext,
    course: Course,
) -> None:
    state_data = await state.get_data()
    language = get_language(state_data)
    journal = state_data.get("journal", {})
    locale = LOCALES[language]
    tutor = Tutor(course, journal)
    tutor.grant_new_word_budget()
    await _respond_with_next_exercise(
        callback, state, course, tutor, journal, language, locale
    )


@router.callback_query(F.data == RECALL)
async def handle_recall_request(
    callback: CallbackQuery,
    state: FSMContext,
    course: Course,
) -> None:
    state_data = await state.get_data()
    language = get_language(state_data)
    journal = state_data.get("journal", {})
    shown_exercise = Exercise.from_dict(state_data["shown_exercise"])
    locale = LOCALES[language]
    if isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(reply_markup=None)
        await forget_buttoned_message(state)
        await _start_recall(
            state,
            language,
            journal,
            state_data["shown_exercise"],
            shown_exercise,
            callback.message,
            locale,
            course,
        )
    await callback.answer()
