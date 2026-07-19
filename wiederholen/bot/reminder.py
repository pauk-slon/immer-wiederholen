import asyncio
import logging
from typing import cast

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import BaseStorage, StorageKey

from wiederholen.exercises import School

from .bootstrap import load_bot_school_and_storage
from .l10n import LOCALES, get_language
from .redis_storage import ChatScanningStorage

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 15 * 60


async def _remind_chat(
    bot: Bot,
    storage: BaseStorage,
    school: School,
    chat_id: int,
    data: dict,
) -> None:
    journal = data.get("journal", {})
    teacher = school(journal)
    if not teacher.should_remind():
        return
    locale = LOCALES[get_language(data)]
    try:
        await bot.send_message(chat_id, locale.reminder_text)
    except TelegramForbiddenError:
        logger.info("Chat %s blocked the bot, skipping", chat_id)
        return
    teacher.record_reminder_sent()
    key = StorageKey(bot_id=bot.id, chat_id=chat_id, user_id=chat_id)
    await FSMContext(storage=storage, key=key).update_data(journal=journal)


async def tick(bot: Bot, storage: ChatScanningStorage, school: School) -> None:
    async for chat_id, data in storage.iter_fsm_data(bot.id):
        try:
            await _remind_chat(bot, cast(BaseStorage, storage), school, chat_id, data)
        except Exception:
            logger.exception("Failed to process reminder for chat %s", chat_id)


async def run(bot: Bot, storage: ChatScanningStorage, school: School) -> None:
    while True:
        await tick(bot, storage, school)
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def main() -> None:
    bot, school, storage = load_bot_school_and_storage()
    await run(bot, storage, school)


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
