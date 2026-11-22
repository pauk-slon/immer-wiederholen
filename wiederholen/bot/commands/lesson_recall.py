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

from wiederholen.bot.commands.wiederholen import (
    LESSON_RECALL,
    clear_exercise_state,
    make_next_button,
    show_typing_while,
)
from wiederholen.bot.feature_flags import LESSON_RECALL_FLAG, has_feature
from wiederholen.bot.l10n import LOCALES, Locale, get_language
from wiederholen.bot.pending_buttons import (
    clear_stale_buttons,
    forget_buttoned_message,
    remember_buttoned_message,
)
from wiederholen.school import (
    AIGenerationError,
    Course,
    LessonRecall,
    check_translation,
    generate_lesson_recall,
)
from wiederholen.tracing import default_tracer

router = Router()

SKIP: Final = "__lesson_recall_skip__"
RESEND: Final = "__lesson_recall_resend__"

# Exercise state: clear_exercise_state() drops these keys with the rest
_ID_KEY: Final = "lesson_recall_id"
_LESSON_RECALL_KEY: Final = "lesson_recall"
_POSITION_KEY: Final = "lesson_recall_position"
_ANSWER_KEY: Final = "lesson_recall_answer"


class LessonRecallState(StatesGroup):
    generating = State()
    translating = State()
    checking = State()


def _bot(message: Message) -> Bot:
    assert message.bot is not None
    return message.bot


def _keyboard(*rows: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=list(rows))


def _skip_button(locale: Locale) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=locale.btn_lesson_recall_skip, callback_data=SKIP)


def _continue_button(locale: Locale) -> InlineKeyboardMarkup:
    return make_next_button(locale, locale.btn_continue)


async def _is_still_current(
    state: FSMContext, lesson_recall_id: str, expected: State
) -> bool:
    # A command or a button can end the lesson recall while the model works,
    # and a new one can start. Their result is dropped then
    data = await state.get_data()
    return (
        data.get(_ID_KEY) == lesson_recall_id
        and await state.get_state() == expected.state
    )


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


async def _go_to_next_sentence(
    message: Message, state: FSMContext, locale: Locale
) -> None:
    data = await state.get_data()
    lesson_recall = LessonRecall.from_dict(data[_LESSON_RECALL_KEY])
    position = data[_POSITION_KEY] + 1
    if position < len(lesson_recall.sentences):
        await state.set_state(LessonRecallState.translating)
        await state.update_data({_POSITION_KEY: position, _ANSWER_KEY: None})
        await _send_sentence(message, state, locale)
        return
    await clear_exercise_state(state, data)
    sent = await message.answer(
        locale.lesson_recall_done, reply_markup=_continue_button(locale)
    )
    await remember_buttoned_message(state, sent)


@router.callback_query(F.data == LESSON_RECALL)
async def handle_start(
    callback: CallbackQuery,
    state: FSMContext,
    course: Course,
    feature_flags: dict[str, frozenset[int]] | None = None,
    anthropic_client: AsyncAnthropic | None = None,
) -> None:
    data = await state.get_data()
    finished_lesson = data.get("finished_lesson") or {}
    exercises_by_key = {exercise.content_key: exercise for exercise in course.exercises}
    exercises = [
        exercises_by_key[key]
        for key in finished_lesson.get("exercise_keys", [])
        if key in exercises_by_key
    ]
    message = callback.message
    # An old button, or a lesson whose exercises the course no longer has
    if (
        not isinstance(message, Message)
        or not has_feature(feature_flags or {}, LESSON_RECALL_FLAG, message.chat.id)
        or not exercises
        or anthropic_client is None
        or course.lesson_recall_guide is None
    ):
        await callback.answer()
        return
    language = get_language(data)
    locale = LOCALES[language]
    await message.edit_reply_markup(reply_markup=None)
    await forget_buttoned_message(state)
    await callback.answer()
    lesson_recall_id = uuid.uuid4().hex
    await state.set_state(LessonRecallState.generating)
    await state.update_data({_ID_KEY: lesson_recall_id})
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
                    anthropic_client,
                    exercises,
                    wrong_exercise_keys=wrong_exercise_keys,
                    guide=course.lesson_recall_guide,
                    language=language,
                )
        except AIGenerationError as error:
            span.set_attribute("lesson_recall.failure", str(error))
            lesson_recall = None
        else:
            span.set_attribute("lesson_recall.sentences", len(lesson_recall.sentences))
    if not await _is_still_current(
        state, lesson_recall_id, LessonRecallState.generating
    ):
        return
    if lesson_recall is None:
        # finished_lesson stays, so the button can start the lesson recall again
        await state.set_state(None)
        sent = await message.answer(
            locale.lesson_recall_generation_failed,
            reply_markup=_keyboard(
                [
                    InlineKeyboardButton(
                        text=locale.btn_recall_retry, callback_data=LESSON_RECALL
                    )
                ],
                *_continue_button(locale).inline_keyboard,
            ),
        )
        await remember_buttoned_message(state, sent)
        return
    await state.set_state(LessonRecallState.translating)
    await state.update_data(
        {_LESSON_RECALL_KEY: lesson_recall.to_dict(), _POSITION_KEY: 0}
    )
    await _send_sentence(message, state, locale)


async def _check(
    message: Message,
    state: FSMContext,
    course: Course,
    anthropic_client: AsyncAnthropic | None,
    answer: str,
) -> None:
    data = await state.get_data()
    lesson_recall = LessonRecall.from_dict(data[_LESSON_RECALL_KEY])
    locale = LOCALES[lesson_recall.language]
    lesson_recall_id = data[_ID_KEY]
    position = data[_POSITION_KEY]
    await state.set_state(LessonRecallState.checking)
    await state.update_data({_ANSWER_KEY: answer})
    with default_tracer.start_as_current_span("lesson_recall.check") as span:
        try:
            if anthropic_client is None or course.lesson_recall_guide is None:
                raise AIGenerationError("lesson recall is not configured")
            async with show_typing_while(_bot(message), message.chat.id):
                check = await check_translation(
                    anthropic_client,
                    lesson_recall,
                    position,
                    answer,
                    guide=course.lesson_recall_guide,
                )
        except AIGenerationError as error:
            span.set_attribute("lesson_recall.failure", str(error))
            check = None
        else:
            span.set_attribute(
                "lesson_recall.verdict", "correct" if check.is_correct else "wrong"
            )
    if not await _is_still_current(state, lesson_recall_id, LessonRecallState.checking):
        return
    if check is None:
        # The answer stays, so the button sends it again
        await state.set_state(LessonRecallState.translating)
        sent = await message.answer(
            locale.lesson_recall_check_failed,
            reply_markup=_keyboard(
                [
                    InlineKeyboardButton(
                        text=locale.btn_lesson_recall_resend, callback_data=RESEND
                    ),
                    _skip_button(locale),
                ]
            ),
        )
        await remember_buttoned_message(state, sent)
        return
    lines = [
        locale.lesson_recall_correct if check.is_correct else locale.lesson_recall_wrong
    ]
    if check.explanation:
        lines.append(check.explanation)
    if not check.is_correct:
        reference = lesson_recall.sentences[position].reference
        lines.append(locale.lesson_recall_reference.format(reference=reference))
    await message.answer("\n\n".join(lines))
    await _go_to_next_sentence(message, state, locale)


@router.message(LessonRecallState.translating, F.text, ~F.text.startswith("/"))
async def handle_translation(
    message: Message,
    state: FSMContext,
    course: Course,
    anthropic_client: AsyncAnthropic | None = None,
) -> None:
    await clear_stale_buttons(message.bot, message.chat.id, state)
    assert message.text is not None
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
    locale = LOCALES[lesson_recall.language]
    reference = lesson_recall.sentences[data[_POSITION_KEY]].reference
    await message.edit_reply_markup(reply_markup=None)
    await forget_buttoned_message(state)
    await callback.answer()
    await message.answer(locale.lesson_recall_reference.format(reference=reference))
    await _go_to_next_sentence(message, state, locale)


@router.message(LessonRecallState.translating, ~F.text.startswith("/"))
async def handle_not_text(message: Message, state: FSMContext) -> None:
    await clear_stale_buttons(message.bot, message.chat.id, state)
    data = await state.get_data()
    locale = LOCALES[LessonRecall.from_dict(data[_LESSON_RECALL_KEY]).language]
    await _send_sentence(message, state, locale)


@router.message(LessonRecallState.generating, ~F.text.startswith("/"))
@router.message(LessonRecallState.checking, ~F.text.startswith("/"))
async def handle_while_waiting(message: Message, state: FSMContext) -> None:
    locale = LOCALES[get_language(await state.get_data())]
    await message.answer(locale.lesson_recall_wait)
