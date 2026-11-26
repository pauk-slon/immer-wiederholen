from typing import Any, Final

LESSON_SIZE_OPTIONS: Final = (5, 7)
DEFAULT_LESSON_SIZE: Final = 5


def get_lesson_size(state: dict[str, Any]) -> int:
    # An option dropped since the learner picked it, or garbage, falls back
    # to the default
    size = state.get("lesson_size")
    if size in LESSON_SIZE_OPTIONS:
        return size
    return DEFAULT_LESSON_SIZE
