import asyncio
import contextlib
import html
import logging
import random
from collections.abc import AsyncGenerator
from typing import Final

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
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

from wiederholen.bot import answer_diff
from wiederholen.bot.l10n import (
    LOCALES,
    Locale,
    append_streak_line,
    format_count,
    format_wait,
    get_language,
)
from wiederholen.bot.lesson_recall_limit import (
    STARTED_AT_KEY,
    has_lesson_recall_left,
    seconds_until_lesson_recall,
)
from wiederholen.bot.pending_buttons import (
    clear_stale_buttons,
    forget_buttoned_message,
    remember_buttoned_message,
)
from wiederholen.bot.topic_selection import restrict_to_selected_groups
from wiederholen.school import (
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
    shuffle_word_bank,
)

logger = logging.getLogger(__name__)

router = Router()

NEXT_EXERCISE: Final = "__next__"
RECALL: Final = "__recall__"
STUDY_MORE: Final = "__study_more__"
LESSON_RECALL: Final = "__lesson_recall__"

# Telegram's own limit for a photo's caption — well below the 4096 a plain
# text message gets. A question long enough to exceed it (word_bank's own
# parenthetical, description, instruction all appended — see
# _format_question()) falls back to a plain text message instead of a
# truncated caption; see _answer_with_optional_cue().
_PHOTO_CAPTION_LIMIT: Final = 1024

# Telegram doesn't send an empty message
_KEYBOARD_REMOVAL_TEXT: Final = "…"

# The bot's lessons have 5 exercises (#325). The web app keeps
# Tutor.LESSON_SIZE of 1, so it has no counter and no summary
_LESSON_SIZE: Final = 5
# A smaller lesson gives too few sentences for the wait of a generation
_MIN_LESSON_RECALL_SIZE: Final = 3


class UserState(StatesGroup):
    answering = State()
    recalling = State()


# Lasting chat state living in FSM data alongside exercise state — it
# must outlive the state.clear() that ends each exercise, or e.g. the
# language silently reverts to the default after one answer.
_LASTING_CHAT_STATE_KEYS: Final = (
    "language",
    "topic_groups",
    "remind_after_hours",
    # Not a setting: the lesson lasts for several exercises (see
    # wiederholen.school.tutoring.lesson)
    "lesson",
    STARTED_AT_KEY,
)


async def clear_exercise_state(state: FSMContext, state_data: dict) -> None:
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
        "exercise_keys": list(finished_lesson.given_exercise_keys),
        "wrong_exercise_keys": list(finished_lesson.wrong_exercise_keys),
    }


def _lesson_recall_is_on(
    anthropic_client: AsyncAnthropic | None, lesson_size: int | None
) -> bool:
    # check_lesson_recall_config() makes sure that the client has a guide
    return (
        anthropic_client is not None
        and lesson_size is not None
        and lesson_size >= _MIN_LESSON_RECALL_SIZE
    )


def _make_practice_button(locale: Locale) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=locale.btn_practice, callback_data=LESSON_RECALL
                )
            ]
        ]
    )


def offers_lesson_recall(
    anthropic_client: AsyncAnthropic | None,
    feature_flags: dict[str, frozenset[int]] | None,
    chat_id: int,
    finished_lesson: dict | None,
    state_data: dict,
) -> bool:
    return (
        finished_lesson is not None
        and bool(finished_lesson.get("exercise_keys"))
        and _lesson_recall_is_on(anthropic_client, finished_lesson["size"])
        and has_lesson_recall_left(feature_flags, chat_id, state_data)
    )


def _format_lesson_summary(
    finished_lesson: dict | None,
    language: Language,
    seconds_until_practice: float | None,
) -> str | None:
    if finished_lesson is None:
        return None
    locale = LOCALES[language]
    summary = locale.lesson_summary.format(
        correct=finished_lesson["correct"], size=finished_lesson["size"]
    )
    if finished_lesson["streak_days"] is not None:
        days = format_count(finished_lesson["streak_days"], "days", language)
        summary += "\n" + locale.streak_text.format(days=days)
    if seconds_until_practice is not None:
        wait = format_wait(seconds_until_practice, language)
        summary += "\n" + locale.lesson_recall_limit_text.format(wait=wait)
    return summary


async def send_result(
    message: Message,
    result_html: str,
    summary: str | None,
    reply_markup: InlineKeyboardMarkup,
) -> Message:
    if summary is None:
        return await message.answer(
            result_html, reply_markup=reply_markup, parse_mode="HTML"
        )
    await message.answer(result_html, parse_mode="HTML")
    return await message.answer(summary, reply_markup=reply_markup)


async def _remove_reply_keyboard(message: Message) -> None:
    # A message with ReplyKeyboardRemove can't get inline buttons later
    assert message.bot is not None
    sent = await message.answer(
        _KEYBOARD_REMOVAL_TEXT,
        reply_markup=ReplyKeyboardRemove(),
        disable_notification=True,
    )
    try:
        await message.bot.delete_message(message.chat.id, sent.message_id)
    except TelegramAPIError:
        # The answer is already recorded, so the result must come anyway.
        # The learner only sees the short message
        logger.warning("Failed to delete the keyboard removal message", exc_info=True)


def _get_next_label(finished_lesson: dict | None, language: Language) -> str | None:
    # After a lesson, the "Next" button starts the next lesson
    if finished_lesson is None:
        return None
    return LOCALES[language].btn_next_lesson


async def _start_recall(
    state: FSMContext,
    language: Language,
    student_record: dict,
    shown_exercise_dict: dict,
    shown_exercise: Exercise,
    message: Message,
    course: Course,
    *,
    skip_markup: InlineKeyboardMarkup | None = None,
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
        recall_is_skippable=skip_markup is not None,
    )
    await _send_recall_prompt(message, state, recall, language, skip_markup)


async def _send_recall_prompt(
    message: Message,
    state: FSMContext,
    recall: Recall,
    language: Language,
    skip_markup: InlineKeyboardMarkup | None,
) -> None:
    sent = await message.answer(
        _recall_prompt(recall, language, LOCALES[language]),
        reply_markup=skip_markup,
        parse_mode="HTML",
    )
    if skip_markup is not None:
        await remember_buttoned_message(state, sent)


def _make_skip_recall_button(locale: Locale) -> InlineKeyboardMarkup:
    return make_next_button(locale, locale.btn_recall_skip)


def _recall_prompt(recall: Recall, language: Language, locale: Locale) -> str:
    text = locale.recall_prompt.format(recall=html.escape(recall.question))
    hint = recall.hint.get(language) if recall.hint else None
    if hint:
        text += f"\n<i>{html.escape(hint)}</i>"
    return text


def _format_question(
    exercise: Exercise,
    language: Language,
    course: Course,
    *,
    hint_word: str | None = None,
    lesson_counter: list[int] | None = None,
) -> str:
    prefix = ""
    if lesson_counter is not None:
        position, size = lesson_counter
        prefix = f"{position}/{size} "
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


def _format_wrong(
    locale: Locale,
    template: str,
    user_text: str,
    answers: list[str],
    *,
    ignore_punctuation: bool = False,
) -> str:
    correction = answer_diff.correct(
        user_text, answers, ignore_punctuation=ignore_punctuation
    )
    if correction.mistake is not None:
        text = locale.wrong_extra_letters.format(
            mistake=correction.mistake, answer=correction.answer
        )
    else:
        text = template.format(answer=correction.answer)
    return f"{locale.wrong_mark} {text}"


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
    # topics.yaml's cue_generation flag (see Course.cue_generatable_topics):
    # whether an exercise's topic even has anything worth illustrating is a
    # decision made once for the topic, not implied by whatever else the
    # exercise happens to carry.
    cue_url = None
    if (
        cue_store is not None
        and exercise.topic in course.cue_generatable_topics
        and exercise.cue is not False
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
    hint_word: str | None,
    lesson_counter: list[int] | None,
) -> None:
    question_text = _format_question(
        exercise,
        language,
        course,
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
        hint_word=data.get("shown_hint_word"),
        lesson_counter=data.get("shown_lesson_counter"),
    )


_TYPING_INTERVAL_SECONDS: Final = 4  # Telegram's own indicator lasts ~5s


@contextlib.asynccontextmanager
async def show_typing_while(bot: Bot, chat_id: int) -> AsyncGenerator[None]:
    # Telegram's "typing..." indicator auto-expires after ~5s (or once a
    # message is sent), and a model call can easily run past that. Refresh
    # it on a loop in the background instead, cancelled once the call
    # finishes either way.
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


@router.message(Command("wiederholen"))
async def command_wiederholen(
    message: Message,
    state: FSMContext,
    course: Course,
    student_record_book: StudentRecordBook,
    student_identity_store: StudentIdentityStore,
    cue_store: CueStore | None = None,
) -> None:
    await clear_stale_buttons(message.bot, message.chat.id, state)
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
    lesson = dict(data.get("lesson") or {})
    async with student_record_book.check_out(student_id) as student_record:
        tutor = Tutor(
            course,
            student_record,
            lesson=lesson,
            lesson_size=_LESSON_SIZE,
        )
        exercise = tutor.next_exercise()
        if exercise is None:
            sent = await message.answer(
                _format_nothing_due(tutor, language),
                reply_markup=_make_study_more_button(locale),
            )
            await remember_buttoned_message(state, sent)
            return
        hint_word = tutor.get_hint(exercise)
        lesson_counter = _get_lesson_counter(tutor)
        await state.set_state(UserState.answering)
        await state.update_data(
            shown_exercise=exercise.to_dict(),
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
            hint_word=hint_word,
            lesson_counter=lesson_counter,
        )


@router.message(UserState.answering, F.text, ~F.text.startswith("/"))
async def handle_answer(
    message: Message,
    state: FSMContext,
    course: Course,
    student_record_book: StudentRecordBook,
    student_identity_store: StudentIdentityStore,
    feature_flags: dict[str, frozenset[int]] | None = None,
    anthropic_client: AsyncAnthropic | None = None,
) -> None:
    assert message.text is not None
    state_data = await state.get_data()
    await clear_exercise_state(state, state_data)
    language = get_language(state_data)
    shown_exercise = Exercise.from_dict(state_data["shown_exercise"])
    locale = LOCALES[language]
    explanation = html.escape(shown_exercise.explanation[language])
    student_id = await student_identity_store.resolve_or_create_student_id(
        "telegram", str(message.chat.id)
    )
    lesson = dict(state_data.get("lesson") or {})
    async with student_record_book.check_out(student_id) as student_record:
        tutor = Tutor(course, student_record, lesson=lesson)
        mark = tutor.check_answer(shown_exercise, message.text)
        finished_lesson = _get_finished_lesson(tutor, mark)
        await state.update_data(lesson=lesson, finished_lesson=finished_lesson)
        next_label = _get_next_label(finished_lesson, language)
        lesson_counter = state_data.get("shown_lesson_counter")
        seconds_until_practice = seconds_until_lesson_recall(
            feature_flags, message.chat.id, state_data
        )
        lesson_recall_left = seconds_until_practice is None
        has_lesson_recall = lesson_recall_left and _lesson_recall_is_on(
            anthropic_client, lesson_counter[1] if lesson_counter else None
        )
        limit_reached = (
            not lesson_recall_left
            and finished_lesson is not None
            and _lesson_recall_is_on(anthropic_client, finished_lesson["size"])
        )
        if limit_reached:
            trace.get_current_span().set_attribute("lesson_recall.limit_reached", True)
        # The lesson recall practices the mistakes of the lesson, so a lesson
        # with it gets no recall after an answer
        recall_mode = RecallMode.none if has_lesson_recall else mark.recall
        if mark.is_correct:
            result_html = f"{locale.correct_mark} {explanation}"
        else:
            wrong_line = _format_wrong(
                locale,
                locale.wrong,
                message.text,
                course.shown_answers(shown_exercise),
            )
            result_html = f"{wrong_line}\n\n{explanation}"
        if shown_exercise.distractors:
            await _remove_reply_keyboard(message)
        summary = _format_lesson_summary(
            finished_lesson,
            language,
            seconds_until_practice if limit_reached else None,
        )
        if recall_mode == RecallMode.required:
            # The summary counts the answers of the lesson, so it comes before
            # the recall, without buttons. The recall result doesn't repeat it
            await message.answer(result_html, parse_mode="HTML")
            if summary is not None:
                await message.answer(summary)
            await _start_recall(
                state,
                language,
                student_record,
                state_data["shown_exercise"],
                shown_exercise,
                message,
                course,
            )
            return
        if offers_lesson_recall(
            anthropic_client,
            feature_flags,
            message.chat.id,
            finished_lesson,
            state_data,
        ):
            # The practice is the only way on. A button says what comes next
            reply_markup = _make_practice_button(locale)
        elif recall_mode == RecallMode.optional:
            reply_markup = _make_recall_buttons(locale, locale.btn_recall, next_label)
        else:
            reply_markup = make_next_button(locale, next_label)
        sent = await send_result(message, result_html, summary, reply_markup)
        await state.update_data(shown_exercise=state_data["shown_exercise"])
        await remember_buttoned_message(state, sent)


@router.message(UserState.recalling, F.text, ~F.text.startswith("/"))
async def handle_recall(
    message: Message,
    state: FSMContext,
    course: Course,
    student_record_book: StudentRecordBook,
    student_identity_store: StudentIdentityStore,
) -> None:
    assert message.text is not None
    await clear_stale_buttons(message.bot, message.chat.id, state)
    state_data = await state.get_data()
    await clear_exercise_state(state, state_data)
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
    # check_recall() doesn't change student_record, unlike request_recall()
    # in _start_recall() above — open() detects that nothing changed and
    # skips the write on its own, no separate read-only path needed here.
    student_id = await student_identity_store.resolve_or_create_student_id(
        "telegram", str(message.chat.id)
    )
    async with student_record_book.check_out(student_id) as student_record:
        tutor = Tutor(course, student_record)
        if tutor.check_recall(
            Exercise.from_dict(state_data["shown_exercise"]),
            shown_recall,
            message.text,
        ):
            result_html = f"{locale.correct_mark} {locale.correct}"
            reply_markup = make_next_button(locale, next_label)
        else:
            result_html = _format_wrong(
                locale,
                locale.recall_wrong,
                message.text,
                [shown_recall.answer[0]],
                ignore_punctuation=True,
            )
            reply_markup = _make_recall_buttons(
                locale, locale.btn_recall_retry, next_label
            )
        sent = await message.answer(
            result_html, reply_markup=reply_markup, parse_mode="HTML"
        )
    await remember_buttoned_message(state, sent)


@router.message(UserState.recalling)
async def show_the_recall_again(
    message: Message,
    state: FSMContext,
) -> None:
    # Not the fallback: its "next" button would skip the recall
    await clear_stale_buttons(message.bot, message.chat.id, state)
    state_data = await state.get_data()
    language = get_language(state_data)
    skip_markup = (
        _make_skip_recall_button(LOCALES[language])
        if state_data.get("recall_is_skippable")
        else None
    )
    await _send_recall_prompt(
        message,
        state,
        Recall.from_dict(state_data["shown_recall"]),
        language,
        skip_markup,
    )


async def _respond_with_next_exercise(
    callback: CallbackQuery,
    state: FSMContext,
    course: Course,
    tutor: Tutor,
    lesson: dict,
    language: Language,
    locale: Locale,
    *,
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
    hint_word = tutor.get_hint(exercise)
    lesson_counter = _get_lesson_counter(tutor)
    await state.set_state(UserState.answering)
    await state.update_data(
        shown_exercise=exercise.to_dict(),
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
    cue_store: CueStore | None = None,
) -> None:
    state_data = await state.get_data()
    language = get_language(state_data)
    locale = LOCALES[language]
    student_id = await student_identity_store.resolve_or_create_student_id(
        "telegram", str(callback.from_user.id)
    )
    course = restrict_to_selected_groups(course, state_data)
    if await state.get_state() == UserState.recalling:
        # The learner skipped the recall
        await state.set_state(None)
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
            lesson_size=_LESSON_SIZE,
        )
        await _respond_with_next_exercise(
            callback,
            state,
            course,
            tutor,
            lesson,
            language,
            locale,
            cue_store=cue_store,
        )


@router.callback_query(F.data == STUDY_MORE)
async def handle_study_more(
    callback: CallbackQuery,
    state: FSMContext,
    course: Course,
    student_record_book: StudentRecordBook,
    student_identity_store: StudentIdentityStore,
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
            lesson_size=_LESSON_SIZE,
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
        # The learner asked for this recall, after an optional offer or after
        # a wrong attempt, which already offered to go on
        skip_markup = _make_skip_recall_button(locale)
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
                course,
                skip_markup=skip_markup,
            )
    await callback.answer()
