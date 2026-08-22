import os
from pathlib import Path

from aiogram import Bot
from anthropic import AsyncAnthropic

from wiederholen.students import StudentStore
from wiederholen.tutoring import Course

from .feature_flags import parse_feature_flags
from .redis_storage import AiogramFsmStorage


def load_student_store() -> StudentStore:
    return StudentStore.from_url(os.environ["FSM_STORAGE_URL"])


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


def load_bot_course_and_storage() -> tuple[Bot, Course, AiogramFsmStorage]:
    token = os.environ["BOT_TOKEN"]
    course = Course.load(Path(os.environ.get("COURSE_PATH", "data")))
    bot = Bot(token=token)
    return bot, course, AiogramFsmStorage(load_student_store())


def load_reminder_course_and_store() -> tuple[Bot, Course, StudentStore]:
    # reminder.py never participates in aiogram's FSM routing — it only ever
    # wanted a plain per-chat dict, not the aiogram-shaped BaseStorage
    # load_bot_course_and_storage() hands the polling bot. Kept separate
    # rather than reusing that function and unwrapping AiogramFsmStorage.store,
    # since reaching into the adapter's internals from here would leak it.
    token = os.environ["BOT_TOKEN"]
    course = Course.load(Path(os.environ.get("COURSE_PATH", "data")))
    bot = Bot(token=token)
    return bot, course, load_student_store()
