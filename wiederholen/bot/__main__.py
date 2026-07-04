import asyncio
import os
from pathlib import Path
from typing import Final

from aiogram import Bot
from aiogram.types import BotCommand

from . import dp
from .l10n import LOCALES
from wiederholen.exercises import load_exercises, School

TOKEN: Final = os.environ["BOT_TOKEN"]
EXERCISES_PATH: Final = Path(os.environ.get("EXERCISES_PATH", "data/exercises.yaml"))


async def main() -> None:
    school = School(load_exercises(EXERCISES_PATH))
    bot = Bot(token=TOKEN)
    for language_code, locale in LOCALES.items():
        await bot.set_my_commands(
            [
                BotCommand(command="start", description=locale.cmd_start),
                BotCommand(command="wiederholen", description=locale.cmd_wiederholen),
                BotCommand(command="language", description=locale.cmd_language),
            ],
            language_code=language_code,
        )
    await dp.start_polling(bot, school=school)


asyncio.run(main())
