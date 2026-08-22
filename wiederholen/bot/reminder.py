import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError

from wiederholen.students import StudentStore
from wiederholen.tutoring import Course, Tutor

from .bootstrap import load_reminder_course_and_store
from .l10n import LOCALES, get_language
from .tracing import configure_tracing, default_tracer, instrument_redis

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 15 * 60


async def _remind_chat(
    bot: Bot,
    store: StudentStore,
    course: Course,
    chat_id: int,
    data: dict,
) -> None:
    with default_tracer.start_as_current_span(
        "reminder.check_chat",
        attributes={"telegram.chat_id": chat_id, "reminder.sent": False},
    ) as span:
        journal = data.get("journal", {})
        tutor = Tutor(course, journal)
        if not tutor.should_remind():
            return
        locale = LOCALES[get_language(data)]
        try:
            await bot.send_message(chat_id, locale.reminder_text)
        except TelegramForbiddenError:
            logger.info("Chat %s blocked the bot, skipping", chat_id)
            return
        span.set_attribute("reminder.sent", True)
        tutor.record_reminder_sent()
        await store.set(str(chat_id), data)


async def tick(bot: Bot, store: StudentStore, course: Course) -> None:
    with default_tracer.start_as_current_span("reminder.tick"):
        async for student_id, data in store.iter_items():
            chat_id = int(student_id)
            try:
                await _remind_chat(bot, store, course, chat_id, data)
            except Exception:
                logger.exception("Failed to process reminder for chat %s", chat_id)


async def run(bot: Bot, store: StudentStore, course: Course) -> None:
    while True:
        await tick(bot, store, course)
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def main() -> None:
    configure_tracing()
    instrument_redis()
    bot, course, store = load_reminder_course_and_store()
    await run(bot, store, course)


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
