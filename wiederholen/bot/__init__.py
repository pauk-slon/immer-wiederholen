from typing import Final

from aiogram import Dispatcher

from .chat_membership import router as chat_membership_router
from .commands import (
    fallback,
    language,
    lesson_recall,
    progress,
    reminders,
    reset,
    start,
    topics,
    wiederholen,
)
from .tracing import TracingMiddleware

dispatcher: Final = Dispatcher(disable_fsm=True)

# disable_fsm=True skips aiogram's own auto-registration of its FSM-context
# middleware so we can register TracingMiddleware ahead of it here instead —
# outer middlewares wrap in registration order, and the FSM middleware reads
# state from storage (a Redis call) before any handler runs, which would
# otherwise happen outside of (and unparented by) our span.
dispatcher.update.outer_middleware(TracingMiddleware())
dispatcher.update.outer_middleware(dispatcher.fsm)

dispatcher.include_router(chat_membership_router)
dispatcher.include_router(start.router)
dispatcher.include_router(language.router)
dispatcher.include_router(progress.router)
dispatcher.include_router(reset.router)
dispatcher.include_router(topics.router)
dispatcher.include_router(reminders.router)
dispatcher.include_router(wiederholen.router)
dispatcher.include_router(lesson_recall.router)
# Last, because it takes every message that the routers above don't
dispatcher.include_router(fallback.router)

__all__ = ["dispatcher"]
