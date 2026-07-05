import asyncio
import os
from pathlib import Path

from aiogram import Bot
from aiogram.types import BotCommand

from . import dp
from .l10n import LOCALES
from wiederholen.exercises import load_exercises, School


async def main() -> None:
    token = os.environ["BOT_TOKEN"]
    exercises_path = Path(os.environ.get("EXERCISES_PATH", "data/exercises.yaml"))
    school = School(load_exercises(exercises_path))
    bot = Bot(token=token)
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


if __name__ == "__main__":
    asyncio.run(main())
