import asyncio
import logging
import os
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand

from . import dispatcher
from .l10n import LOCALES
from wiederholen.exercises import load_exercises, School

logger = logging.getLogger(__name__)


async def main() -> None:
    token = os.environ["BOT_TOKEN"]
    exercises_path = Path(os.environ.get("EXERCISES_PATH", "data/exercises.yaml"))
    dispatcher.fsm.storage = RedisStorage.from_url(os.environ["FSM_STORAGE_URL"])
    school = School(load_exercises(exercises_path))
    bot = Bot(token=token)
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
