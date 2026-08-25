import asyncio
import contextlib
import difflib
import html
import random
from collections.abc import AsyncIterator
from typing import Final

from aiogram import Bot, F, Router
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
from anthropic import AsyncAnthropic
from opentelemetry import trace

from wiederholen.bot.feature_flags import has_feature
from wiederholen.bot.l10n import LOCALES, Locale, get_language
from wiederholen.bot.pending_buttons import (
    clear_stale_buttons,
    forget_buttoned_message,
    remember_buttoned_message,
)
from wiederholen.bot.telegram_student_id import TelegramStudentID
from wiederholen.school import (
    AIGenerationError,
    Course,
    Exercise,
    Language,
    Recall,
    RecallMode,
    StudentRecordBook,
    Tutor,
    generate_shadow_exercise,
    shuffle_word_bank,
)

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


def make_next_button(locale: Locale) -> InlineKeyboardMarkup:
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
    student_record: dict,
    shown_exercise_dict: dict,
    shown_exercise: Exercise,
    message: Message,
    locale: Locale,
    course: Course,
    *,
    ai_mode: bool,
) -> None:
    # student_record is mutated in place; whichever student_record_book.check_out() the
    # caller opened it under persists it on exit — this function itself
    # never touches the store.
    tutor = Tutor(course, student_record)
    recall = tutor.request_recall(shown_exercise)
    await state.set_state(UserState.recalling)
    await state.update_data(
        language=language,
        shown_exercise=shown_exercise_dict,
        shown_recall=recall.to_dict(),
        ai_mode=ai_mode,
    )
    hint = recall.hint.get(language) if recall.hint else None
    recall_text = locale.recall_prompt.format(recall=recall.question)
    if hint:
        await message.answer(f"{recall_text}\n<i>{hint}</i>", parse_mode="HTML")
    else:
        await message.answer(recall_text)


def _format_question(
    exercise: Exercise,
    language: Language,
    course: Course,
    *,
    is_ai_generated: bool = False,
) -> str:
    prefix = "🤖 " if is_ai_generated else ""
    text = f"{prefix}❓ {exercise.question}"
    if exercise.word_bank:
        # Reconstructs exactly the shape question's own hand-written
        # parenthetical hint used to have (see issue #191) — just shuffled
        # fresh on every render instead of frozen once at authoring time,
        # same as the web widget's own tile UI shuffles its copy.
        text += f" ({' / '.join(shuffle_word_bank(exercise.word_bank))})"
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


_TYPING_INTERVAL_SECONDS: Final = 4  # Telegram's own indicator lasts ~5s


@contextlib.asynccontextmanager
async def _show_typing_while(bot: Bot, chat_id: int) -> AsyncIterator[None]:
    # Telegram's "typing..." indicator auto-expires after ~5s (or once a
    # message is sent) — full shadow-exercise generation (question, answer,
    # distractors, explanation, recalls, all written fresh — see
    # wiederholen.school.authoring) can easily run past that, so a
    # single one-shot call wouldn't stay visible for the whole wait. Refresh
    # it on a loop in the background instead, cancelled once generation
    # finishes either way (success or AIGenerationError).
    async def _pulse() -> None:
        while True:
            await bot.send_chat_action(chat_id, "typing")
            await asyncio.sleep(_TYPING_INTERVAL_SECONDS)

    task = asyncio.create_task(_pulse())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


async def _apply_ai_mode(
    exercise: Exercise,
    *,
    ai_mode: bool,
    anthropic_client: AsyncAnthropic | None,
    course: Course,
    authoring_guide: str | None,
    bot: Bot | None,
    chat_id: int | None,
) -> Exercise | None:
    # None means "AI mode is on but generation failed" — distinct from
    # ai_mode being off, in which case the original exercise passes through
    # untouched. The caller shows locale.ai_generation_failed on None rather
    # than falling back to the real exercise, so a tester notices generation
    # is broken instead of unknowingly seeing human-authored questions.
    if not ai_mode:
        return exercise
    if anthropic_client is None:
        return None
    # bot/chat_id are None only for _respond_with_next_exercise's
    # inaccessible-message edge case (see its own isinstance(..., Message)
    # guards) — generation still runs, there's just nowhere left to show a
    # typing indicator, so fall back to a no-op context instead of skipping
    # generation itself.
    typing_indicator = (
        _show_typing_while(bot, chat_id)
        if bot is not None and chat_id is not None
        else contextlib.nullcontext()
    )
    try:
        async with typing_indicator:
            return await generate_shadow_exercise(
                anthropic_client, exercise, course, authoring_guide=authoring_guide
            )
    except AIGenerationError:
        return None


@router.message(Command("wiederholen"))
async def command_wiederholen(
    message: Message,
    state: FSMContext,
    course: Course,
    student_record_book: StudentRecordBook,
    feature_flags: dict[str, frozenset[int]] | None = None,
    anthropic_client: AsyncAnthropic | None = None,
    authoring_guide: str | None = None,
) -> None:
    await clear_stale_buttons(message, state)
    # An example check point for #121's flag mechanism — no visible effect
    # yet, just a span attribute for whoever's testing the flag right now.
    if has_feature(feature_flags or {}, "ai_exercises", message.chat.id):
        trace.get_current_span().set_attribute("feature.ai_exercises", True)
    data = await state.get_data()
    language = get_language(data)
    locale = LOCALES[language]
    async with student_record_book.check_out(
        TelegramStudentID.encode(message.chat.id)
    ) as student_record:
        tutor = Tutor(course, student_record)
        exercise = tutor.next_exercise()
        if exercise is None:
            sent = await message.answer(
                locale.nothing_due_text, reply_markup=_make_study_more_button(locale)
            )
            await remember_buttoned_message(state, sent)
            return
        # Only apply for topics the content repo has explicitly opted in via
        # topics.yaml's ai_generation flag (see Course.ai_generatable_topics)
        # — for topics where the question's exact wording encodes part of
        # the answer (word banks, fixed "verb → form" templates,
        # subject-dependent conjugation), a rewritten question can silently
        # stop matching the untouched answer.
        ai_mode = bool(data.get("ai_mode", False)) and (
            exercise.topic in course.ai_generatable_topics
        )
        bot = message.bot
        assert bot is not None
        exercise = await _apply_ai_mode(
            exercise,
            ai_mode=ai_mode,
            anthropic_client=anthropic_client,
            course=course,
            authoring_guide=authoring_guide,
            bot=bot,
            chat_id=message.chat.id,
        )
        if exercise is None:
            await message.answer(locale.ai_generation_failed)
            return
        await state.set_state(UserState.answering)
        await state.update_data(shown_exercise=exercise.to_dict())
        question_text = _format_question(
            exercise, language, course, is_ai_generated=ai_mode
        )
        await message.answer(question_text, **_show_exercise_kwargs(exercise))


@router.message(UserState.answering)
async def handle_answer(
    message: Message,
    state: FSMContext,
    course: Course,
    student_record_book: StudentRecordBook,
) -> None:
    state_data = await state.get_data()
    ai_mode = state_data.get("ai_mode", False)
    await state.clear()
    language = get_language(state_data)
    shown_exercise = Exercise.from_dict(state_data["shown_exercise"])
    locale = LOCALES[language]
    explanation = shown_exercise.explanation[language]
    async with student_record_book.check_out(
        TelegramStudentID.encode(message.chat.id)
    ) as student_record:
        tutor = Tutor(course, student_record)
        mark = tutor.check_answer(shown_exercise, message.text or "")
        result_line = (
            locale.correct
            if mark.is_correct
            else locale.wrong.format(answer=shown_exercise.answer)
        )
        if mark.recall == RecallMode.optional:
            reply_markup = _make_recall_buttons(locale, locale.btn_recall)
        elif mark.recall == RecallMode.none:
            reply_markup = make_next_button(locale)
        else:
            reply_markup = None
        first_reply_markup = (
            ReplyKeyboardRemove() if shown_exercise.distractors else None
        )
        await message.answer(result_line, reply_markup=first_reply_markup)
        sent_explanation = await message.answer(explanation, reply_markup=reply_markup)
        if mark.recall == RecallMode.required:
            await _start_recall(
                state,
                language,
                student_record,
                state_data["shown_exercise"],
                shown_exercise,
                message,
                locale,
                course,
                ai_mode=ai_mode,
            )
        else:
            await state.update_data(
                language=language,
                shown_exercise=state_data["shown_exercise"],
                ai_mode=ai_mode,
            )
            if reply_markup is not None:
                await remember_buttoned_message(state, sent_explanation)


@router.message(UserState.recalling)
async def handle_recall(
    message: Message,
    state: FSMContext,
    course: Course,
    student_record_book: StudentRecordBook,
) -> None:
    state_data = await state.get_data()
    ai_mode = state_data.get("ai_mode", False)
    await state.clear()
    language = get_language(state_data)
    shown_recall = Recall.from_dict(state_data["shown_recall"])
    await state.update_data(
        language=language,
        shown_exercise=state_data["shown_exercise"],
        shown_recall=state_data["shown_recall"],
        ai_mode=ai_mode,
    )
    locale = LOCALES[language]
    # check_recall() is pure (never mutates student_record), unlike request_recall()
    # in _start_recall() above — open() detects that nothing changed and
    # skips the write on its own, no separate read-only path needed here.
    async with student_record_book.check_out(
        TelegramStudentID.encode(message.chat.id)
    ) as student_record:
        tutor = Tutor(course, student_record)
        if tutor.check_recall(shown_recall, message.text or ""):
            sent = await message.answer(
                locale.recall_correct,
                reply_markup=make_next_button(locale),
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
    language: Language,
    locale: Locale,
    *,
    ai_mode: bool,
    anthropic_client: AsyncAnthropic | None,
    authoring_guide: str | None,
) -> None:
    # tutor already wraps the student_record its caller opened via
    # student_record_book.check_out() — this function only ever mutates through
    # tutor, so it never needs the store itself.
    exercise = tutor.next_exercise()
    if exercise is None:
        if isinstance(callback.message, Message):
            await callback.message.edit_reply_markup(reply_markup=None)
            sent = await callback.message.answer(
                locale.nothing_due_text, reply_markup=_make_study_more_button(locale)
            )
            await remember_buttoned_message(state, sent)
        await callback.answer()
        return
    # See command_wiederholen's own version of this check for why it's
    # per-topic, not just the raw ai_mode toggle.
    ai_mode = ai_mode and exercise.topic in course.ai_generatable_topics
    # None (rather than message.bot/message.chat.id) for the rare
    # inaccessible-message case — same isinstance(..., Message) guard the
    # rest of this function already uses below; _apply_ai_mode() still runs
    # generation either way, it just has nowhere left to show typing.
    has_accessible_message = isinstance(callback.message, Message)
    exercise = await _apply_ai_mode(
        exercise,
        ai_mode=ai_mode,
        anthropic_client=anthropic_client,
        course=course,
        authoring_guide=authoring_guide,
        bot=callback.bot if has_accessible_message else None,
        chat_id=callback.message.chat.id if has_accessible_message else None,
    )
    if exercise is None:
        if isinstance(callback.message, Message):
            await callback.message.edit_reply_markup(reply_markup=None)
            await forget_buttoned_message(state)
            await callback.message.answer(locale.ai_generation_failed)
        await callback.answer()
        return
    await state.set_state(UserState.answering)
    await state.update_data(shown_exercise=exercise.to_dict())
    if isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(reply_markup=None)
        await forget_buttoned_message(state)
        question_text = _format_question(
            exercise, language, course, is_ai_generated=ai_mode
        )
        await callback.message.answer(question_text, **_show_exercise_kwargs(exercise))
    await callback.answer()


@router.callback_query(F.data == NEXT_EXERCISE)
async def handle_next_exercise(
    callback: CallbackQuery,
    state: FSMContext,
    course: Course,
    student_record_book: StudentRecordBook,
    anthropic_client: AsyncAnthropic | None = None,
    authoring_guide: str | None = None,
) -> None:
    state_data = await state.get_data()
    language = get_language(state_data)
    locale = LOCALES[language]
    async with student_record_book.check_out(
        TelegramStudentID.encode(callback.from_user.id)
    ) as student_record:
        tutor = Tutor(course, student_record)
        await _respond_with_next_exercise(
            callback,
            state,
            course,
            tutor,
            language,
            locale,
            ai_mode=state_data.get("ai_mode", False),
            anthropic_client=anthropic_client,
            authoring_guide=authoring_guide,
        )


@router.callback_query(F.data == STUDY_MORE)
async def handle_study_more(
    callback: CallbackQuery,
    state: FSMContext,
    course: Course,
    student_record_book: StudentRecordBook,
    anthropic_client: AsyncAnthropic | None = None,
    authoring_guide: str | None = None,
) -> None:
    state_data = await state.get_data()
    language = get_language(state_data)
    locale = LOCALES[language]
    async with student_record_book.check_out(
        TelegramStudentID.encode(callback.from_user.id)
    ) as student_record:
        tutor = Tutor(course, student_record)
        tutor.grant_new_word_budget()
        await _respond_with_next_exercise(
            callback,
            state,
            course,
            tutor,
            language,
            locale,
            ai_mode=state_data.get("ai_mode", False),
            anthropic_client=anthropic_client,
            authoring_guide=authoring_guide,
        )


@router.callback_query(F.data == RECALL)
async def handle_recall_request(
    callback: CallbackQuery,
    state: FSMContext,
    course: Course,
    student_record_book: StudentRecordBook,
) -> None:
    state_data = await state.get_data()
    language = get_language(state_data)
    shown_exercise = Exercise.from_dict(state_data["shown_exercise"])
    locale = LOCALES[language]
    if isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(reply_markup=None)
        await forget_buttoned_message(state)
        async with student_record_book.check_out(
            TelegramStudentID.encode(callback.from_user.id)
        ) as student_record:
            await _start_recall(
                state,
                language,
                student_record,
                state_data["shown_exercise"],
                shown_exercise,
                callback.message,
                locale,
                course,
                ai_mode=state_data.get("ai_mode", False),
            )
    await callback.answer()
