from typing import Final

from aiogram import Dispatcher

from .commands import language, progress, reset, start, wiederholen
from .tracing import TracingMiddleware

dispatcher: Final = Dispatcher()

dispatcher.message.outer_middleware(TracingMiddleware())
dispatcher.callback_query.outer_middleware(TracingMiddleware())

dispatcher.include_router(start.router)
dispatcher.include_router(language.router)
dispatcher.include_router(progress.router)
dispatcher.include_router(reset.router)
dispatcher.include_router(wiederholen.router)

__all__ = ["dispatcher"]
