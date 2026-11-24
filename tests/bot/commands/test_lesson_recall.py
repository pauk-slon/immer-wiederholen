import time
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.methods import AnswerCallbackQuery, EditMessageReplyMarkup, SendMessage
from aiogram.types import InlineKeyboardMarkup
from anthropic import AsyncAnthropic
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Tracer

from tests.plugins.aiogram import FeedCallbackQuery, FeedMessage, FeedRawUpdate
from tests.plugins.curriculum import make_exercise
from tests.plugins.student_record_book import IntroducePairs
from wiederholen.bot.commands.lesson_recall import (
    NEXT_SENTENCE,
    RESEND,
    SKIP,
    LessonRecallState,
)
from wiederholen.bot.commands.wiederholen import LESSON_RECALL, NEXT_EXERCISE, RECALL
from wiederholen.bot.l10n import RU
from wiederholen.bot.lesson_recall_limit import DAILY_LESSON_RECALLS, STARTED_AT_KEY
from wiederholen.school import (
    AIGenerationError,
    Course,
    Exercise,
    LessonRecall,
    LessonRecallSentence,
    TranslationCheck,
)

GUIDE = "Write two sentences."
WARTEN = make_exercise(word="warten", answer="auf")
HOFFEN = make_exercise(word="hoffen", answer="auf")
DENKEN = make_exercise(word="denken", answer="an", distractors=["auf", "für", "um"])
ACHTEN = make_exercise(word="achten", answer="auf")
COURSE = Course([WARTEN, HOFFEN, DENKEN, ACHTEN], lesson_recall_guide=GUIDE)
WORDS = ("warten", "hoffen", "denken", "achten")
PRACTICE = (RU.btn_practice, LESSON_RECALL)
NEXT_LESSON = (RU.btn_next_lesson, NEXT_EXERCISE)


def _lesson_recall(*texts: str, language: Any = "ru") -> LessonRecall:
    return LessonRecall(
        exercises=(WARTEN, HOFFEN),
        sentences=tuple(
            LessonRecallSentence(
                text=text, reference=f"Ref {i}", exercise_indexes=(i % 2,)
            )
            for i, text in enumerate(texts)
        ),
        language=language,
    )


@pytest.fixture
def flags() -> dict[str, frozenset[int]]:
    return {}


@pytest.fixture
def client() -> Mock:
    return Mock(spec=AsyncAnthropic)


@pytest.fixture
def generate() -> Iterator[AsyncMock]:
    mock = AsyncMock(return_value=_lesson_recall("Первая фраза.", "Вторая фраза."))
    with patch("wiederholen.bot.commands.lesson_recall.generate_lesson_recall", mock):
        yield mock


@pytest.fixture
def check() -> Iterator[AsyncMock]:
    mock = AsyncMock(
        return_value=TranslationCheck(
            is_correct=True, explanation=None, correction=None
        )
    )
    with patch("wiederholen.bot.commands.lesson_recall.check_translation", mock):
        yield mock


@pytest.fixture
def send(
    feed_message: FeedMessage,
    feed_callback_query: FeedCallbackQuery,
    flags: dict,
    client: Mock,
):
    class Send:
        async def message(self, text: str, **kwargs) -> list[Any]:
            return await feed_message(text, **self._kwargs(kwargs))

        async def callback(self, data: str, **kwargs) -> list[Any]:
            return await feed_callback_query(data, **self._kwargs(kwargs))

        def _kwargs(self, kwargs: dict) -> dict:
            return {
                "course": COURSE,
                "feature_flags": flags,
                "anthropic_client": client,
            } | kwargs

    return Send()


async def _shown_exercise(state: FSMContext) -> Exercise:
    return Exercise.from_dict((await state.get_data())["shown_exercise"])


async def _answer_lesson(
    send: Any, state: FSMContext, rights: list[bool], **kwargs
) -> list[Any]:
    await send.message("/wiederholen", **kwargs)
    requests: list[Any] = []
    for index, right in enumerate(rights):
        if index > 0:
            await send.callback(NEXT_EXERCISE, **kwargs)
        exercise = await _shown_exercise(state)
        requests = await send.message(
            exercise.answer[0] if right else "falsch", **kwargs
        )
    return requests


async def _finish_lesson(send: Any, state: FSMContext, **kwargs) -> list[Any]:
    return await _answer_lesson(send, state, [False, True, True, True], **kwargs)


def _course_with_recalls(words: tuple[str, ...] = WORDS) -> Course:
    return Course(
        [make_exercise(word=word, recalls=True) for word in words],
        lesson_recall_guide=GUIDE,
    )


def _sent(requests: list[Any]) -> list[SendMessage]:
    return [r for r in requests if isinstance(r, SendMessage)]


def _buttons(request: Any) -> list[tuple[str, str | None]]:
    assert isinstance(request.reply_markup, InlineKeyboardMarkup)
    return [
        (button.text, button.callback_data)
        for row in request.reply_markup.inline_keyboard
        for button in row
    ]


async def _start(send: Any, state: FSMContext) -> list[Any]:
    await _finish_lesson(send, state)
    return await send.callback(LESSON_RECALL)


async def test_the_summary_offers_practice_and_the_next_lesson(
    send: Any, state: FSMContext
) -> None:
    requests = await _finish_lesson(send, state)

    summary = _sent(requests)[-1]
    assert summary.text is not None
    assert summary.text.startswith(RU.lesson_summary.format(correct=3, size=4))
    assert _buttons(summary) == [PRACTICE, NEXT_LESSON]


async def test_without_an_api_key_there_is_no_lesson_recall(
    send: Any, state: FSMContext
) -> None:
    requests = await _finish_lesson(send, state, anthropic_client=None)

    assert _buttons(_sent(requests)[-1]) == [NEXT_LESSON]


async def test_a_lesson_with_a_lesson_recall_gets_no_optional_recall(
    send: Any, state: FSMContext
) -> None:
    requests = await _answer_lesson(send, state, [True], course=_course_with_recalls())

    assert _buttons(_sent(requests)[-1]) == [(RU.cmd_wiederholen, NEXT_EXERCISE)]


async def test_a_lesson_of_three_exercises_has_no_lesson_recall(
    send: Any, state: FSMContext
) -> None:
    course = _course_with_recalls(WORDS[:3])

    first = await _answer_lesson(send, state, [True], course=course)
    await send.callback(NEXT_EXERCISE, course=course)
    await send.message((await _shown_exercise(state)).answer[0], course=course)
    await send.callback(NEXT_EXERCISE, course=course)
    last = await send.message((await _shown_exercise(state)).answer[0], course=course)

    assert RECALL in [data for _, data in _buttons(_sent(first)[-1])]
    assert NEXT_LESSON in _buttons(_sent(last)[-1])


async def test_a_wrong_required_recall_at_the_end_of_a_lesson_offers_practice(
    send: Any,
    state: FSMContext,
    introduce_pairs: IntroducePairs,
) -> None:
    course = _course_with_recalls()
    await introduce_pairs(course.exercises)
    await _answer_lesson(send, state, [True, True, True, False], course=course)

    requests = await send.message("falsch", course=course)

    keyboard = _sent(requests)[-1].reply_markup
    assert isinstance(keyboard, InlineKeyboardMarkup)
    assert [
        [(button.text, button.callback_data) for button in row]
        for row in keyboard.inline_keyboard
    ] == [[(RU.btn_recall_retry, RECALL)], [PRACTICE, NEXT_LESSON]]


async def test_a_retry_at_the_end_of_a_lesson_offers_practice(
    send: Any,
    state: FSMContext,
    introduce_pairs: IntroducePairs,
) -> None:
    course = _course_with_recalls()
    await introduce_pairs(course.exercises)
    await _answer_lesson(send, state, [True, True, True, False], course=course)
    await send.message("falsch", course=course)

    requests = await send.callback(RECALL, course=course)

    assert _buttons(_sent(requests)[-1]) == [
        PRACTICE,
        (RU.btn_recall_skip, NEXT_EXERCISE),
    ]


async def test_a_right_required_recall_at_the_end_of_a_lesson_offers_practice(
    send: Any,
    state: FSMContext,
    introduce_pairs: IntroducePairs,
) -> None:
    course = _course_with_recalls()
    await introduce_pairs(course.exercises)
    await _answer_lesson(send, state, [True, True, True, False], course=course)
    recall = (await state.get_data())["shown_recall"]

    requests = await send.message(recall["answer"][0], course=course)

    assert _buttons(_sent(requests)[-1]) == [PRACTICE, NEXT_LESSON]


async def test_the_start_sends_the_lesson_and_shows_the_first_sentence(
    send: Any, state: FSMContext, generate: AsyncMock, client: Mock
) -> None:
    await _finish_lesson(send, state)
    finished_lesson = (await state.get_data())["finished_lesson"]

    requests = await send.callback(LESSON_RECALL)

    assert any(isinstance(r, EditMessageReplyMarkup) for r in requests)
    args, kwargs = generate.call_args
    assert args[0] is client
    assert [e.content_key for e in args[1]] == finished_lesson["exercise_keys"]
    assert kwargs["wrong_exercise_keys"] == frozenset(
        finished_lesson["wrong_exercise_keys"]
    )
    assert len(kwargs["wrong_exercise_keys"]) == 1
    assert kwargs["guide"] == GUIDE
    assert kwargs["language"] == "ru"
    (sentence,) = _sent(requests)
    assert sentence.text == "1/2 ✍️ Переведите:\nПервая фраза."
    assert _buttons(sentence) == [(RU.btn_lesson_recall_skip, SKIP)]
    assert await state.get_state() == LessonRecallState.translating.state


async def test_continue_without_a_finished_lesson_shows_the_next_exercise(
    send: Any, state: FSMContext, generate: AsyncMock
) -> None:
    await send.callback(LESSON_RECALL)

    generate.assert_not_called()
    assert await state.get_state() == "UserState:answering"


async def test_continue_without_an_api_key_shows_the_next_exercise(
    send: Any, state: FSMContext, generate: AsyncMock
) -> None:
    await _finish_lesson(send, state)

    await send.callback(LESSON_RECALL, anthropic_client=None)

    generate.assert_not_called()
    assert await state.get_state() == "UserState:answering"


async def _use_up_the_daily_limit(state: FSMContext, hours_ago: float = 1) -> None:
    started_at = time.time() - hours_ago * 60 * 60
    await state.update_data({STARTED_AT_KEY: [started_at] * DAILY_LESSON_RECALLS})


async def test_a_started_lesson_recall_counts_toward_the_daily_limit(
    send: Any, state: FSMContext, generate: AsyncMock
) -> None:
    await _start(send, state)
    await send.message("/wiederholen")

    assert len((await state.get_data())[STARTED_AT_KEY]) == 1


async def test_a_failed_generation_does_not_count_toward_the_daily_limit(
    send: Any, state: FSMContext, generate: AsyncMock
) -> None:
    generate.side_effect = AIGenerationError("boom")

    await _start(send, state)

    assert STARTED_AT_KEY not in await state.get_data()


async def test_after_the_daily_limit_continue_shows_the_next_exercise(
    send: Any, state: FSMContext, generate: AsyncMock
) -> None:
    await _use_up_the_daily_limit(state)

    requests = await _finish_lesson(send, state)
    await send.callback(LESSON_RECALL)

    assert _buttons(_sent(requests)[-1]) == [NEXT_LESSON]
    generate.assert_not_called()
    assert await state.get_state() == "UserState:answering"


async def test_after_the_daily_limit_the_optional_recall_comes_back(
    send: Any, state: FSMContext
) -> None:
    await _use_up_the_daily_limit(state)

    requests = await _answer_lesson(send, state, [True], course=_course_with_recalls())

    assert RECALL in [data for _, data in _buttons(_sent(requests)[-1])]


async def test_a_lesson_recall_older_than_a_day_does_not_count(
    send: Any, state: FSMContext, generate: AsyncMock
) -> None:
    await _use_up_the_daily_limit(state, hours_ago=25)

    requests = await _finish_lesson(send, state)
    await send.callback(LESSON_RECALL)

    assert _buttons(_sent(requests)[-1]) == [PRACTICE, NEXT_LESSON]
    assert len((await state.get_data())[STARTED_AT_KEY]) == 1


async def test_a_chat_in_the_unlimited_flag_has_no_daily_limit(
    send: Any, state: FSMContext, generate: AsyncMock, chat_id: int
) -> None:
    flags = {"lesson_recall_unlimited": frozenset({chat_id})}
    await _use_up_the_daily_limit(state)

    requests = await _finish_lesson(send, state, feature_flags=flags)

    assert _buttons(_sent(requests)[-1]) == [PRACTICE, NEXT_LESSON]


async def test_the_daily_limit_is_recorded_on_the_update_span(
    send: Any, state: FSMContext
) -> None:
    await _use_up_the_daily_limit(state)
    await _answer_lesson(send, state, [True, True, True])
    await send.callback(NEXT_EXERCISE)

    with patch(
        "wiederholen.bot.commands.wiederholen.trace", spec=otel_trace
    ) as mock_trace:
        await send.message((await _shown_exercise(state)).answer[0])

    set_attribute = mock_trace.get_current_span.return_value.set_attribute
    set_attribute.assert_called_once_with("lesson_recall.limit_reached", True)


async def test_a_start_skips_exercises_that_the_course_no_longer_has(
    send: Any, state: FSMContext, generate: AsyncMock
) -> None:
    await _finish_lesson(send, state)

    await send.callback(
        LESSON_RECALL, course=Course([HOFFEN], lesson_recall_guide=GUIDE)
    )

    assert list(generate.call_args.args[1]) == [HOFFEN]


async def test_a_failed_generation_leads_to_the_next_exercise(
    send: Any, state: FSMContext, generate: AsyncMock
) -> None:
    await _finish_lesson(send, state)
    generate.side_effect = AIGenerationError("boom")

    requests = await send.callback(LESSON_RECALL)

    message = _sent(requests)[-1]
    assert message.text == RU.lesson_recall_generation_failed
    assert _buttons(message) == [(RU.cmd_wiederholen, NEXT_EXERCISE)]
    assert await state.get_state() is None


async def test_a_generation_result_is_dropped_if_the_chat_moved_on(
    send: Any, state: FSMContext, generate: AsyncMock
) -> None:
    await _finish_lesson(send, state)

    async def move_on(*args, **kwargs) -> LessonRecall:
        await state.set_state(None)
        return _lesson_recall("Фраза.")

    generate.side_effect = move_on

    requests = await send.callback(LESSON_RECALL)

    assert _sent(requests) == []
    assert len((await state.get_data())[STARTED_AT_KEY]) == 1


async def test_a_translation_is_checked_and_the_next_sentence_follows(
    send: Any, state: FSMContext, generate: AsyncMock, check: AsyncMock, client: Mock
) -> None:
    await _start(send, state)

    requests = await send.message("Wir warten.")

    args, kwargs = check.call_args
    assert args[0] is client
    assert args[1] == generate.return_value
    assert args[2:] == (0, "Wir warten.")
    assert kwargs == {"guide": GUIDE}
    result, sentence = _sent(requests)[-2:]
    assert result.text == f"{RU.correct_mark} {RU.correct}"
    assert sentence.text == "2/2 ✍️ Переведите:\nВторая фраза."


async def test_a_wrong_translation_shows_the_explanation_and_the_correction(
    send: Any, state: FSMContext, generate: AsyncMock, check: AsyncMock
) -> None:
    await _start(send, state)
    check.return_value = TranslationCheck(
        is_correct=False,
        explanation="После warten нужен auf.",
        correction="Wir warten auf <b>.",
    )

    requests = await send.message("Wir warten für <b>.")

    assert _sent(requests)[-1].text == (
        "❌ После warten нужен auf.\n\n"
        "Ваш вариант с исправлениями:\n<blockquote>Wir warten <u>auf</u> &lt;b&gt;.</blockquote>"
    )
    assert _sent(requests)[-1].parse_mode == "HTML"


async def test_a_correction_that_only_removes_words_strikes_them_through(
    send: Any, state: FSMContext, generate: AsyncMock, check: AsyncMock
) -> None:
    await _start(send, state)
    check.return_value = TranslationCheck(
        is_correct=False, explanation=None, correction="Wir warten auf den Bus."
    )

    requests = await send.message("Wir warten sehr auf den Bus.")

    assert _sent(requests)[-1].text == (
        "❌ "
        "Ваш вариант с исправлениями:\n<blockquote>Wir warten <s>sehr</s> auf den Bus.</blockquote>"
    )


async def test_a_correction_that_changes_most_words_has_no_marks(
    send: Any, state: FSMContext, generate: AsyncMock, check: AsyncMock
) -> None:
    await _start(send, state)
    check.return_value = TranslationCheck(
        is_correct=False, explanation=None, correction="Wir warten auf <den> Bus."
    )

    requests = await send.message("Ich hoffe für ein Auto.")

    assert _sent(requests)[-1].text == (
        "❌ Ваш вариант с исправлениями:\n<blockquote>Wir warten auf &lt;den&gt; Bus.</blockquote>"
    )


async def test_a_short_correction_with_two_changes_keeps_its_marks(
    send: Any, state: FSMContext, generate: AsyncMock, check: AsyncMock
) -> None:
    await _start(send, state)
    check.return_value = TranslationCheck(
        is_correct=False, explanation=None, correction="Er ist geblieben."
    )

    requests = await send.message("Er hat gewartet.")

    assert _sent(requests)[-1].text == (
        "❌ Ваш вариант с исправлениями:\n<blockquote>Er <u>ist</u> <u>geblieben</u>.</blockquote>"
    )


async def test_an_unchanged_correction_shows_the_reference(
    send: Any, state: FSMContext, generate: AsyncMock, check: AsyncMock
) -> None:
    await _start(send, state)
    check.return_value = TranslationCheck(
        is_correct=False, explanation=None, correction="Wir warten."
    )

    requests = await send.message(" Wir warten. ")

    assert (
        _sent(requests)[-1].text
        == "❌ Вариант перевода:\n<blockquote>Ref 0</blockquote>"
    )


async def test_a_wrong_translation_without_a_correction_shows_the_reference(
    send: Any, state: FSMContext, generate: AsyncMock, check: AsyncMock
) -> None:
    await _start(send, state)
    check.return_value = TranslationCheck(
        is_correct=False, explanation="После warten нужен auf <b>.", correction=None
    )

    requests = await send.message("Wir warten für.")

    assert _sent(requests)[-1].text == (
        "❌ После warten нужен auf &lt;b&gt;.\n\nВариант перевода:\n<blockquote>Ref 0</blockquote>"
    )
    assert _sent(requests)[-1].parse_mode == "HTML"


_RECALL_WITH_MARKUP_IN_THE_REFERENCE = LessonRecall(
    exercises=(WARTEN,),
    sentences=(
        LessonRecallSentence(
            text="Первая фраза.", reference="Tom & <Jerry>", exercise_indexes=(0,)
        ),
    ),
    language="ru",
)


async def test_a_wrong_translation_escapes_the_reference(
    send: Any, state: FSMContext, generate: AsyncMock, check: AsyncMock
) -> None:
    generate.return_value = _RECALL_WITH_MARKUP_IN_THE_REFERENCE
    await _start(send, state)
    check.return_value = TranslationCheck(
        is_correct=False, explanation=None, correction=None
    )

    requests = await send.message("Wir warten.")

    assert _sent(requests)[-2].text == (
        "❌ Вариант перевода:\n<blockquote>Tom &amp; &lt;Jerry&gt;</blockquote>"
    )


async def test_a_skip_escapes_the_reference(
    send: Any, state: FSMContext, generate: AsyncMock
) -> None:
    generate.return_value = _RECALL_WITH_MARKUP_IN_THE_REFERENCE
    await _start(send, state)

    requests = await send.callback(SKIP)

    assert (
        _sent(requests)[-2].text
        == "Вариант перевода:\n<blockquote>Tom &amp; &lt;Jerry&gt;</blockquote>"
    )


async def test_the_last_result_leads_to_the_next_exercise(
    send: Any, state: FSMContext, generate: AsyncMock, check: AsyncMock
) -> None:
    await _start(send, state)
    await send.message("Wir warten.")

    requests = await send.message("Ich hoffe.")

    result, summary = _sent(requests)
    assert result.text == f"{RU.correct_mark} {RU.correct}"
    assert result.reply_markup is None
    assert summary.text == RU.lesson_recall_summary.format(correct=2, size=2)
    assert _buttons(summary) == [NEXT_LESSON]
    assert await state.get_state() is None
    data = await state.get_data()
    assert "lesson_recall" not in data
    assert "finished_lesson" not in data
    assert "lesson" in data


async def test_a_skip_of_the_last_sentence_leads_to_the_next_exercise(
    send: Any, state: FSMContext, generate: AsyncMock
) -> None:
    await _start(send, state)
    await send.callback(SKIP)

    requests = await send.callback(SKIP)

    reference, summary = _sent(requests)
    assert reference.text == "Вариант перевода:\n<blockquote>Ref 1</blockquote>"
    assert summary.text == RU.lesson_recall_summary.format(correct=0, size=2)
    assert _buttons(summary) == [NEXT_LESSON]


async def test_a_next_exercise_button_of_another_message_leaves_the_lesson_recall(
    send: Any, state: FSMContext, generate: AsyncMock, check: AsyncMock
) -> None:
    await _start(send, state)

    await send.callback(NEXT_EXERCISE)
    await send.message("Wir warten.")

    check.assert_not_called()
    assert await state.get_state() != LessonRecallState.translating.state


async def test_a_failed_check_keeps_the_answer_for_another_try(
    send: Any, state: FSMContext, generate: AsyncMock, check: AsyncMock
) -> None:
    await _start(send, state)
    check.side_effect = AIGenerationError("boom")

    requests = await send.message("Wir warten.")

    message = _sent(requests)[-1]
    assert message.text == RU.lesson_recall_check_failed
    assert _buttons(message) == [
        (RU.btn_lesson_recall_resend, RESEND),
        (RU.btn_lesson_recall_skip, SKIP),
    ]
    check.side_effect = None
    requests = await send.callback(RESEND)
    assert check.call_args.args[2:] == (0, "Wir warten.")
    assert _sent(requests)[-1].text == "2/2 ✍️ Переведите:\nВторая фраза."


async def test_a_resend_without_an_answer_does_nothing(
    send: Any, state: FSMContext, generate: AsyncMock, check: AsyncMock
) -> None:
    await _start(send, state)

    requests = await send.callback(RESEND)

    check.assert_not_called()
    assert _sent(requests) == []


async def test_a_skip_shows_the_reference_without_a_model_call(
    send: Any, state: FSMContext, generate: AsyncMock, check: AsyncMock
) -> None:
    await _start(send, state)

    requests = await send.callback(SKIP)

    check.assert_not_called()
    reference, sentence = _sent(requests)[-2:]
    assert reference.text == "Вариант перевода:\n<blockquote>Ref 0</blockquote>"
    assert reference.parse_mode == "HTML"
    assert sentence.text == "2/2 ✍️ Переведите:\nВторая фраза."


async def test_a_skip_on_an_inaccessible_message_does_nothing(
    send: Any,
    state: FSMContext,
    generate: AsyncMock,
    feed_raw_update: FeedRawUpdate,
    telegram_user_id: int,
) -> None:
    await _start(send, state)

    requests = await feed_raw_update(
        {
            "update_id": 4,
            "callback_query": {
                "id": "x",
                "from": {"id": telegram_user_id, "is_bot": False, "first_name": "T"},
                "chat_instance": "1",
                "data": SKIP,
            },
        },
        course=COURSE,
    )

    assert _sent(requests) == []
    assert (await state.get_data())["lesson_recall_position"] == 0


@pytest.mark.parametrize(
    "waiting", [LessonRecallState.generating, LessonRecallState.checking]
)
async def test_a_message_while_the_model_works_gets_a_short_reply(
    send: Any, state: FSMContext, generate: AsyncMock, check: AsyncMock, waiting: Any
) -> None:
    await _start(send, state)
    await state.set_state(waiting)
    await state.update_data(lesson_recall_waiting_since=time.time() - 10)

    requests = await send.message("Hallo?")

    assert [r.text for r in _sent(requests)] == [RU.lesson_recall_wait]
    check.assert_not_called()


async def test_a_lost_generation_leads_to_the_next_exercise(
    send: Any, state: FSMContext, generate: AsyncMock
) -> None:
    await _finish_lesson(send, state)
    await state.set_state(LessonRecallState.generating)
    await state.update_data(lesson_recall_waiting_since=time.time() - 120)

    requests = await send.message("Hallo?")

    assert _sent(requests)[-1].text == RU.lesson_recall_generation_failed
    assert await state.get_state() is None


async def test_a_lost_check_offers_to_send_the_answer_again(
    send: Any, state: FSMContext, generate: AsyncMock, check: AsyncMock
) -> None:
    await _start(send, state)
    await state.set_state(LessonRecallState.checking)
    await state.update_data(
        lesson_recall_answer="Wir warten.",
        lesson_recall_waiting_since=time.time() - 120,
    )

    requests = await send.message("Hallo?")

    check.assert_not_called()
    assert _sent(requests)[-1].text == RU.lesson_recall_check_failed
    await send.callback(RESEND)
    assert check.call_args.args[2:] == (0, "Wir warten.")


async def test_a_check_result_is_dropped_if_the_sentence_changed(
    send: Any, state: FSMContext, generate: AsyncMock, check: AsyncMock
) -> None:
    await _start(send, state)

    async def second_message_moves_on(*args, **kwargs) -> TranslationCheck:
        await state.update_data(lesson_recall_position=1)
        return TranslationCheck(is_correct=True, explanation=None, correction=None)

    check.side_effect = second_message_moves_on

    requests = await send.message("Wir warten.")

    assert _sent(requests) == []


async def test_a_check_result_is_dropped_if_the_chat_moved_on(
    send: Any, state: FSMContext, generate: AsyncMock, check: AsyncMock
) -> None:
    await _start(send, state)

    async def move_on(*args, **kwargs) -> TranslationCheck:
        await state.set_state(None)
        return TranslationCheck(is_correct=True, explanation=None, correction=None)

    check.side_effect = move_on

    requests = await send.message("Wir warten.")

    assert _sent(requests) == []


async def test_a_button_while_checking_asks_to_wait(
    send: Any, state: FSMContext, generate: AsyncMock
) -> None:
    await _start(send, state)
    await state.set_state(LessonRecallState.checking)

    requests = await send.callback(SKIP)

    answers = [r for r in requests if isinstance(r, AnswerCallbackQuery)]
    assert [a.text for a in answers] == [RU.lesson_recall_wait]
    assert _sent(requests) == []


async def test_an_old_skip_button_is_answered(send: Any, state: FSMContext) -> None:
    requests = await send.callback(SKIP)

    assert any(isinstance(r, AnswerCallbackQuery) for r in requests)
    assert _sent(requests) == []


async def test_a_too_long_translation_isnt_checked(
    send: Any, state: FSMContext, generate: AsyncMock, check: AsyncMock
) -> None:
    await _start(send, state)

    requests = await send.message("Wir warten " + "sehr " * 60)

    check.assert_not_called()
    notice, sentence = _sent(requests)
    assert notice.text == RU.lesson_recall_too_long.format(limit=300)
    assert sentence.text == "1/2 ✍️ Переведите:\nПервая фраза."
    assert _buttons(sentence) == [(RU.btn_lesson_recall_skip, SKIP)]
    assert any(isinstance(r, EditMessageReplyMarkup) for r in requests)
    assert await state.get_state() == LessonRecallState.translating.state


async def test_a_translation_of_the_maximum_length_is_checked(
    send: Any, state: FSMContext, generate: AsyncMock, check: AsyncMock
) -> None:
    await _start(send, state)

    await send.message("a" * 300 + "  ")

    check.assert_called_once()


async def test_a_too_long_translation_is_recorded_on_the_update_span(
    send: Any, state: FSMContext, generate: AsyncMock
) -> None:
    await _start(send, state)

    with patch(
        "wiederholen.bot.commands.lesson_recall.trace", spec=otel_trace
    ) as mock_trace:
        await send.message("a" * 301)

    set_attribute = mock_trace.get_current_span.return_value.set_attribute
    set_attribute.assert_called_once_with("lesson_recall.too_long", True)


async def test_a_message_without_text_shows_the_sentence_again(
    send: Any,
    state: FSMContext,
    generate: AsyncMock,
    check: AsyncMock,
    feed_raw_update: FeedRawUpdate,
    chat_id: int,
    flags: dict,
) -> None:
    await _start(send, state)

    requests = await feed_raw_update(
        {
            "update_id": 3,
            "message": {
                "message_id": 2,
                "date": datetime.now(tz=UTC),
                "chat": {"id": chat_id, "type": "private"},
                "from": {"id": chat_id, "is_bot": False, "first_name": "Test"},
                "sticker": {
                    "file_id": "x",
                    "file_unique_id": "x",
                    "type": "regular",
                    "width": 1,
                    "height": 1,
                    "is_animated": False,
                    "is_video": False,
                },
            },
        },
        course=COURSE,
        feature_flags=flags,
    )

    check.assert_not_called()
    assert _sent(requests)[-1].text == "1/2 ✍️ Переведите:\nПервая фраза."


async def test_wiederholen_ends_the_lesson_recall(
    send: Any, state: FSMContext, generate: AsyncMock, check: AsyncMock
) -> None:
    await _start(send, state)

    await send.message("/wiederholen")

    check.assert_not_called()
    assert await state.get_state() == "UserState:answering"


async def test_a_wait_reply_uses_the_language_of_the_start(
    send: Any, state: FSMContext, generate: AsyncMock
) -> None:
    generate.return_value = _lesson_recall("Sentence one.", "Two.", language="en")
    await _start(send, state)
    await state.set_state(LessonRecallState.checking)
    await state.update_data(lesson_recall_waiting_since=time.time() - 10)

    requests = await send.message("Hallo?")

    assert [r.text for r in _sent(requests)] == ["⏳ One moment, I'm still thinking…"]


async def test_the_check_uses_the_language_of_the_start(
    send: Any, state: FSMContext, generate: AsyncMock, check: AsyncMock
) -> None:
    generate.return_value = _lesson_recall("Sentence one.", "Two.", language="en")
    await _start(send, state)

    requests = await send.message("Wir warten.")

    assert _sent(requests)[-2].text == "✅ Correct!"


async def test_the_spans_record_the_generation_and_the_check(
    send: Any,
    state: FSMContext,
    generate: AsyncMock,
    check: AsyncMock,
    tracer: Tracer,
    exporter: InMemorySpanExporter,
) -> None:
    with patch("wiederholen.bot.commands.lesson_recall.default_tracer", tracer):
        await _start(send, state)
        check.return_value = TranslationCheck(
            is_correct=False, explanation=None, correction="Wir warten auf."
        )
        await send.message("Wir warten.")
        await send.callback(NEXT_SENTENCE)
        check.side_effect = AIGenerationError("model did not call the expected tool")
        await send.message("Ich hoffe.")
        check.side_effect = None
        check.return_value = TranslationCheck(
            is_correct=False, explanation=None, correction=None
        )
        await send.message("Wir hoffen.")

    generation, corrected, failure, uncorrected = exporter.get_finished_spans()
    assert generation.name == "lesson_recall.generate"
    assert dict(generation.attributes or {}) == {
        "lesson_recall.exercises": 4,
        "lesson_recall.wrong_exercises": 1,
        "lesson_recall.sentences": 2,
    }
    assert corrected.name == "lesson_recall.check"
    assert dict(corrected.attributes or {}) == {
        "lesson_recall.verdict": "wrong",
        "lesson_recall.corrected": True,
    }
    assert dict(uncorrected.attributes or {}) == {
        "lesson_recall.verdict": "wrong",
        "lesson_recall.corrected": False,
    }
    assert dict(failure.attributes or {}) == {
        "lesson_recall.failure": "model did not call the expected tool"
    }


async def test_the_last_sentence_is_recorded_on_the_update_span(
    send: Any, state: FSMContext, generate: AsyncMock
) -> None:
    await _start(send, state)
    await send.callback(SKIP)

    with patch(
        "wiederholen.bot.commands.lesson_recall.trace", spec=otel_trace
    ) as mock_trace:
        await send.callback(SKIP)

    set_attribute = mock_trace.get_current_span.return_value.set_attribute
    assert set_attribute.call_args_list[-1].args == ("lesson_recall.finished", True)


async def test_a_skip_is_recorded_on_the_update_span(
    send: Any, state: FSMContext, generate: AsyncMock
) -> None:
    await _start(send, state)

    with patch(
        "wiederholen.bot.commands.lesson_recall.trace", spec=otel_trace
    ) as mock_trace:
        await send.callback(SKIP)

    mock_trace.get_current_span.return_value.set_attribute.assert_called_once_with(
        "lesson_recall.skipped", True
    )


async def test_a_wrong_translation_waits_for_the_learner(
    send: Any, state: FSMContext, generate: AsyncMock, check: AsyncMock
) -> None:
    await _start(send, state)
    check.return_value = TranslationCheck(
        is_correct=False, explanation="После warten нужен auf.", correction=None
    )

    requests = await send.message("Wir warten für.")

    [result] = _sent(requests)
    assert _buttons(result) == [(RU.btn_next_sentence, NEXT_SENTENCE)]
    assert await state.get_state() == LessonRecallState.reading.state


async def test_continue_after_a_wrong_translation_shows_the_next_sentence(
    send: Any, state: FSMContext, generate: AsyncMock, check: AsyncMock
) -> None:
    await _start(send, state)
    check.return_value = TranslationCheck(
        is_correct=False, explanation=None, correction=None
    )
    await send.message("Wir warten für.")

    requests = await send.callback(NEXT_SENTENCE)

    assert isinstance(requests[0], EditMessageReplyMarkup)
    assert requests[0].reply_markup is None
    assert _sent(requests)[-1].text == "2/2 ✍️ Переведите:\nВторая фраза."
    assert await state.get_state() == LessonRecallState.translating.state


async def test_a_message_while_reading_shows_the_next_sentence_unchecked(
    send: Any, state: FSMContext, generate: AsyncMock, check: AsyncMock
) -> None:
    await _start(send, state)
    check.return_value = TranslationCheck(
        is_correct=False, explanation=None, correction=None
    )
    await send.message("Wir warten für.")

    requests = await send.message("Ich hoffe.")

    check.assert_called_once()
    assert any(isinstance(r, EditMessageReplyMarkup) for r in requests)
    assert _sent(requests)[-1].text == "2/2 ✍️ Переведите:\nВторая фраза."
    assert await state.get_state() == LessonRecallState.translating.state


async def test_continue_on_an_inaccessible_message_does_nothing(
    send: Any,
    state: FSMContext,
    generate: AsyncMock,
    check: AsyncMock,
    feed_raw_update: FeedRawUpdate,
    telegram_user_id: int,
) -> None:
    await _start(send, state)
    check.return_value = TranslationCheck(
        is_correct=False, explanation=None, correction=None
    )
    await send.message("Wir warten für.")

    requests = await feed_raw_update(
        {
            "update_id": 5,
            "callback_query": {
                "id": "x",
                "from": {"id": telegram_user_id, "is_bot": False, "first_name": "T"},
                "chat_instance": "1",
                "data": NEXT_SENTENCE,
            },
        },
        course=COURSE,
    )

    assert _sent(requests) == []
    assert await state.get_state() == LessonRecallState.reading.state


async def test_an_old_continue_button_is_answered(send: Any, state: FSMContext) -> None:
    requests = await send.callback(NEXT_SENTENCE)

    assert any(isinstance(r, AnswerCallbackQuery) for r in requests)
    assert _sent(requests) == []


async def test_the_summary_counts_the_right_translations(
    send: Any, state: FSMContext, generate: AsyncMock, check: AsyncMock
) -> None:
    await _start(send, state)
    check.return_value = TranslationCheck(
        is_correct=False, explanation=None, correction=None
    )
    await send.message("Wir warten für.")
    await send.callback(NEXT_SENTENCE)
    check.return_value = TranslationCheck(
        is_correct=True, explanation="Отлично, hoffen auf.", correction=None
    )

    requests = await send.message("Ich hoffe auf.")

    result, summary = _sent(requests)
    assert result.text == f"{RU.correct_mark} Отлично, hoffen auf."
    assert summary.text == RU.lesson_recall_summary.format(correct=1, size=2)


async def test_a_right_translation_with_an_explanation_waits_for_the_learner(
    send: Any, state: FSMContext, generate: AsyncMock, check: AsyncMock
) -> None:
    await _start(send, state)
    check.return_value = TranslationCheck(
        is_correct=True, explanation="Верно, warten auf.", correction=None
    )

    requests = await send.message("Wir warten auf.")

    [result] = _sent(requests)
    assert result.text == f"{RU.correct_mark} Верно, warten auf."
    assert _buttons(result) == [(RU.btn_next_sentence, NEXT_SENTENCE)]
    assert await state.get_state() == LessonRecallState.reading.state


async def test_the_next_lesson_after_the_summary_skips_the_practice(
    send: Any, state: FSMContext, generate: AsyncMock
) -> None:
    await _finish_lesson(send, state)

    await send.callback(NEXT_EXERCISE)

    generate.assert_not_called()
    assert await state.get_state() == "UserState:answering"


async def test_an_offer_of_practice_is_recorded_on_the_update_span(
    send: Any, state: FSMContext
) -> None:
    await _answer_lesson(send, state, [False, True, True])
    await send.callback(NEXT_EXERCISE)

    with patch(
        "wiederholen.bot.commands.wiederholen.trace", spec=otel_trace
    ) as mock_trace:
        await send.message((await _shown_exercise(state)).answer[0])

    set_attribute = mock_trace.get_current_span.return_value.set_attribute
    set_attribute.assert_called_once_with("lesson_recall.offered", True)
