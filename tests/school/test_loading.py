from pathlib import Path

import pytest

from tests.conftest import TmpYamlFile
from tests.plugins.curriculum import make_exercise_data
from wiederholen.school.curriculum import Course


class TestExerciseValidation:
    def test_answer_in_distractors_raises(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        exercise_data = make_exercise_data()
        exercise_data["distractors"][0] = exercise_data["answer"]
        with (
            pytest.raises(ValueError, match="must not be in distractors"),
            tmp_yaml_file([exercise_data], filename="exercises.yaml"),
        ):
            Course.load(tmp_path)

    def test_wrong_explanation_keys_raises(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        with (
            pytest.raises(ValueError, match="explanation must have keys"),
            tmp_yaml_file(
                [make_exercise_data() | {"explanation": {"de": "falsch"}}],
                filename="exercises.yaml",
            ),
        ):
            Course.load(tmp_path)

    def test_wrong_description_keys_raises(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        with (
            pytest.raises(ValueError, match="description must have keys"),
            tmp_yaml_file(
                [make_exercise_data() | {"description": {"de": "falsch"}}],
                filename="exercises.yaml",
            ),
        ):
            Course.load(tmp_path)

    def test_word_bank_not_joining_into_answer_raises(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        with (
            pytest.raises(ValueError, match="must join into answer"),
            tmp_yaml_file(
                [make_exercise_data() | {"word_bank": ["nicht", "auf"]}],
                filename="exercises.yaml",
            ),
        ):
            Course.load(tmp_path)

    def test_matching_word_bank_loads(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        exercise_data = make_exercise_data(answer="sie wohnt in Hamburg") | {
            "word_bank": ["sie", "wohnt", "in Hamburg"]
        }
        with tmp_yaml_file([exercise_data], filename="exercises.yaml"):
            course = Course.load(tmp_path)
        assert course.exercises[0].word_bank == ["sie", "wohnt", "in Hamburg"]


class TestTopicsConfigLoading:
    def test_missing_file_returns_empty(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        with tmp_yaml_file([], filename="exercises.yaml"):
            course = Course.load(tmp_path)
        assert course.word_chained_topics == {}
        assert course.gated_topics == frozenset()
        assert course.answer_chained_topics == {}
        assert course.topic_instructions == {}
        assert course.ai_generatable_topics == frozenset()
        assert course.cue_generatable_topics == frozenset()

    def test_loads_chains_and_gates(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        data = {
            "partizip_ii": {
                "chains": ["preteritum"],
                "gates": ["partizip_ii_meaning"],
            }
        }
        with (
            tmp_yaml_file([], filename="exercises.yaml"),
            tmp_yaml_file(data, filename="topics.yaml"),
        ):
            course = Course.load(tmp_path)
        assert course.word_chained_topics == {
            "partizip_ii": ["preteritum", "partizip_ii_meaning"]
        }
        assert course.gated_topics == frozenset({"partizip_ii_meaning"})

    def test_loads_chains_by_answer(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        data = {
            "government": {
                "chains_by_answer": ["preposition_meaning", "preposition_case"],
            }
        }
        with (
            tmp_yaml_file([], filename="exercises.yaml"),
            tmp_yaml_file(data, filename="topics.yaml"),
        ):
            course = Course.load(tmp_path)
        assert course.answer_chained_topics == {
            "government": ["preposition_meaning", "preposition_case"],
        }
        assert course.word_chained_topics == {"government": []}
        assert course.gated_topics == frozenset()

    def test_empty_file_returns_empty(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        with (
            tmp_yaml_file([], filename="exercises.yaml"),
            tmp_yaml_file(None, filename="topics.yaml"),
        ):
            course = Course.load(tmp_path)
        assert course.word_chained_topics == {}
        assert course.gated_topics == frozenset()
        assert course.answer_chained_topics == {}
        assert course.topic_instructions == {}
        assert course.ai_generatable_topics == frozenset()
        assert course.cue_generatable_topics == frozenset()

    def test_loads_topic_instructions(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        data = {
            "konjunktion_wortstellung": {
                "instruction": {
                    "ru": "Заполни пропуски в правильном порядке.",
                    "en": "Fill in the blank with the words in the correct order.",
                },
            }
        }
        with (
            tmp_yaml_file([], filename="exercises.yaml"),
            tmp_yaml_file(data, filename="topics.yaml"),
        ):
            course = Course.load(tmp_path)
        assert course.topic_instructions == {
            "konjunktion_wortstellung": {
                "ru": "Заполни пропуски в правильном порядке.",
                "en": "Fill in the blank with the words in the correct order.",
            },
        }

    def test_topic_without_instruction_is_absent(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        data = {"partizip_ii": {"chains": ["preteritum"]}}
        with (
            tmp_yaml_file([], filename="exercises.yaml"),
            tmp_yaml_file(data, filename="topics.yaml"),
        ):
            course = Course.load(tmp_path)
        assert course.topic_instructions == {}

    def test_loads_ai_generation_flag(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        data = {
            "verb_preposition": {"ai_generation": True},
            "partizip_ii": {"chains": ["preteritum"]},
        }
        with (
            tmp_yaml_file([], filename="exercises.yaml"),
            tmp_yaml_file(data, filename="topics.yaml"),
        ):
            course = Course.load(tmp_path)
        assert course.ai_generatable_topics == frozenset({"verb_preposition"})

    def test_ai_generation_false_is_not_included(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        data = {"verb_preposition": {"ai_generation": False}}
        with (
            tmp_yaml_file([], filename="exercises.yaml"),
            tmp_yaml_file(data, filename="topics.yaml"),
        ):
            course = Course.load(tmp_path)
        assert course.ai_generatable_topics == frozenset()

    def test_loads_cue_generation_flag(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        data = {
            "preposition_meaning": {"cue_generation": True},
            "partizip_ii": {"chains": ["preteritum"]},
        }
        with (
            tmp_yaml_file([], filename="exercises.yaml"),
            tmp_yaml_file(data, filename="topics.yaml"),
        ):
            course = Course.load(tmp_path)
        assert course.cue_generatable_topics == frozenset({"preposition_meaning"})

    def test_cue_generation_false_is_not_included(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        data = {"preposition_meaning": {"cue_generation": False}}
        with (
            tmp_yaml_file([], filename="exercises.yaml"),
            tmp_yaml_file(data, filename="topics.yaml"),
        ):
            course = Course.load(tmp_path)
        assert course.cue_generatable_topics == frozenset()


class TestRecallValidation:
    def test_empty_answer_raises(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        data = make_exercise_data(recalls=True)
        data["recalls"][0]["answer"] = []
        with (
            pytest.raises(ValueError, match="recall.answer must not be empty"),
            tmp_yaml_file([data], filename="exercises.yaml"),
        ):
            Course.load(tmp_path)

    def test_invalid_hint_keys_raises(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        data = make_exercise_data(recalls=True)
        invalid_hint_recall_data = data["recalls"][0] | {"hint": {"de": "falsch"}}
        with (
            pytest.raises(ValueError, match="recall.hint keys must be a subset"),
            tmp_yaml_file(
                [data | {"recalls": [invalid_hint_recall_data]}],
                filename="exercises.yaml",
            ),
        ):
            Course.load(tmp_path)
