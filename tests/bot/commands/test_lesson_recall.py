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
from wiederholen.bot.commands.lesson_recall import RESEND, SKIP, LessonRecallState
from wiederholen.bot.commands.wiederholen import LESSON_RECALL, NEXT_EXERCISE, RECALL
from wiederholen.bot.l10n import RU
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
def flags(chat_id: int) -> dict[str, frozenset[int]]:
    return {"lesson_recall": frozenset({chat_id})}


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


async def test_continue_after_the_summary_starts_a_lesson_recall(
    send: Any, state: FSMContext
) -> None:
    requests = await _finish_lesson(send, state)

    summary = _sent(requests)[-1]
    assert summary.text is not None and "Верно: 3 из 4" in summary.text
    assert _buttons(summary) == [(RU.btn_continue, LESSON_RECALL)]


async def test_a_chat_outside_the_flag_gets_no_lesson_recall(
    send: Any, state: FSMContext
) -> None:
    requests = await _finish_lesson(send, state, feature_flags={})

    assert _buttons(_sent(requests)[-1]) == [(RU.btn_continue, NEXT_EXERCISE)]


async def test_a_chat_in_the_flag_gets_no_optional_recall(
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
    assert (RU.btn_continue, NEXT_EXERCISE) in _buttons(_sent(last)[-1])


async def test_continue_after_a_wrong_required_recall_starts_a_lesson_recall(
    send: Any, state: FSMContext
) -> None:
    course = _course_with_recalls()
    await _answer_lesson(send, state, [True, True, True, False], course=course)

    requests = await send.message("falsch", course=course)

    assert _buttons(_sent(requests)[-1]) == [
        (RU.btn_recall_retry, RECALL),
        (RU.btn_continue, LESSON_RECALL),
    ]


async def test_continue_after_a_right_required_recall_starts_a_lesson_recall(
    send: Any, state: FSMContext
) -> None:
    course = _course_with_recalls()
    await _answer_lesson(send, state, [True, True, True, False], course=course)
    recall = (await state.get_data())["shown_recall"]

    requests = await send.message(recall["answer"][0], course=course)

    assert _buttons(_sent(requests)[-1]) == [(RU.btn_continue, LESSON_RECALL)]


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
    sentence = _sent(requests)[-1]
    assert sentence.text == "1/2 ✍️ Переведите:\nПервая фраза."
    assert _buttons(sentence) == [(RU.btn_lesson_recall_skip, SKIP)]
    assert await state.get_state() == LessonRecallState.translating.state


async def test_continue_without_a_finished_lesson_shows_the_next_exercise(
    send: Any, state: FSMContext, generate: AsyncMock
) -> None:
    await send.callback(LESSON_RECALL)

    generate.assert_not_called()
    assert await state.get_state() == "UserState:answering"


async def test_continue_outside_the_flag_shows_the_next_exercise(
    send: Any, state: FSMContext, generate: AsyncMock
) -> None:
    await _finish_lesson(send, state)

    await send.callback(LESSON_RECALL, feature_flags={})

    generate.assert_not_called()
    assert await state.get_state() == "UserState:answering"


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
    assert result.text == RU.lesson_recall_correct
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

    assert _sent(requests)[-2].text == (
        "🔴 Неверно.\n\nПосле warten нужен auf.\n\n"
        "Ваш вариант с исправлениями: Wir warten <u>auf</u> &lt;b&gt;."
    )
    assert _sent(requests)[-2].parse_mode == "HTML"


async def test_a_correction_that_only_removes_words_strikes_them_through(
    send: Any, state: FSMContext, generate: AsyncMock, check: AsyncMock
) -> None:
    await _start(send, state)
    check.return_value = TranslationCheck(
        is_correct=False, explanation=None, correction="Wir warten auf den Bus."
    )

    requests = await send.message("Wir warten sehr auf den Bus.")

    assert _sent(requests)[-2].text == (
        "🔴 Неверно.\n\n"
        "Ваш вариант с исправлениями: Wir warten <s>sehr</s> auf den Bus."
    )


async def test_an_unchanged_correction_shows_the_reference(
    send: Any, state: FSMContext, generate: AsyncMock, check: AsyncMock
) -> None:
    await _start(send, state)
    check.return_value = TranslationCheck(
        is_correct=False, explanation=None, correction="Wir warten."
    )

    requests = await send.message(" Wir warten. ")

    assert _sent(requests)[-2].text == "🔴 Неверно.\n\nВариант перевода: Ref 0"


async def test_a_wrong_translation_without_a_correction_shows_the_reference(
    send: Any, state: FSMContext, generate: AsyncMock, check: AsyncMock
) -> None:
    await _start(send, state)
    check.return_value = TranslationCheck(
        is_correct=False, explanation="После warten нужен auf <b>.", correction=None
    )

    requests = await send.message("Wir warten für.")

    assert _sent(requests)[-2].text == (
        "🔴 Неверно.\n\nПосле warten нужен auf &lt;b&gt;.\n\nВариант перевода: Ref 0"
    )
    assert _sent(requests)[-2].parse_mode == "HTML"


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

    assert _sent(requests)[-1].text == (
        "🔴 Неверно.\n\nВариант перевода: Tom &amp; &lt;Jerry&gt;"
    )


async def test_a_skip_escapes_the_reference(
    send: Any, state: FSMContext, generate: AsyncMock
) -> None:
    generate.return_value = _RECALL_WITH_MARKUP_IN_THE_REFERENCE
    await _start(send, state)

    requests = await send.callback(SKIP)

    assert _sent(requests)[-1].text == "Вариант перевода: Tom &amp; &lt;Jerry&gt;"


async def test_the_last_result_leads_to_the_next_exercise(
    send: Any, state: FSMContext, generate: AsyncMock, check: AsyncMock
) -> None:
    await _start(send, state)
    await send.message("Wir warten.")

    requests = await send.message("Ich hoffe.")

    [result] = _sent(requests)
    assert result.text == RU.lesson_recall_correct
    assert _buttons(result) == [(RU.cmd_wiederholen, NEXT_EXERCISE)]
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

    [reference] = _sent(requests)
    assert reference.text == "Вариант перевода: Ref 1"
    assert _buttons(reference) == [(RU.cmd_wiederholen, NEXT_EXERCISE)]


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
    assert reference.text == "Вариант перевода: Ref 0"
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

    assert _sent(requests)[-2].text == "🟢 Correct!"


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
