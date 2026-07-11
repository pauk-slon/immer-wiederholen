from typing import Final

from aiogram import Dispatcher

from .commands import start, language, wiederholen

dispatcher: Final = Dispatcher()

# Order matches handler registration order in the original single-file
# bot: start, language, then the wiederholen exercise flow.
dispatcher.include_router(start.router)
dispatcher.include_router(language.router)
dispatcher.include_router(wiederholen.router)

__all__ = ["dispatcher"]
