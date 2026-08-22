import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.redis import RedisStorage

from wiederholen.journal_backend import JournalBackend
from wiederholen.tutoring import Course, Tutor

from .bootstrap import load_bot_course_and_storage
from .l10n import LOCALES, get_language
from .tracing import configure_tracing, default_tracer, instrument_redis

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 15 * 60


async def _remind_chat(
    bot: Bot,
    fsm_storage: RedisStorage,
    journal_backend: JournalBackend,
    course: Course,
    chat_id: int,
    journal: dict,
) -> None:
    with default_tracer.start_as_current_span(
        "reminder.check_chat",
        attributes={"telegram.chat_id": chat_id, "reminder.sent": False},
    ) as span:
        tutor = Tutor(course, journal)
        if not tutor.should_remind():
            return
        # language lives in aiogram's own FSM data, not the journal — this is
        # the one point reminder.py still needs a real aiogram storage for
        # (see "Persistence" in CLAUDE.md).
        data = await fsm_storage.get_data(
            StorageKey(bot_id=bot.id, chat_id=chat_id, user_id=chat_id)
        )
        locale = LOCALES[get_language(data)]
        try:
            await bot.send_message(chat_id, locale.reminder_text)
        except TelegramForbiddenError:
            logger.info("Chat %s blocked the bot, skipping", chat_id)
            return
        span.set_attribute("reminder.sent", True)
        tutor.record_reminder_sent()
        await journal_backend.save_journal(str(chat_id), journal)


async def tick(
    bot: Bot,
    fsm_storage: RedisStorage,
    journal_backend: JournalBackend,
    course: Course,
) -> None:
    with default_tracer.start_as_current_span("reminder.tick"):
        async for student_id, journal in journal_backend.iter_journals():
            chat_id = int(student_id)
            try:
                await _remind_chat(
                    bot, fsm_storage, journal_backend, course, chat_id, journal
                )
            except Exception:
                logger.exception("Failed to process reminder for chat %s", chat_id)


async def run(
    bot: Bot,
    fsm_storage: RedisStorage,
    journal_backend: JournalBackend,
    course: Course,
) -> None:
    while True:
        await tick(bot, fsm_storage, journal_backend, course)
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def main() -> None:
    configure_tracing()
    instrument_redis()
    bot, course, fsm_storage, journal_backend = load_bot_course_and_storage()
    await run(bot, fsm_storage, journal_backend, course)


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
