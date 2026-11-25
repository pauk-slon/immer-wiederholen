import html
import time
import uuid
from typing import Final

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from anthropic import AsyncAnthropic
from opentelemetry import trace
from opentelemetry.trace import Span

from wiederholen.bot import answer_diff
from wiederholen.bot.button_styles import RECOMMENDED
from wiederholen.bot.commands.wiederholen import (
    LESSON_RECALL,
    NEXT_EXERCISE,
    clear_exercise_state,
    handle_next_exercise,
    offers_lesson_recall,
    send_result,
    show_typing_while,
)
from wiederholen.bot.l10n import LOCALES, Locale, get_language
from wiederholen.bot.lesson_recall_limit import count_lesson_recall
from wiederholen.bot.pending_buttons import (
    clear_stale_buttons,
    forget_buttoned_message,
    remember_buttoned_message,
)
from wiederholen.school import (
    AIGenerationError,
    Course,
    CueStore,
    Exercise,
    LessonRecall,
    StudentIdentityStore,
    StudentRecordBook,
    TranslationCheck,
    check_translation,
    generate_lesson_recall,
)
from wiederholen.tracing import default_tracer

router = Router()

SKIP: Final = "__lesson_recall_skip__"
NEXT_SENTENCE: Final = "__lesson_recall_next__"

_MIN_CHANGED_WORDS_WITHOUT_MARKS: Final = 3
# The result repeats the translation, so a longer one wouldn't fit a message
_MAX_ANSWER_LENGTH: Final = 300
RESEND: Final = "__lesson_recall_resend__"

_ID_KEY: Final = "lesson_recall_id"
_LESSON_RECALL_KEY: Final = "lesson_recall"
_POSITION_KEY: Final = "lesson_recall_position"
_ANSWER_KEY: Final = "lesson_recall_answer"
_CORRECT_KEY: Final = "lesson_recall_correct"
_WAITING_SINCE_KEY: Final = "lesson_recall_waiting_since"

# Longer than any model call, so a wait this long lost its handler,
# for example to a restart of the bot
_LOST_WAIT_SECONDS: Final = 60.0


class LessonRecallState(StatesGroup):
    generating = State()
    translating = State()
    checking = State()
    reading = State()


def _bot(message: Message) -> Bot:
    assert message.bot is not None
    return message.bot


def _keyboard(*rows: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=list(rows))


def _skip_button(locale: Locale) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=locale.btn_lesson_recall_skip, callback_data=SKIP)


def _next_exercise_button(locale: Locale) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=locale.cmd_wiederholen, callback_data=NEXT_EXERCISE
    )


def _require_setup(
    anthropic_client: AsyncAnthropic | None, course: Course
) -> tuple[AsyncAnthropic, str]:
    # check_lesson_recall_config() stops the bot at startup without them
    assert anthropic_client is not None
    assert course.lesson_recall_guide is not None
    return anthropic_client, course.lesson_recall_guide


def _lesson_recall_locale(data: dict) -> Locale:
    return LOCALES[LessonRecall.from_dict(data[_LESSON_RECALL_KEY]).language]


async def _start_waiting(state: FSMContext, waiting: State) -> None:
    await state.set_state(waiting)
    await state.update_data({_WAITING_SINCE_KEY: time.time()})


async def _is_still_current(
    state: FSMContext,
    lesson_recall_id: str,
    expected: State,
    *,
    position: int | None = None,
) -> bool:
    # A command, a button or a second message can move the chat on while the
    # model works. Its result is dropped then
    data = await state.get_data()
    return (
        data.get(_ID_KEY) == lesson_recall_id
        and await state.get_state() == expected.state
        and (position is None or data.get(_POSITION_KEY) == position)
    )


async def _report_failed_generation(
    message: Message, state: FSMContext, locale: Locale
) -> None:
    await state.set_state(None)
    sent = await message.answer(
        locale.lesson_recall_generation_failed,
        reply_markup=_keyboard([_next_exercise_button(locale)]),
    )
    await remember_buttoned_message(state, sent)


async def _offer_check_retry(
    message: Message, state: FSMContext, locale: Locale
) -> None:
    # The answer stays, so the button sends it again
    await state.set_state(LessonRecallState.translating)
    sent = await message.answer(
        locale.lesson_recall_check_failed,
        reply_markup=_keyboard(
            [
                InlineKeyboardButton(
                    text=locale.btn_lesson_recall_resend,
                    callback_data=RESEND,
                    style=RECOMMENDED,
                ),
                _skip_button(locale),
            ],
        ),
    )
    await remember_buttoned_message(state, sent)


async def _send_sentence(message: Message, state: FSMContext, locale: Locale) -> None:
    data = await state.get_data()
    lesson_recall = LessonRecall.from_dict(data[_LESSON_RECALL_KEY])
    position = data[_POSITION_KEY]
    sent = await message.answer(
        locale.lesson_recall_sentence.format(
            position=position + 1,
            size=len(lesson_recall.sentences),
            text=lesson_recall.sentences[position].text,
        ),
        reply_markup=_keyboard([_skip_button(locale)]),
    )
    await remember_buttoned_message(state, sent)


def _shown_correction(check: TranslationCheck, answer: str) -> str | None:
    if check.correction and check.correction != answer.strip():
        return check.correction
    return None


def _correction_html(answer: str, correction: str) -> str:
    changed, total = answer_diff.count_changed_words(
        answer, correction, ignore_punctuation=True
    )
    # Many marks on most of the words don't show where the mistakes are
    if changed >= _MIN_CHANGED_WORDS_WITHOUT_MARKS and changed > total / 2:
        return html.escape(correction)
    diff = answer_diff.correct(answer, [correction], ignore_punctuation=True)
    return diff.mistake or diff.answer


def _quote(text_html: str) -> str:
    # Sets the sentence apart from the explanation above it
    return f"<blockquote>{text_html}</blockquote>"


def _reference_html(locale: Locale, reference: str) -> str:
    return locale.lesson_recall_reference.format(
        reference=_quote(html.escape(reference))
    )


async def _send_result_and_go_on(
    message: Message,
    state: FSMContext,
    locale: Locale,
    result_html: str,
    *,
    wait_for_learner: bool = False,
) -> None:
    data = await state.get_data()
    lesson_recall = LessonRecall.from_dict(data[_LESSON_RECALL_KEY])
    position = data[_POSITION_KEY] + 1
    size = len(lesson_recall.sentences)
    if position < size:
        await state.update_data({_POSITION_KEY: position, _ANSWER_KEY: None})
        if wait_for_learner:
            # The next sentence would push the result up before the learner
            # reads it
            await state.set_state(LessonRecallState.reading)
            sent = await message.answer(
                result_html,
                parse_mode="HTML",
                reply_markup=_keyboard(
                    [
                        InlineKeyboardButton(
                            text=locale.btn_next_sentence, callback_data=NEXT_SENTENCE
                        )
                    ]
                ),
            )
            await remember_buttoned_message(state, sent)
            return
        await message.answer(result_html, parse_mode="HTML")
        await state.set_state(LessonRecallState.translating)
        await _send_sentence(message, state, locale)
        return
    trace.get_current_span().set_attribute("lesson_recall.finished", True)
    await clear_exercise_state(state, data)
    sent = await send_result(
        message,
        result_html,
        locale.lesson_recall_summary.format(
            correct=data.get(_CORRECT_KEY, 0), size=size
        ),
        _keyboard(
            [
                InlineKeyboardButton(
                    text=locale.btn_next_lesson, callback_data=NEXT_EXERCISE
                )
            ]
        ),
    )
    await remember_buttoned_message(state, sent)


async def _show_next_sentence(
    message: Message, state: FSMContext, locale: Locale
) -> None:
    await state.set_state(LessonRecallState.translating)
    await _send_sentence(message, state, locale)


def _lesson_exercises(course: Course, finished_lesson: dict | None) -> list[Exercise]:
    exercises_by_key = {exercise.content_key: exercise for exercise in course.exercises}
    return [
        exercises_by_key[key]
        for key in (finished_lesson or {}).get("exercise_keys", [])
        if key in exercises_by_key
    ]


async def start_lesson_recall(
    message: Message,
    state: FSMContext,
    course: Course,
    anthropic_client: AsyncAnthropic | None,
) -> None:
    """Starts the lesson recall of the lesson that has just finished. The
    caller has checked with offers_lesson_recall() that the chat gets one."""
    data = await state.get_data()
    finished_lesson = data.get("finished_lesson")
    assert finished_lesson is not None
    language = get_language(data)
    locale = LOCALES[language]
    exercises = _lesson_exercises(course, finished_lesson)
    if not exercises:
        await _report_failed_generation(message, state, locale)
        return
    client, guide = _require_setup(anthropic_client, course)
    lesson_recall_id = uuid.uuid4().hex
    await state.update_data({_ID_KEY: lesson_recall_id, _CORRECT_KEY: 0})
    await _start_waiting(state, LessonRecallState.generating)
    wrong_exercise_keys = frozenset(finished_lesson.get("wrong_exercise_keys", []))
    with default_tracer.start_as_current_span(
        "lesson_recall.generate",
        attributes={
            "lesson_recall.exercises": len(exercises),
            "lesson_recall.wrong_exercises": sum(
                exercise.content_key in wrong_exercise_keys for exercise in exercises
            ),
        },
    ) as span:
        try:
            async with show_typing_while(_bot(message), message.chat.id):
                lesson_recall = await generate_lesson_recall(
                    client,
                    exercises,
                    wrong_exercise_keys=wrong_exercise_keys,
                    guide=guide,
                    language=language,
                )
        except AIGenerationError as error:
            span.set_attribute("lesson_recall.failure", str(error))
            lesson_recall = None
        else:
            span.set_attribute("lesson_recall.sentences", len(lesson_recall.sentences))
            _record_exercises(span, lesson_recall, wrong_exercise_keys)
            # Counted even if the chat moved on, because the model call is paid
            await state.update_data(count_lesson_recall(await state.get_data()))
    if not await _is_still_current(
        state, lesson_recall_id, LessonRecallState.generating
    ):
        return
    if lesson_recall is None:
        await _report_failed_generation(message, state, locale)
        return
    await state.update_data(
        {_LESSON_RECALL_KEY: lesson_recall.to_dict(), _POSITION_KEY: 0}
    )
    await state.set_state(LessonRecallState.translating)
    await _send_sentence(message, state, locale)


@router.callback_query(F.data == LESSON_RECALL)
async def handle_old_practice_button(
    callback: CallbackQuery,
    state: FSMContext,
    course: Course,
    student_record_book: StudentRecordBook,
    student_identity_store: StudentIdentityStore,
    feature_flags: dict[str, frozenset[int]] | None = None,
    anthropic_client: AsyncAnthropic | None = None,
    cue_store: CueStore | None = None,
) -> None:
    # A practice button from before the practice became required (ADR 0037).
    # It starts the practice if the chat still gets it, otherwise the next
    # exercise, because the learner wants to go on
    data = await state.get_data()
    message = callback.message
    if not isinstance(message, Message) or not offers_lesson_recall(
        anthropic_client,
        feature_flags,
        message.chat.id,
        data.get("finished_lesson"),
        data,
    ):
        await handle_next_exercise(
            callback,
            state,
            course,
            student_record_book,
            student_identity_store,
            cue_store=cue_store,
        )
        return
    await message.edit_reply_markup(reply_markup=None)
    await forget_buttoned_message(state)
    await callback.answer()
    await start_lesson_recall(message, state, course, anthropic_client)


def _record_exercises(
    span: Span, lesson_recall: LessonRecall, wrong_exercise_keys: frozenset[str]
) -> None:
    used = lesson_recall.used_exercise_indexes()
    for index, exercise in enumerate(lesson_recall.exercises):
        span.add_event(
            "LessonRecallExercise",
            attributes={
                "word": exercise.word,
                "topic": exercise.topic,
                "used": index in used,
                "answered_wrong": exercise.content_key in wrong_exercise_keys,
            },
        )


async def _check(
    message: Message,
    state: FSMContext,
    course: Course,
    anthropic_client: AsyncAnthropic | None,
    answer: str,
) -> None:
    client, guide = _require_setup(anthropic_client, course)
    data = await state.get_data()
    lesson_recall = LessonRecall.from_dict(data[_LESSON_RECALL_KEY])
    locale = LOCALES[lesson_recall.language]
    lesson_recall_id = data[_ID_KEY]
    position = data[_POSITION_KEY]
    await _start_waiting(state, LessonRecallState.checking)
    await state.update_data({_ANSWER_KEY: answer})
    await clear_stale_buttons(_bot(message), message.chat.id, state)
    practiced = lesson_recall.sentences[position].exercise_indexes
    with default_tracer.start_as_current_span(
        "lesson_recall.check",
        attributes={
            "lesson_recall.sentence_topics": [
                lesson_recall.exercises[index].topic for index in practiced
            ]
        },
    ) as span:
        try:
            async with show_typing_while(_bot(message), message.chat.id):
                check = await check_translation(
                    client, lesson_recall, position, answer, guide=guide
                )
        except AIGenerationError as error:
            span.set_attribute("lesson_recall.failure", str(error))
            check = None
        else:
            span.set_attribute(
                "lesson_recall.verdict", "correct" if check.is_correct else "wrong"
            )
            if not check.is_correct:
                span.set_attribute(
                    "lesson_recall.corrected",
                    _shown_correction(check, answer) is not None,
                )
    if not await _is_still_current(
        state, lesson_recall_id, LessonRecallState.checking, position=position
    ):
        return
    if check is None:
        await _offer_check_retry(message, state, locale)
        return
    paragraphs = []
    if check.explanation:
        paragraphs.append(html.escape(check.explanation))
    if check.is_correct:
        await state.update_data({_CORRECT_KEY: data.get(_CORRECT_KEY, 0) + 1})
        mark = locale.correct_mark
        if not paragraphs:
            paragraphs.append(locale.correct)
    else:
        mark = locale.wrong_mark
        if correction := _shown_correction(check, answer):
            paragraphs.append(
                locale.lesson_recall_correction.format(
                    correction=_quote(_correction_html(answer, correction))
                )
            )
        else:
            reference = lesson_recall.sentences[position].reference
            paragraphs.append(_reference_html(locale, reference))
    await _send_result_and_go_on(
        message,
        state,
        locale,
        f"{mark} " + "\n\n".join(paragraphs),
        wait_for_learner=not check.is_correct or bool(check.explanation),
    )


@router.message(LessonRecallState.translating, F.text, ~F.text.startswith("/"))
async def handle_translation(
    message: Message,
    state: FSMContext,
    course: Course,
    anthropic_client: AsyncAnthropic | None = None,
) -> None:
    assert message.text is not None
    if len(message.text.strip()) > _MAX_ANSWER_LENGTH:
        trace.get_current_span().set_attribute("lesson_recall.too_long", True)
        locale = _lesson_recall_locale(await state.get_data())
        await clear_stale_buttons(_bot(message), message.chat.id, state)
        await message.answer(
            locale.lesson_recall_too_long.format(limit=_MAX_ANSWER_LENGTH)
        )
        await _send_sentence(message, state, locale)
        return
    await _check(message, state, course, anthropic_client, message.text)


@router.callback_query(LessonRecallState.translating, F.data == RESEND)
async def handle_resend(
    callback: CallbackQuery,
    state: FSMContext,
    course: Course,
    anthropic_client: AsyncAnthropic | None = None,
) -> None:
    answer = (await state.get_data()).get(_ANSWER_KEY)
    message = callback.message
    if not answer or not isinstance(message, Message):
        await callback.answer()
        return
    await message.edit_reply_markup(reply_markup=None)
    await forget_buttoned_message(state)
    await callback.answer()
    await _check(message, state, course, anthropic_client, answer)


@router.callback_query(LessonRecallState.translating, F.data == SKIP)
async def handle_skip(callback: CallbackQuery, state: FSMContext) -> None:
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer()
        return
    trace.get_current_span().set_attribute("lesson_recall.skipped", True)
    data = await state.get_data()
    lesson_recall = LessonRecall.from_dict(data[_LESSON_RECALL_KEY])
    locale = _lesson_recall_locale(data)
    reference = lesson_recall.sentences[data[_POSITION_KEY]].reference
    await message.edit_reply_markup(reply_markup=None)
    await forget_buttoned_message(state)
    await callback.answer()
    await _send_result_and_go_on(
        message,
        state,
        locale,
        _reference_html(locale, reference),
    )


@router.message(LessonRecallState.translating, ~F.text.startswith("/"))
async def handle_not_text(message: Message, state: FSMContext) -> None:
    await clear_stale_buttons(message.bot, message.chat.id, state)
    await _send_sentence(message, state, _lesson_recall_locale(await state.get_data()))


@router.callback_query(LessonRecallState.reading, F.data == NEXT_SENTENCE)
async def handle_next_sentence(callback: CallbackQuery, state: FSMContext) -> None:
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer()
        return
    await message.edit_reply_markup(reply_markup=None)
    await forget_buttoned_message(state)
    await callback.answer()
    await _show_next_sentence(
        message, state, _lesson_recall_locale(await state.get_data())
    )


@router.message(LessonRecallState.reading, ~F.text.startswith("/"))
async def handle_while_reading(message: Message, state: FSMContext) -> None:
    # The learner hasn't seen the next sentence, so the message can't be its
    # translation
    await clear_stale_buttons(message.bot, message.chat.id, state)
    await _show_next_sentence(
        message, state, _lesson_recall_locale(await state.get_data())
    )


@router.callback_query(LessonRecallState.checking, F.data.in_({SKIP, RESEND}))
async def handle_button_while_checking(
    callback: CallbackQuery, state: FSMContext
) -> None:
    locale = _lesson_recall_locale(await state.get_data())
    await callback.answer(locale.lesson_recall_wait)


@router.callback_query(F.data.in_({SKIP, RESEND, NEXT_SENTENCE}))
async def handle_old_button(callback: CallbackQuery) -> None:
    await callback.answer()


@router.message(LessonRecallState.generating, ~F.text.startswith("/"))
@router.message(LessonRecallState.checking, ~F.text.startswith("/"))
async def handle_while_waiting(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    is_generating = await state.get_state() == LessonRecallState.generating.state
    # There is no lesson recall yet to take the language from
    locale = (
        LOCALES[get_language(data)] if is_generating else _lesson_recall_locale(data)
    )
    if time.time() - data.get(_WAITING_SINCE_KEY, 0.0) < _LOST_WAIT_SECONDS:
        await message.answer(locale.lesson_recall_wait)
    elif is_generating:
        await _report_failed_generation(message, state, locale)
    else:
        await _offer_check_retry(message, state, locale)
