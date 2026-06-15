import asyncio
import os
from typing import Final

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

TOKEN: Final = os.environ["BOT_TOKEN"]

dp: Final = Dispatcher()


@dp.message(Command("start"))
async def command_start_handler(message: Message) -> None:
    await message.answer(
        "Hi! I'll help you memorize foreign words using spaced repetition."
    )


async def main() -> None:
    bot = Bot(token=TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
