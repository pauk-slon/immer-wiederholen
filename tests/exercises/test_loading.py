from pathlib import Path

import pytest

from wiederholen.exercises import Course

from tests.conftest import TmpYamlFile
from tests.plugins.exercises import make_exercise_data


class TestExerciseValidation:
    def test_answer_in_distractors_raises(
        self, tmp_path: Path, tmp_yaml_file: TmpYamlFile
    ) -> None:
        exercise_data = make_exercise_data()
        exercise_data["distractors"][0] = exercise_data["answer"]
        with pytest.raises(ValueError, match="must not be in distractors"):
            with tmp_yaml_file([exercise_data], filename="exercises.yaml"):
                Course.load(tmp_path)

    def test_wrong_explanation_keys_raises(
        self, tmp_path: Path, tmp_yaml_file: TmpYamlFile
    ) -> None:
        with pytest.raises(ValueError, match="explanation must have keys"):
            with tmp_yaml_file(
                [make_exercise_data() | {"explanation": {"de": "falsch"}}],
                filename="exercises.yaml",
            ):
                Course.load(tmp_path)

    def test_wrong_description_keys_raises(
        self, tmp_path: Path, tmp_yaml_file: TmpYamlFile
    ) -> None:
        with pytest.raises(ValueError, match="description must have keys"):
            with tmp_yaml_file(
                [make_exercise_data() | {"description": {"de": "falsch"}}],
                filename="exercises.yaml",
            ):
                Course.load(tmp_path)


class TestChainedTopicsLoading:
    def test_missing_file_returns_empty_dict(
        self, tmp_path: Path, tmp_yaml_file: TmpYamlFile
    ) -> None:
        with tmp_yaml_file([], filename="exercises.yaml"):
            course = Course.load(tmp_path)
        assert course.chained_topics == {}

    def test_loads_file_contents(
        self, tmp_path: Path, tmp_yaml_file: TmpYamlFile
    ) -> None:
        data = {"preposition_case": ["preposition_meaning"]}
        with tmp_yaml_file([], filename="exercises.yaml"):
            with tmp_yaml_file(data, filename="chained_categories.yaml"):
                course = Course.load(tmp_path)
        assert course.chained_topics == data

    def test_empty_file_returns_empty_dict(
        self, tmp_path: Path, tmp_yaml_file: TmpYamlFile
    ) -> None:
        with tmp_yaml_file([], filename="exercises.yaml"):
            with tmp_yaml_file(None, filename="chained_categories.yaml"):
                course = Course.load(tmp_path)
        assert course.chained_topics == {}


class TestRecallValidation:
    def test_empty_answer_raises(
        self, tmp_path: Path, tmp_yaml_file: TmpYamlFile
    ) -> None:
        data = make_exercise_data(recalls=True)
        data["recalls"][0]["answer"] = []
        with pytest.raises(ValueError, match="recall.answer must not be empty"):
            with tmp_yaml_file([data], filename="exercises.yaml"):
                Course.load(tmp_path)

    def test_invalid_hint_keys_raises(
        self, tmp_path: Path, tmp_yaml_file: TmpYamlFile
    ) -> None:
        data = make_exercise_data(recalls=True)
        invalid_hint_recall_data = data["recalls"][0] | {"hint": {"de": "falsch"}}
        with pytest.raises(ValueError, match="recall.hint keys must be a subset"):
            with tmp_yaml_file(
                [data | {"recalls": [invalid_hint_recall_data]}],
                filename="exercises.yaml",
            ):
                Course.load(tmp_path)
