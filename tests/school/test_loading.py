from pathlib import Path

import pytest

from tests.conftest import TmpYamlFile
from tests.plugins.curriculum import make_exercise, make_exercise_data
from wiederholen.school.curriculum import Course, Exercise, TopicGroup


class TestExerciseValidation:
    def test_answer_in_distractors_raises(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        exercise_data = make_exercise_data()
        exercise_data["distractors"][0] = "auf"
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

    def test_single_answer_loads_as_a_list(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        with tmp_yaml_file(
            [make_exercise_data(answer="auf")], filename="exercises.yaml"
        ):
            course = Course.load(tmp_path)
        assert course.exercises[0].answer == ["auf"]

    def test_several_answers_load(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        exercise_data = make_exercise_data(answer=["Komm", "Komme"], distractors=[])
        with tmp_yaml_file([exercise_data], filename="exercises.yaml"):
            course = Course.load(tmp_path)
        assert course.exercises[0].answer == ["Komm", "Komme"]

    def test_empty_answer_raises(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        with (
            pytest.raises(ValueError, match="answer must not be empty"),
            tmp_yaml_file([make_exercise_data(answer=[])], filename="exercises.yaml"),
        ):
            Course.load(tmp_path)

    def test_repeated_answer_raises(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        with (
            pytest.raises(ValueError, match="must not repeat an answer"),
            tmp_yaml_file(
                [make_exercise_data(answer=["auf", "auf"])],
                filename="exercises.yaml",
            ),
        ):
            Course.load(tmp_path)

    def test_answers_differing_only_in_case_raise(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        with (
            pytest.raises(ValueError, match="must not repeat an answer"),
            tmp_yaml_file(
                [make_exercise_data(answer=["Komm", "komm "], distractors=[])],
                filename="exercises.yaml",
            ),
        ):
            Course.load(tmp_path)

    def test_second_answer_in_distractors_raises(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        with (
            pytest.raises(ValueError, match="must not be in distractors"),
            tmp_yaml_file(
                [make_exercise_data(answer=["auf", "für"], distractors=["für", "an"])],
                filename="exercises.yaml",
            ),
        ):
            Course.load(tmp_path)

    def test_another_order_of_the_word_bank_loads(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        exercise_data = make_exercise_data(
            answer=["heute kommt er", "er kommt heute"], distractors=[]
        ) | {"word_bank": ["heute", "kommt", "er"]}
        with tmp_yaml_file([exercise_data], filename="exercises.yaml"):
            course = Course.load(tmp_path)
        assert course.exercises[0].answer == ["heute kommt er", "er kommt heute"]

    def test_answer_that_splits_a_word_bank_chunk_raises(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        exercise_data = make_exercise_data(
            answer=["sie wohnt in Hamburg", "in sie wohnt Hamburg"], distractors=[]
        ) | {"word_bank": ["sie", "wohnt", "in Hamburg"]}
        with (
            pytest.raises(ValueError, match="must be an order of word_bank"),
            tmp_yaml_file([exercise_data], filename="exercises.yaml"),
        ):
            Course.load(tmp_path)

    def test_single_answer_is_saved_as_a_string(self) -> None:
        # An older version can read it back after a rollback
        assert make_exercise(answer="auf").to_dict()["answer"] == "auf"

    def test_several_answers_are_saved_as_a_list(self) -> None:
        exercise = make_exercise(answer=["Komm", "Komme"], distractors=[])
        assert Exercise.from_dict(exercise.to_dict()) == exercise

    def test_exercise_saved_with_a_single_answer_string_loads(self) -> None:
        # Also an exercise in FSM or web session data saved before answer became
        # a list
        exercise = make_exercise(answer="auf")
        assert Exercise.from_dict(exercise.to_dict()) == exercise


def _grouped(topics: dict) -> dict:
    return {"group": {"title": {"ru": "Группа", "en": "Group"}, "topics": topics}}


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
        assert course.topic_groups == {}

    def test_loads_chains_and_gates(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        data = {
            "partizip_ii": {
                "chains": ["preteritum"],
                "gates": ["partizip_ii_meaning"],
            },
            "partizip_ii_meaning": None,
        }
        with (
            tmp_yaml_file([], filename="exercises.yaml"),
            tmp_yaml_file(_grouped(data), filename="topics.yaml"),
        ):
            course = Course.load(tmp_path)
        assert course.word_chained_topics["partizip_ii"] == [
            "preteritum",
            "partizip_ii_meaning",
        ]
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
            tmp_yaml_file(_grouped(data), filename="topics.yaml"),
        ):
            course = Course.load(tmp_path)
        assert course.answer_chained_topics == {
            "government": ["preposition_meaning", "preposition_case"],
        }
        assert course.word_chained_topics["government"] == []
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
            tmp_yaml_file(_grouped(data), filename="topics.yaml"),
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
            tmp_yaml_file(_grouped(data), filename="topics.yaml"),
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
            tmp_yaml_file(_grouped(data), filename="topics.yaml"),
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
            tmp_yaml_file(_grouped(data), filename="topics.yaml"),
        ):
            course = Course.load(tmp_path)
        assert course.ai_generatable_topics == frozenset()

    def test_loads_topic_groups(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        data = {
            "verb_forms": {
                "title": {"ru": "Формы глаголов", "en": "Verb forms"},
                "topics": {
                    "partizip_ii": {"gates": ["partizip_ii_meaning"]},
                    "partizip_ii_meaning": None,
                },
            },
            "cases": {
                "title": {"ru": "Падежи", "en": "Cases"},
                "topics": {"verb_case": None},
            },
        }
        with (
            tmp_yaml_file([], filename="exercises.yaml"),
            tmp_yaml_file(data, filename="topics.yaml"),
        ):
            course = Course.load(tmp_path)
        assert list(course.topic_groups) == ["verb_forms", "cases"]
        assert course.topic_groups["verb_forms"] == TopicGroup(
            title={"ru": "Формы глаголов", "en": "Verb forms"},
            topics=frozenset({"partizip_ii", "partizip_ii_meaning"}),
        )
        assert course.topic_groups["cases"].topics == frozenset({"verb_case"})
        assert course.gated_topics == frozenset({"partizip_ii_meaning"})

    def test_wrong_group_title_keys_raises(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        data = {"group": {"title": {"de": "Gruppe"}, "topics": {"verb_case": None}}}
        with (
            pytest.raises(ValueError, match="title must have keys"),
            tmp_yaml_file([], filename="exercises.yaml"),
            tmp_yaml_file(data, filename="topics.yaml"),
        ):
            Course.load(tmp_path)

    def test_topic_in_two_groups_raises(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        title = {"ru": "Группа", "en": "Group"}
        data = {
            "first": {"title": title, "topics": {"verb_case": None}},
            "second": {"title": title, "topics": {"verb_case": None}},
        }
        with (
            pytest.raises(ValueError, match="is in both 'first' and 'second'"),
            tmp_yaml_file([], filename="exercises.yaml"),
            tmp_yaml_file(data, filename="topics.yaml"),
        ):
            Course.load(tmp_path)

    def test_gated_topic_in_another_group_raises(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        title = {"ru": "Группа", "en": "Group"}
        data = {
            "forms": {
                "title": title,
                "topics": {"partizip_ii": {"gates": ["partizip_ii_meaning"]}},
            },
            "meanings": {"title": title, "topics": {"partizip_ii_meaning": None}},
        }
        with (
            pytest.raises(ValueError, match="must be in the same group"),
            tmp_yaml_file([], filename="exercises.yaml"),
            tmp_yaml_file(data, filename="topics.yaml"),
        ):
            Course.load(tmp_path)

    def test_chain_into_another_group_loads(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        title = {"ru": "Группа", "en": "Group"}
        data = {
            "governance": {
                "title": title,
                "topics": {
                    "verb_preposition": {"chains_by_answer": ["preposition_case"]}
                },
            },
            "prepositions": {"title": title, "topics": {"preposition_case": None}},
        }
        with (
            tmp_yaml_file([], filename="exercises.yaml"),
            tmp_yaml_file(data, filename="topics.yaml"),
        ):
            course = Course.load(tmp_path)
        assert course.answer_chained_topics == {
            "verb_preposition": ["preposition_case"]
        }


class TestRecallValidation:
    def test_single_answer_loads_as_a_list(
        self,
        tmp_path: Path,
        tmp_yaml_file: TmpYamlFile,
    ) -> None:
        data = make_exercise_data(recalls=True)
        data["recalls"][0] |= {"answer": "Ich warte auf den Bus."}
        with tmp_yaml_file([data], filename="exercises.yaml"):
            course = Course.load(tmp_path)
        assert course.exercises[0].recalls[0].answer == ["Ich warte auf den Bus."]

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
