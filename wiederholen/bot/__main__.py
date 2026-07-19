import asyncio
import logging

from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import BotCommand

from . import dispatcher
from .bootstrap import load_bot_school_and_storage
from .l10n import LOCALES

logger = logging.getLogger(__name__)


async def main() -> None:
    bot, school, storage = load_bot_school_and_storage()
    dispatcher.fsm.storage = storage
    for language_code, locale in LOCALES.items():
        try:
            await bot.set_my_name(locale.bot_name, language_code=language_code)
            await bot.set_my_description(
                locale.bot_short_description, language_code=language_code
            )
            await bot.set_my_short_description(
                locale.bot_short_description, language_code=language_code
            )
            await bot.set_my_commands(
                [
                    BotCommand(command="start", description=locale.cmd_start),
                    BotCommand(
                        command="wiederholen",
                        description=locale.cmd_wiederholen,
                    ),
                    BotCommand(command="language", description=locale.cmd_language),
                ],
                language_code=language_code,
            )
        except TelegramRetryAfter as e:
            logger.warning(
                "Rate limited setting bot info, skipping: retry in %ds",
                e.retry_after,
            )
    await dispatcher.start_polling(bot, school=school)


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
