from pathlib import Path

import pytest

from wiederholen.bot.bootstrap import load_bot_info
from wiederholen.school.curriculum import Course

DEMO_PATH = Path(__file__).parents[2] / "demo"


@pytest.fixture
def demo_course() -> Course:
    return Course.load(DEMO_PATH)


def test_demo_course_uses_every_exercise_field(demo_course: Course) -> None:
    # The demo doubles as the format's documentation — keep at least one
    # example of each optional field in it.
    exercises = demo_course.exercises
    assert any(exercise.distractors for exercise in exercises)
    assert any(not exercise.distractors for exercise in exercises)
    assert any(len(exercise.answer) > 1 for exercise in exercises)
    assert any(len(exercise.recalls) > 1 for exercise in exercises)
    assert any(recall.hint for exercise in exercises for recall in exercise.recalls)
    assert any(exercise.description for exercise in exercises)
    assert any(exercise.word_bank for exercise in exercises)
    assert any(exercise.grammar_classes for exercise in exercises)


def test_demo_course_uses_every_topics_setting(demo_course: Course) -> None:
    assert len(demo_course.topic_groups) > 1
    assert any(demo_course.word_chained_topics.values())
    assert demo_course.gated_topics
    assert demo_course.answer_chained_topics
    assert demo_course.topic_instructions
    assert demo_course.ai_generatable_topics
    assert demo_course.cue_generatable_topics


def test_demo_course_has_bot_info(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COURSE_PATH", str(DEMO_PATH))
    bot_info = load_bot_info()
    assert bot_info is not None
    assert set(bot_info) == {"ru", "en"}
