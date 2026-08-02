from typing import Final

from aiogram import Dispatcher

from .commands import language, progress, reset, start, wiederholen
from .tracing import TracingMiddleware

dispatcher: Final = Dispatcher(disable_fsm=True)

# disable_fsm=True skips aiogram's own auto-registration of its FSM-context
# middleware so we can register TracingMiddleware ahead of it here instead —
# outer middlewares wrap in registration order, and the FSM middleware reads
# state from storage (a Redis call) before any handler runs, which would
# otherwise happen outside of (and unparented by) our span.
dispatcher.update.outer_middleware(TracingMiddleware())
dispatcher.update.outer_middleware(dispatcher.fsm)

dispatcher.include_router(start.router)
dispatcher.include_router(language.router)
dispatcher.include_router(progress.router)
dispatcher.include_router(reset.router)
dispatcher.include_router(wiederholen.router)

__all__ = ["dispatcher"]
