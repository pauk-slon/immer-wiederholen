import os
from pathlib import Path

from aiogram import Bot
from anthropic import AsyncAnthropic

from wiederholen.tutoring import Course

from .feature_flags import parse_feature_flags
from .redis_storage import ScanningRedisStorage


def load_storage() -> ScanningRedisStorage:
    return ScanningRedisStorage.from_url(os.environ["FSM_STORAGE_URL"])


def load_feature_flags() -> dict[str, frozenset[int]]:
    return parse_feature_flags(os.environ.get("FEATURE_FLAGS", ""))


def load_anthropic_client() -> AsyncAnthropic | None:
    # Unlike BOT_TOKEN, not required at startup: AI mode is opt-in per chat
    # (see feature_flags) and only the flag-gated test chat needs it, so a
    # normal deployment without ANTHROPIC_API_KEY set still starts cleanly.
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    return AsyncAnthropic(api_key=api_key)


def load_authoring_guide() -> str | None:
    # Optional, same reasoning as topics.yaml's absence (see wiederholen.
    # tutoring.curriculum): without it, shadow-exercise generation just runs
    # on few-shot examples alone rather than failing to start.
    guide_path = os.environ.get("AUTHORING_GUIDE_PATH")
    if not guide_path:
        return None
    return Path(guide_path).read_text()


def load_bot_course_and_storage() -> tuple[Bot, Course, ScanningRedisStorage]:
    token = os.environ["BOT_TOKEN"]
    course = Course.load(Path(os.environ.get("COURSE_PATH", "data")))
    bot = Bot(token=token)
    return bot, course, load_storage()
