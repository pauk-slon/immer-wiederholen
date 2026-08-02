import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import BaseStorage, StorageKey

from wiederholen.tutoring import Course, Tutor

from .bootstrap import load_bot_course_and_storage
from .l10n import LOCALES, get_language
from .redis_storage import ScanningRedisStorage
from .tracing import configure_tracing, default_tracer, instrument_redis

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 15 * 60


async def _remind_chat(
    bot: Bot,
    storage: BaseStorage,
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
        key = StorageKey(bot_id=bot.id, chat_id=chat_id, user_id=chat_id)
        await FSMContext(storage=storage, key=key).update_data(journal=journal)


async def tick(bot: Bot, storage: ScanningRedisStorage, course: Course) -> None:
    with default_tracer.start_as_current_span("reminder.tick"):
        async for chat_id, data in storage.iter_fsm_data(bot.id):
            try:
                await _remind_chat(bot, storage, course, chat_id, data)
            except Exception:
                logger.exception("Failed to process reminder for chat %s", chat_id)


async def run(bot: Bot, storage: ScanningRedisStorage, course: Course) -> None:
    while True:
        await tick(bot, storage, course)
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def main() -> None:
    configure_tracing()
    instrument_redis()
    bot, course, storage = load_bot_course_and_storage()
    await run(bot, storage, course)


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
