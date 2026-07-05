from contextlib import contextmanager, AbstractContextManager
from pathlib import Path
from typing import Any, Generator, Callable

import pytest
import yaml

from wiederholen.exercises import Mark, RecallMode, School, load_exercises

from .plugins.exercises import make_exercise, make_exercise_data


type TmpYamlFile = Callable[[Any], AbstractContextManager[Path]]


@pytest.fixture
def tmp_yaml_file(tmp_path: Path) -> TmpYamlFile:
    @contextmanager
    def factory(data: Any, *, filename: str = "data.yaml") -> Generator[Path]:
        text = yaml.safe_dump(data)
        yaml_file = tmp_path / filename
        yaml_file.write_text(text)
        yield yaml_file
        yaml_file.unlink(missing_ok=True)

    return factory


def test_ask_prefers_higher_weight_topic() -> None:
    exercises = [make_exercise(topic="warten"), make_exercise(topic="hoffen")]
    state = {"topic_weights": {"warten": 1000.0, "hoffen": 1.0}}
    teacher = School(exercises)(state)
    counts: dict[str, int] = {"warten": 0, "hoffen": 0}
    for _ in range(200):
        counts[teacher.ask().topic] += 1
    assert counts["warten"] > counts["hoffen"]


def test_wrong_answer_doubles_topic_weight() -> None:
    exercise = make_exercise(topic="warten", answer="auf")
    state: dict = {}
    School([exercise])(state).check_answer(exercise, "für")
    assert state["topic_weights"]["warten"] == 2.0


def test_correct_answer_halves_topic_weight() -> None:
    exercise = make_exercise(topic="warten", answer="auf")
    state = {"topic_weights": {"warten": 4.0}}
    School([exercise])(state).check_answer(exercise, "auf")
    assert state["topic_weights"]["warten"] == 2.0


def test_topic_weight_not_below_one() -> None:
    exercise = make_exercise(topic="warten", answer="auf")
    state = {"topic_weights": {"warten": 1.0}}
    School([exercise])(state).check_answer(exercise, "auf")
    assert state["topic_weights"]["warten"] == 1.0


def test_check_returns_none_recall_without_recall_field() -> None:
    exercise = make_exercise(answer="auf", recall=False)
    assert School([exercise])({}).check_answer(exercise, "auf") == Mark(
        correct=True, recall=RecallMode.none
    )


def test_check_returns_required_recall_on_wrong_answer_with_recall() -> None:
    exercise = make_exercise(answer="auf", recall=True)
    assert School([exercise])({}).check_answer(exercise, "für") == Mark(
        correct=False, recall=RecallMode.required
    )


def test_check_returns_optional_recall_on_correct_answer_with_recall() -> None:
    exercise = make_exercise(answer="auf", recall=True)
    assert School([exercise])({}).check_answer(exercise, "auf") == Mark(
        correct=True, recall=RecallMode.optional
    )


class TestExerciseValidation:
    def test_answer_in_distractors_raises(self, tmp_yaml_file: TmpYamlFile) -> None:
        exercise_data = make_exercise_data()
        exercise_data["distractors"][0] = exercise_data["answer"]
        with pytest.raises(ValueError, match="must not be in distractors"):
            with tmp_yaml_file([exercise_data]) as exercise_file:
                load_exercises(exercise_file)

    def test_wrong_explanation_keys_raises(self, tmp_yaml_file: TmpYamlFile) -> None:
        with pytest.raises(ValueError, match="explanation must have keys"):
            with tmp_yaml_file(
                [make_exercise_data() | {"explanation": {"de": "falsch"}}]
            ) as exercise_file:
                load_exercises(exercise_file)


class TestRecallValidation:
    def test_empty_answer_raises(self, tmp_yaml_file: TmpYamlFile) -> None:
        data = make_exercise_data(recall=True)
        data["recall"]["answer"] = []
        with pytest.raises(ValueError, match="recall.answer must not be empty"):
            with tmp_yaml_file([data]) as exercises_file:
                load_exercises(exercises_file)

    def test_invalid_hint_keys_raises(self, tmp_yaml_file: TmpYamlFile) -> None:
        data = make_exercise_data(recall=True)
        invalid_hint_recall_data = data["recall"] | {"hint": {"de": "falsch"}}
        with pytest.raises(ValueError, match="recall.hint keys must be a subset"):
            with tmp_yaml_file(
                [data | {"recall": invalid_hint_recall_data}]
            ) as exercises_file:
                load_exercises(exercises_file)
