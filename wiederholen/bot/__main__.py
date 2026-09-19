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
    load_bot_info,
    load_feature_flags,
)
from .l10n import LOCALES

logger = logging.getLogger(__name__)


async def main() -> None:
    configure_tracing()
    instrument_redis()
    bot, course, storage, student_record_book, student_identity_store = (
        load_bot_course_and_storage()
    )
    feature_flags = load_feature_flags()
    anthropic_client = load_anthropic_client()
    authoring_guide = load_authoring_guide()
    bot_info_by_language = load_bot_info()
    dispatcher.fsm.storage = storage
    for language_code, locale in LOCALES.items():
        try:
            if bot_info_by_language and (
                bot_info := bot_info_by_language.get(language_code)
            ):
                await bot.set_my_name(bot_info.name, language_code=language_code)
                await bot.set_my_description(
                    bot_info.description, language_code=language_code
                )
                await bot.set_my_short_description(
                    bot_info.short_description, language_code=language_code
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
        student_identity_store=student_identity_store,
        feature_flags=feature_flags,
        anthropic_client=anthropic_client,
        authoring_guide=authoring_guide,
    )


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
