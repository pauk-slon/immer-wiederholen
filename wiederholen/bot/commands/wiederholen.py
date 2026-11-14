import asyncio
import contextlib
import difflib
import html
import logging
import random
from collections.abc import AsyncGenerator
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
from wiederholen.bot.l10n import (
    LOCALES,
    Locale,
    append_streak_line,
    format_count,
    get_language,
)
from wiederholen.bot.pending_buttons import (
    clear_stale_buttons,
    forget_buttoned_message,
    remember_buttoned_message,
)
from wiederholen.bot.topic_selection import restrict_to_selected_groups
from wiederholen.school import (
    AIGenerationError,
    Course,
    CueStore,
    Exercise,
    Language,
    Mark,
    Recall,
    RecallMode,
    StudentIdentityStore,
    StudentRecordBook,
    Tutor,
    generate_shadow_exercise,
    shuffle_word_bank,
)

logger = logging.getLogger(__name__)

router = Router()

NEXT_EXERCISE: Final = "__next__"
RECALL: Final = "__recall__"
STUDY_MORE: Final = "__study_more__"

# Telegram's own limit for a photo's caption — well below the 4096 a plain
# text message gets. A question long enough to exceed it (word_bank's own
# parenthetical, description, instruction all appended — see
# _format_question()) falls back to a plain text message instead of a
# truncated caption; see _answer_with_optional_cue().
_PHOTO_CAPTION_LIMIT: Final = 1024

# The lesson size for chats with the lessons flag (#325). Other chats and
# the web app keep Tutor.LESSON_SIZE, so only these chats get lessons of
# more than one exercise, with a counter and a summary
_FLAGGED_LESSON_SIZE: Final = 5


class UserState(StatesGroup):
    answering = State()
    recalling = State()


# Lasting chat state living in FSM data alongside exercise state — it
# must outlive the state.clear() that ends each exercise, or e.g. AI mode
# silently reverts to off after one answer.
_LASTING_CHAT_STATE_KEYS: Final = (
    "language",
    "ai_mode",
    "topic_groups",
    "remind_after_hours",
    # Not a setting: the lesson lasts for several exercises (see
    # wiederholen.school.tutoring.lesson)
    "lesson",
)


async def _clear_exercise_state(state: FSMContext, state_data: dict) -> None:
    await state.clear()
    await state.update_data(
        {key: state_data[key] for key in _LASTING_CHAT_STATE_KEYS if key in state_data}
    )


def _make_reply_keyboard(exercise: Exercise, course: Course) -> ReplyKeyboardMarkup:
    options = [*exercise.distractors, *course.shown_answers(exercise)]
    random.shuffle(options)
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=opt)] for opt in options],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def make_next_button(locale: Locale, label: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=label or locale.cmd_wiederholen,
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


def _format_nothing_due(tutor: Tutor, language: Language) -> str:
    locale = LOCALES[language]
    return append_streak_line(
        locale.nothing_due_text, tutor.streak(), language, locale.streak_text
    )


def _make_recall_buttons(
    locale: Locale, label: str, next_label: str | None = None
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=label, callback_data=RECALL),
                InlineKeyboardButton(
                    text=next_label or locale.cmd_wiederholen,
                    callback_data=NEXT_EXERCISE,
                ),
            ]
        ]
    )


def _lesson_size(feature_flags: dict[str, frozenset[int]] | None, chat_id: int) -> int:
    if has_feature(feature_flags or {}, "lessons", chat_id):
        return _FLAGGED_LESSON_SIZE
    return Tutor.LESSON_SIZE


def _get_lesson_counter(tutor: Tutor) -> list[int] | None:
    # [position, size] for the question's "3/5", only in a lesson of
    # several exercises
    progress = tutor.lesson_progress()
    if progress is None or progress.size < 2:
        return None
    return [progress.position, progress.size]


def _get_finished_lesson(tutor: Tutor, mark: Mark) -> dict | None:
    # Kept as exercise state until the "N more" button comes, which can be
    # after a recall. Only a lesson of several exercises gets a summary
    finished_lesson = mark.finished_lesson
    if finished_lesson is None or finished_lesson.size < 2:
        return None
    streak = tutor.streak() if finished_lesson.extends_streak else None
    return {
        "size": finished_lesson.size,
        "correct": finished_lesson.correct,
        "streak_days": streak.days if streak is not None else None,
    }


def _append_lesson_summary(
    text: str, finished_lesson: dict | None, language: Language
) -> str:
    if finished_lesson is None:
        return text
    locale = LOCALES[language]
    summary = locale.lesson_summary.format(
        correct=finished_lesson["correct"], size=finished_lesson["size"]
    )
    if finished_lesson["streak_days"] is not None:
        days = format_count(finished_lesson["streak_days"], "days", language)
        summary += "\n" + locale.streak_text.format(days=days)
    return f"{text}\n\n{summary}"


def _get_next_label(finished_lesson: dict | None, language: Language) -> str | None:
    # After a lesson, the "Next" button starts the next lesson. Only a
    # flagged chat has a finished_lesson, so its size is the flagged one
    if finished_lesson is None:
        return None
    count = format_count(_FLAGGED_LESSON_SIZE, "exercises", language)
    return LOCALES[language].btn_more_exercises.format(count=count)


async def _start_recall(
    state: FSMContext,
    language: Language,
    student_record: dict,
    shown_exercise_dict: dict,
    shown_exercise: Exercise,
    message: Message,
    locale: Locale,
    course: Course,
) -> None:
    # student_record is mutated in place; whichever student_record_book.check_out() the
    # caller opened it under persists it on exit — this function itself
    # never touches the store.
    tutor = Tutor(course, student_record)
    recall = tutor.request_recall(shown_exercise)
    await state.set_state(UserState.recalling)
    await state.update_data(
        shown_exercise=shown_exercise_dict,
        shown_recall=recall.to_dict(),
    )
    text = locale.recall_prompt.format(recall=html.escape(recall.question))
    hint = recall.hint.get(language) if recall.hint else None
    if hint:
        text += f"\n<i>{html.escape(hint)}</i>"
    await message.answer(text, parse_mode="HTML")


def _format_question(
    exercise: Exercise,
    language: Language,
    course: Course,
    *,
    is_ai_generated: bool = False,
    hint_word: str | None = None,
    lesson_counter: list[int] | None = None,
) -> str:
    prefix = "🤖 " if is_ai_generated else ""
    if lesson_counter is not None:
        position, size = lesson_counter
        prefix = f"{position}/{size} {prefix}"
    text = f"{prefix}❓ {html.escape(exercise.question)}"
    if exercise.word_bank:
        # Reconstructs exactly the shape question's own hand-written
        # parenthetical hint used to have (see issue #191) — just shuffled
        # fresh on every render instead of frozen once at authoring time,
        # same as the web widget's own tile UI shuffles its copy.
        chunks = " / ".join(
            html.escape(chunk)
            for chunk in shuffle_word_bank(exercise.word_bank, exercise.answer)
        )
        text += f" ({chunks})"
    if exercise.description:
        text += f"\n💭 {html.escape(exercise.description[language])}"
    instruction = course.topic_instructions.get(exercise.topic, {}).get(language)
    if instruction:
        text += f"\nℹ️ {html.escape(instruction)}"
    if hint_word:
        hint_text = LOCALES[language].grammar_class_hint.format(word=hint_word)
        text += f"\n🔍 <tg-spoiler>{html.escape(hint_text)}</tg-spoiler>"
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


def _show_exercise_kwargs(exercise: Exercise, course: Course) -> dict:
    if exercise.distractors:
        return {"reply_markup": _make_reply_keyboard(exercise, course)}
    return {"reply_markup": ReplyKeyboardRemove()}


async def _answer_with_optional_cue(
    target: Message,
    text: str,
    exercise: Exercise,
    course: Course,
    cue_store: CueStore | None,
    **kwargs,
) -> None:
    # Only for topics the content repo has explicitly opted in via
    # topics.yaml's cue_generation flag (see Course.cue_generatable_topics)
    # — mirrors ai_generatable_topics's own per-topic gating, and for the
    # same reason: whether an exercise's topic even has anything worth
    # illustrating is a decision made once for the topic, not implied by
    # whatever else the exercise happens to carry.
    cue_url = None
    if (
        cue_store is not None
        and exercise.topic in course.cue_generatable_topics
        and len(text) <= _PHOTO_CAPTION_LIMIT
    ):
        try:
            cue_url = await cue_store.get_cue_url(exercise)
        except Exception:
            # Best-effort, same shape as clear_stale_buttons()'s own
            # TelegramBadRequest swallowing: a failed cue lookup degrades
            # to the plain-text question rather than breaking the exercise
            # flow — a learner is never blocked from practicing by an R2
            # hiccup.
            logger.warning(
                "Failed to look up cue for exercise, falling back to text",
                exc_info=True,
            )
    if cue_url is not None:
        await target.answer_photo(cue_url, caption=text, **kwargs)
    else:
        await target.answer(text, **kwargs)


async def _send_question(
    target: Message,
    exercise: Exercise,
    language: Language,
    course: Course,
    cue_store: CueStore | None,
    *,
    is_ai_generated: bool,
    hint_word: str | None,
    lesson_counter: list[int] | None,
) -> None:
    question_text = _format_question(
        exercise,
        language,
        course,
        is_ai_generated=is_ai_generated,
        hint_word=hint_word,
        lesson_counter=lesson_counter,
    )
    await _answer_with_optional_cue(
        target,
        question_text,
        exercise,
        course,
        cue_store,
        parse_mode="HTML",
        **_show_exercise_kwargs(exercise, course),
    )


async def _get_pending_exercise(
    state: FSMContext, data: dict, course: Course
) -> Exercise | None:
    # The shown exercise if it still waits for an answer. /wiederholen and
    # the "Next" button show it again, not the next one: otherwise a
    # learner could skip every exercise of a lesson and still finish it.
    # Unless /topics has deselected its topic since, which a lesson skips too
    if await state.get_state() != UserState.answering:
        return None
    shown_exercise = Exercise.from_dict(data["shown_exercise"])
    if not any(e.topic == shown_exercise.topic for e in course.exercises):
        return None
    return shown_exercise


async def _send_pending_question(
    target: Message,
    exercise: Exercise,
    data: dict,
    language: Language,
    course: Course,
    cue_store: CueStore | None,
) -> None:
    await _send_question(
        target,
        exercise,
        language,
        course,
        cue_store,
        is_ai_generated=data.get("shown_is_ai_generated", False),
        hint_word=data.get("shown_hint_word"),
        lesson_counter=data.get("shown_lesson_counter"),
    )


_TYPING_INTERVAL_SECONDS: Final = 4  # Telegram's own indicator lasts ~5s


@contextlib.asynccontextmanager
async def _show_typing_while(bot: Bot, chat_id: int) -> AsyncGenerator[None]:
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
    student_identity_store: StudentIdentityStore,
    feature_flags: dict[str, frozenset[int]] | None = None,
    anthropic_client: AsyncAnthropic | None = None,
    authoring_guide: str | None = None,
    cue_store: CueStore | None = None,
) -> None:
    await clear_stale_buttons(message.bot, message.chat.id, state)
    # An example check point for #121's flag mechanism — no visible effect
    # yet, just a span attribute for whoever's testing the flag right now.
    if has_feature(feature_flags or {}, "ai_exercises", message.chat.id):
        trace.get_current_span().set_attribute("feature.ai_exercises", True)
    data = await state.get_data()
    language = get_language(data)
    locale = LOCALES[language]
    course = restrict_to_selected_groups(course, data)
    pending_exercise = await _get_pending_exercise(state, data, course)
    if pending_exercise is not None:
        await _send_pending_question(
            message, pending_exercise, data, language, course, cue_store
        )
        return
    student_id = await student_identity_store.resolve_or_create_student_id(
        "telegram", str(message.chat.id)
    )
    # A copy, saved only after AI generation succeeds: if it fails, the next
    # request takes the same exercise from the lesson again
    lesson = dict(data.get("lesson") or {})
    async with student_record_book.check_out(student_id) as student_record:
        tutor = Tutor(
            course,
            student_record,
            lesson=lesson,
            lesson_size=_lesson_size(feature_flags, message.chat.id),
        )
        exercise = tutor.next_exercise()
        if exercise is None:
            sent = await message.answer(
                _format_nothing_due(tutor, language),
                reply_markup=_make_study_more_button(locale),
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
        hint_word = tutor.get_hint(exercise)
        lesson_counter = _get_lesson_counter(tutor)
        await state.set_state(UserState.answering)
        await state.update_data(
            shown_exercise=exercise.to_dict(),
            shown_is_ai_generated=ai_mode,
            shown_hint_word=hint_word,
            shown_lesson_counter=lesson_counter,
            lesson=lesson,
        )
        await _send_question(
            message,
            exercise,
            language,
            course,
            cue_store,
            is_ai_generated=ai_mode,
            hint_word=hint_word,
            lesson_counter=lesson_counter,
        )


@router.message(UserState.answering)
async def handle_answer(
    message: Message,
    state: FSMContext,
    course: Course,
    student_record_book: StudentRecordBook,
    student_identity_store: StudentIdentityStore,
) -> None:
    state_data = await state.get_data()
    await _clear_exercise_state(state, state_data)
    language = get_language(state_data)
    shown_exercise = Exercise.from_dict(state_data["shown_exercise"])
    locale = LOCALES[language]
    explanation = shown_exercise.explanation[language]
    student_id = await student_identity_store.resolve_or_create_student_id(
        "telegram", str(message.chat.id)
    )
    lesson = dict(state_data.get("lesson") or {})
    async with student_record_book.check_out(student_id) as student_record:
        tutor = Tutor(course, student_record, lesson=lesson)
        mark = tutor.check_answer(shown_exercise, message.text or "")
        finished_lesson = _get_finished_lesson(tutor, mark)
        await state.update_data(lesson=lesson, finished_lesson=finished_lesson)
        next_label = _get_next_label(finished_lesson, language)
        result_line = (
            locale.correct
            if mark.is_correct
            else locale.wrong.format(answer=course.shown_answer_text(shown_exercise))
        )
        if mark.recall == RecallMode.optional:
            reply_markup = _make_recall_buttons(locale, locale.btn_recall, next_label)
        elif mark.recall == RecallMode.none:
            reply_markup = make_next_button(locale, next_label)
        else:
            reply_markup = None
        # The summary comes with the "Next" button, so after a required
        # recall it comes after the recall
        if reply_markup is not None:
            explanation = _append_lesson_summary(explanation, finished_lesson, language)
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
            )
        else:
            await state.update_data(shown_exercise=state_data["shown_exercise"])
            if reply_markup is not None:
                await remember_buttoned_message(state, sent_explanation)


@router.message(UserState.recalling)
async def handle_recall(
    message: Message,
    state: FSMContext,
    course: Course,
    student_record_book: StudentRecordBook,
    student_identity_store: StudentIdentityStore,
) -> None:
    state_data = await state.get_data()
    await _clear_exercise_state(state, state_data)
    language = get_language(state_data)
    shown_recall = Recall.from_dict(state_data["shown_recall"])
    finished_lesson = state_data.get("finished_lesson")
    await state.update_data(
        shown_exercise=state_data["shown_exercise"],
        shown_recall=state_data["shown_recall"],
        finished_lesson=finished_lesson,
    )
    next_label = _get_next_label(finished_lesson, language)
    locale = LOCALES[language]
    # check_recall() is pure (never mutates student_record), unlike request_recall()
    # in _start_recall() above — open() detects that nothing changed and
    # skips the write on its own, no separate read-only path needed here.
    student_id = await student_identity_store.resolve_or_create_student_id(
        "telegram", str(message.chat.id)
    )
    async with student_record_book.check_out(student_id) as student_record:
        tutor = Tutor(course, student_record)
        if tutor.check_recall(shown_recall, message.text or ""):
            sent = await message.answer(
                _append_lesson_summary(
                    locale.recall_correct, finished_lesson, language
                ),
                reply_markup=make_next_button(locale, next_label),
            )
        else:
            correct_answer = _highlight_diff(message.text or "", shown_recall.answer[0])
            sent = await message.answer(
                _append_lesson_summary(
                    locale.recall_wrong.format(answer=correct_answer),
                    finished_lesson,
                    language,
                ),
                reply_markup=_make_recall_buttons(
                    locale, locale.btn_recall_retry, next_label
                ),
                parse_mode="HTML",
            )
    await remember_buttoned_message(state, sent)


async def _respond_with_next_exercise(
    callback: CallbackQuery,
    state: FSMContext,
    course: Course,
    tutor: Tutor,
    lesson: dict,
    language: Language,
    locale: Locale,
    *,
    ai_mode: bool,
    anthropic_client: AsyncAnthropic | None,
    authoring_guide: str | None,
    cue_store: CueStore | None,
) -> None:
    # tutor already wraps the student_record its caller opened via
    # student_record_book.check_out() — this function only ever mutates through
    # tutor, so it never needs the store itself.
    exercise = tutor.next_exercise()
    if exercise is None:
        if isinstance(callback.message, Message):
            await callback.message.edit_reply_markup(reply_markup=None)
            sent = await callback.message.answer(
                _format_nothing_due(tutor, language),
                reply_markup=_make_study_more_button(locale),
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
    hint_word = tutor.get_hint(exercise)
    lesson_counter = _get_lesson_counter(tutor)
    await state.set_state(UserState.answering)
    # Saved only after AI generation succeeded, as in command_wiederholen
    await state.update_data(
        shown_exercise=exercise.to_dict(),
        shown_is_ai_generated=ai_mode,
        shown_hint_word=hint_word,
        shown_lesson_counter=lesson_counter,
        lesson=lesson,
    )
    if isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(reply_markup=None)
        await forget_buttoned_message(state)
        await _send_question(
            callback.message,
            exercise,
            language,
            course,
            cue_store,
            is_ai_generated=ai_mode,
            hint_word=hint_word,
            lesson_counter=lesson_counter,
        )
    await callback.answer()


async def _respond_with_pending_exercise(
    callback: CallbackQuery,
    state: FSMContext,
    state_data: dict,
    course: Course,
    language: Language,
    cue_store: CueStore | None,
) -> bool:
    # A "Next" button that comes while an exercise waits for an answer, such
    # as the reminder's, shows that exercise again, as /wiederholen does
    pending_exercise = await _get_pending_exercise(state, state_data, course)
    if pending_exercise is None:
        return False
    if isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(reply_markup=None)
        await forget_buttoned_message(state)
        await _send_pending_question(
            callback.message, pending_exercise, state_data, language, course, cue_store
        )
    await callback.answer()
    return True


@router.callback_query(F.data == NEXT_EXERCISE)
async def handle_next_exercise(
    callback: CallbackQuery,
    state: FSMContext,
    course: Course,
    student_record_book: StudentRecordBook,
    student_identity_store: StudentIdentityStore,
    feature_flags: dict[str, frozenset[int]] | None = None,
    anthropic_client: AsyncAnthropic | None = None,
    authoring_guide: str | None = None,
    cue_store: CueStore | None = None,
) -> None:
    state_data = await state.get_data()
    language = get_language(state_data)
    locale = LOCALES[language]
    student_id = await student_identity_store.resolve_or_create_student_id(
        "telegram", str(callback.from_user.id)
    )
    course = restrict_to_selected_groups(course, state_data)
    if await _respond_with_pending_exercise(
        callback, state, state_data, course, language, cue_store
    ):
        return
    lesson = dict(state_data.get("lesson") or {})
    async with student_record_book.check_out(student_id) as student_record:
        tutor = Tutor(
            course,
            student_record,
            lesson=lesson,
            lesson_size=_lesson_size(feature_flags, callback.from_user.id),
        )
        await _respond_with_next_exercise(
            callback,
            state,
            course,
            tutor,
            lesson,
            language,
            locale,
            ai_mode=state_data.get("ai_mode", False),
            anthropic_client=anthropic_client,
            authoring_guide=authoring_guide,
            cue_store=cue_store,
        )


@router.callback_query(F.data == STUDY_MORE)
async def handle_study_more(
    callback: CallbackQuery,
    state: FSMContext,
    course: Course,
    student_record_book: StudentRecordBook,
    student_identity_store: StudentIdentityStore,
    feature_flags: dict[str, frozenset[int]] | None = None,
    anthropic_client: AsyncAnthropic | None = None,
    authoring_guide: str | None = None,
    cue_store: CueStore | None = None,
) -> None:
    state_data = await state.get_data()
    language = get_language(state_data)
    locale = LOCALES[language]
    student_id = await student_identity_store.resolve_or_create_student_id(
        "telegram", str(callback.from_user.id)
    )
    course = restrict_to_selected_groups(course, state_data)
    if await _respond_with_pending_exercise(
        callback, state, state_data, course, language, cue_store
    ):
        return
    lesson = dict(state_data.get("lesson") or {})
    async with student_record_book.check_out(student_id) as student_record:
        tutor = Tutor(
            course,
            student_record,
            lesson=lesson,
            lesson_size=_lesson_size(feature_flags, callback.from_user.id),
        )
        tutor.grant_new_word_budget()
        await _respond_with_next_exercise(
            callback,
            state,
            course,
            tutor,
            lesson,
            language,
            locale,
            ai_mode=state_data.get("ai_mode", False),
            anthropic_client=anthropic_client,
            authoring_guide=authoring_guide,
            cue_store=cue_store,
        )


@router.callback_query(F.data == RECALL)
async def handle_recall_request(
    callback: CallbackQuery,
    state: FSMContext,
    course: Course,
    student_record_book: StudentRecordBook,
    student_identity_store: StudentIdentityStore,
) -> None:
    state_data = await state.get_data()
    language = get_language(state_data)
    shown_exercise = Exercise.from_dict(state_data["shown_exercise"])
    locale = LOCALES[language]
    if isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(reply_markup=None)
        await forget_buttoned_message(state)
        student_id = await student_identity_store.resolve_or_create_student_id(
            "telegram", str(callback.from_user.id)
        )
        async with student_record_book.check_out(student_id) as student_record:
            await _start_recall(
                state,
                language,
                student_record,
                state_data["shown_exercise"],
                shown_exercise,
                callback.message,
                locale,
                course,
            )
    await callback.answer()
