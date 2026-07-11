from typing import Final

from aiogram import Dispatcher

from .commands import start, language, wiederholen

dispatcher: Final = Dispatcher()

dispatcher.include_router(start.router)
dispatcher.include_router(language.router)
dispatcher.include_router(wiederholen.router)

__all__ = ["dispatcher"]
