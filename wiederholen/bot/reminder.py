import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.redis import RedisStorage

from wiederholen.bot.commands.wiederholen import make_next_button
from wiederholen.school import Course, StudentRecordBook, Tutor
from wiederholen.tracing import configure_tracing, default_tracer, instrument_redis

from .bootstrap import load_bot_course_and_storage
from .l10n import LOCALES, get_language
from .pending_buttons import clear_stale_buttons, remember_buttoned_message
from .telegram_student_id import NotATelegramStudentIdError, TelegramStudentID

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 15 * 60


async def _remind_chat(
    bot: Bot,
    fsm_storage: RedisStorage,
    student_record_book: StudentRecordBook,
    course: Course,
    chat_id: int,
) -> None:
    with default_tracer.start_as_current_span(
        "reminder.check_chat",
        attributes={"telegram.chat_id": chat_id, "reminder.sent": False},
    ) as span:
        student_id = TelegramStudentID.encode(chat_id)
        async with student_record_book.check_out(student_id) as student_record:
            tutor = Tutor(course, student_record)
            if not tutor.should_remind():
                return
            # language lives in aiogram's own FSM data, not the student_record —
            # this is the one point reminder.py still needs a real aiogram
            # storage for (see "Persistence" in CLAUDE.md). The same FSMContext
            # also backs clear_stale_buttons()/remember_buttoned_message() below
            # — reminder.py has no incoming Message the way a command handler
            # does, but a StorageKey built from bot_id/chat_id/user_id is exactly
            # what FSMContext wraps either way, so the pending_buttons helpers
            # work identically here.
            state = FSMContext(
                storage=fsm_storage,
                key=StorageKey(bot_id=bot.id, chat_id=chat_id, user_id=chat_id),
            )
            data = await state.get_data()
            locale = LOCALES[get_language(data)]
            try:
                # Clears whatever button group is still attached to an earlier
                # message (e.g. a "Следующее задание" prompt the learner never
                # tapped) before attaching a fresh one here — without this, a
                # reminder used to leave that old button dangling forever, the
                # same problem clear_stale_buttons() already solves for every
                # command entry point (see its own module docstring). Both
                # calls can raise TelegramForbiddenError for the same
                # underlying reason (the chat blocked the bot), so one
                # try/except covers both rather than duplicating the same
                # catch twice.
                await clear_stale_buttons(bot, chat_id, state)
                sent = await bot.send_message(
                    chat_id, locale.reminder_text, reply_markup=make_next_button(locale)
                )
            except TelegramForbiddenError:
                logger.info("Chat %s blocked the bot, skipping", chat_id)
                return
            span.set_attribute("reminder.sent", True)
            tutor.record_reminder_sent()
            await remember_buttoned_message(state, sent)
            # No explicit save here — student_record_book.check_out() persists the
            # record_reminder_sent() mutation on exit; the two early returns
            # above left the student_record untouched, so open() writes nothing for
            # them.


async def tick(
    bot: Bot,
    fsm_storage: RedisStorage,
    student_record_book: StudentRecordBook,
    course: Course,
) -> None:
    with default_tracer.start_as_current_span("reminder.tick"):
        async for student_id in student_record_book:
            try:
                chat_id = TelegramStudentID.decode(student_id)
            except NotATelegramStudentIdError:
                continue
            try:
                await _remind_chat(
                    bot, fsm_storage, student_record_book, course, chat_id
                )
            except Exception:
                logger.exception("Failed to process reminder for chat %s", chat_id)


async def run(
    bot: Bot,
    fsm_storage: RedisStorage,
    student_record_book: StudentRecordBook,
    course: Course,
) -> None:
    while True:
        await tick(bot, fsm_storage, student_record_book, course)
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def main() -> None:
    configure_tracing()
    instrument_redis()
    bot, course, fsm_storage, student_record_book = load_bot_course_and_storage()
    await run(bot, fsm_storage, student_record_book, course)


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
