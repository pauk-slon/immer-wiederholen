import asyncio
import os
from pathlib import Path
from typing import Final

from aiogram import Bot
from aiogram.types import BotCommand

from . import dp
from .l10n import LOCALES
from wiederholen.cards import load_cards, make_card_picker

TOKEN: Final = os.environ["BOT_TOKEN"]
CARDS_PATH: Final = Path(os.environ.get("CARDS_PATH", "data/cards.yaml"))


async def main() -> None:
    cards = load_cards(CARDS_PATH)
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
    await dp.start_polling(bot, card_picker=make_card_picker(cards))


asyncio.run(main())
