from contextlib import AbstractContextManager
from pathlib import Path
from typing import Callable, Any

import pytest

from wiederholen.exercises import load_exercises

from tests.plugins.exercises import make_exercise_data

type TmpYamlFile = Callable[[Any], AbstractContextManager[Path]]


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
