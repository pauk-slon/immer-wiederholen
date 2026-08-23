import os
from pathlib import Path

from aiogram import Bot
from aiogram.fsm.storage.redis import RedisStorage
from anthropic import AsyncAnthropic

from wiederholen.school import Course, RedisStudentRecordBook, StudentRecordBook

from .feature_flags import parse_feature_flags


def load_student_record_book() -> StudentRecordBook:
    return RedisStudentRecordBook.from_url(os.environ["STUDENT_RECORD_STORAGE_URL"])


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
    guide = Path(guide_path).read_text()
    # AUTHORING_GUIDE_PATH points at the content repo's whole CLAUDE.md, but
    # everything from "## Deploying" onward (compose.yaml, DNS, GitHub Pages,
    # ...) is infra documentation, not exercise-writing guidance — irrelevant
    # to shadow-exercise generation, and it references local files/repos the
    # model has no access to anyway. Cut the guide off there, keeping only
    # the Exercises/Recall sections that precede it.
    return guide.split("\n## Deploying", 1)[0]


def load_bot_course_and_storage() -> tuple[
    Bot, Course, RedisStorage, StudentRecordBook
]:
    # Shared by both wiederholen.bot.__main__.main() (polling bot) and
    # wiederholen.bot.reminder.main() (reminder worker) — both processes need
    # all four: the reminder worker has no aiogram routers of its own, but
    # still does a point lookup into RedisStorage for a chat's language (see
    # wiederholen.bot.reminder), so it can't do without it either.
    token = os.environ["BOT_TOKEN"]
    course = Course.load(Path(os.environ.get("COURSE_PATH", "data")))
    bot = Bot(token=token)
    storage_url = os.environ["BOT_FSM_STORAGE_URL"]
    return bot, course, RedisStorage.from_url(storage_url), load_student_record_book()
