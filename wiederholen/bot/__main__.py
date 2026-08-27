import asyncio
import logging

from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import BotCommand

from wiederholen.tracing import configure_tracing, instrument_redis

from . import dispatcher
from .bootstrap import (
    load_anthropic_client,
    load_authoring_guide,
    load_bot_course_and_storage,
    load_cue_store,
    load_feature_flags,
)
from .l10n import LOCALES

logger = logging.getLogger(__name__)


async def main() -> None:
    configure_tracing()
    instrument_redis()
    bot, course, storage, student_record_book = load_bot_course_and_storage()
    feature_flags = load_feature_flags()
    anthropic_client = load_anthropic_client()
    authoring_guide = load_authoring_guide()
    cue_store = load_cue_store()
    dispatcher.fsm.storage = storage
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
                    BotCommand(command="progress", description=locale.cmd_progress),
                    BotCommand(command="language", description=locale.cmd_language),
                    BotCommand(command="reset", description=locale.cmd_reset),
                ],
                language_code=language_code,
            )
        except TelegramRetryAfter as e:
            logger.warning(
                "Rate limited setting bot info, skipping: retry in %ds",
                e.retry_after,
            )
    await dispatcher.start_polling(
        bot,
        course=course,
        student_record_book=student_record_book,
        feature_flags=feature_flags,
        anthropic_client=anthropic_client,
        authoring_guide=authoring_guide,
        cue_store=cue_store,
    )


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
