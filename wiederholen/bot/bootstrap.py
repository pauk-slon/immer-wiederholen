import os
from pathlib import Path

from aiogram import Bot

from wiederholen.exercises import School, load_exercises

from .redis_storage import ScanningRedisStorage


def load_storage() -> ScanningRedisStorage:
    return ScanningRedisStorage.from_url(os.environ["FSM_STORAGE_URL"])


def load_bot_school_and_storage() -> tuple[Bot, School, ScanningRedisStorage]:
    token = os.environ["BOT_TOKEN"]
    exercises_path = Path(os.environ.get("EXERCISES_PATH", "data/exercises.yaml"))
    school = School(load_exercises(exercises_path))
    bot = Bot(token=token)
    return bot, school, load_storage()
