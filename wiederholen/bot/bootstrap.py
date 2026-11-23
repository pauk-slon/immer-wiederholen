import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from aiogram import Bot
from aiogram.fsm.storage.redis import RedisStorage
from anthropic import AsyncAnthropic

from wiederholen.school import (
    CachedCueStore,
    Course,
    CueStore,
    Language,
    R2CueStore,
    RedisStudentIdentityStore,
    RedisStudentRecordBook,
    StudentIdentityStore,
    StudentRecordBook,
)

from .feature_flags import LESSON_RECALL_UNLIMITED_FLAG, parse_feature_flags


@dataclass(frozen=True)
class BotInfo:
    name: str
    description: str
    short_description: str


def load_student_record_book() -> StudentRecordBook:
    return RedisStudentRecordBook.from_url(os.environ["STUDENT_RECORD_STORAGE_URL"])


def load_student_identity_store() -> StudentIdentityStore:
    return RedisStudentIdentityStore.from_url(
        os.environ["STUDENT_IDENTITY_STORAGE_URL"]
    )


def load_cue_store() -> CueStore | None:
    # Optional, same "absence means off" shape as load_anthropic_client():
    # only a deployment that's actually set up R2 needs this, and this
    # project's own local dev/CI runs don't have real R2 credentials.
    account_id = os.environ.get("R2_ACCOUNT_ID")
    if not account_id:
        return None
    return CachedCueStore(
        R2CueStore(
            account_id=account_id,
            access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            bucket=os.environ["R2_BUCKET"],
            public_url_base=os.environ["R2_PUBLIC_URL_BASE"],
        )
    )


def load_feature_flags() -> dict[str, frozenset[int]]:
    return parse_feature_flags(os.environ.get("BOT_FEATURE_FLAGS", ""))


def check_lesson_recall_config(
    feature_flags: dict[str, frozenset[int]],
    anthropic_client: AsyncAnthropic | None,
    course: Course,
) -> None:
    # ANTHROPIC_API_KEY turns on the lesson recall, its only use
    if anthropic_client is None:
        if feature_flags.get(LESSON_RECALL_UNLIMITED_FLAG):
            raise RuntimeError(
                f"the {LESSON_RECALL_UNLIMITED_FLAG} feature flag needs "
                "ANTHROPIC_API_KEY"
            )
        return
    if course.lesson_recall_guide is None:
        raise RuntimeError("ANTHROPIC_API_KEY needs the course's lesson_recall.md")


def load_anthropic_client() -> AsyncAnthropic | None:
    # Optional: without it, the bot has no lesson recall (see
    # check_lesson_recall_config()). Each request sets its own timeout and
    # retries
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    return AsyncAnthropic(api_key=api_key)


def load_bot_info() -> dict[Language, BotInfo] | None:
    # Optional, same as topics.yaml: if bot.yaml's absent, main() just
    # leaves whatever name/description Telegram already has on file.
    path = Path(os.environ.get("COURSE_PATH", "data")) / "bot.yaml"
    if not path.exists():
        return None
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    info = data.get("info") or {}
    return {
        language: BotInfo(
            name=entry["name"],
            description=entry["description"],
            short_description=entry["short_description"],
        )
        for language, entry in info.items()
    }


def load_bot_course_and_storage() -> tuple[
    Bot, Course, RedisStorage, StudentRecordBook, StudentIdentityStore
]:
    # Shared by both wiederholen.bot.__main__.main() (polling bot) and
    # wiederholen.bot.reminder.main() (reminder worker) — both processes need
    # all five: the reminder worker has no aiogram routers of its own, but
    # still does a point lookup into RedisStorage for a chat's language (see
    # wiederholen.bot.reminder), so it can't do without it either.
    token = os.environ["BOT_TOKEN"]
    course = Course.load(Path(os.environ.get("COURSE_PATH", "data")))
    bot = Bot(token=token)
    storage_url = os.environ["BOT_FSM_STORAGE_URL"]
    return (
        bot,
        course,
        RedisStorage.from_url(storage_url),
        load_student_record_book(),
        load_student_identity_store(),
    )
