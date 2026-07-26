import os
from pathlib import Path

from aiogram import Bot

from wiederholen.tutoring import Course

from .redis_storage import ScanningRedisStorage


def load_storage() -> ScanningRedisStorage:
    return ScanningRedisStorage.from_url(os.environ["FSM_STORAGE_URL"])


def load_bot_course_and_storage() -> tuple[Bot, Course, ScanningRedisStorage]:
    token = os.environ["BOT_TOKEN"]
    course = Course.load(Path(os.environ.get("COURSE_PATH", "data")))
    bot = Bot(token=token)
    return bot, course, load_storage()
