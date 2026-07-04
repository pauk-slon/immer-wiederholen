from wiederholen.exercises import Mark, School

from .conftest import make_exercise


def test_ask_prefers_higher_weight_topic() -> None:
    exercises = [make_exercise("warten"), make_exercise("hoffen")]
    state = {"topic_weights": {"warten": 1000.0, "hoffen": 1.0}}
    teacher = School(exercises)(state)
    counts: dict[str, int] = {"warten": 0, "hoffen": 0}
    for _ in range(200):
        counts[teacher.ask().topic] += 1
    assert counts["warten"] > counts["hoffen"]


def test_wrong_answer_doubles_topic_weight() -> None:
    exercise = make_exercise("warten", answer="auf")
    state: dict = {}
    School([exercise])(state).check_answer(exercise, "für")
    assert state["topic_weights"]["warten"] == 2.0


def test_correct_answer_halves_topic_weight() -> None:
    exercise = make_exercise("warten", answer="auf")
    state = {"topic_weights": {"warten": 4.0}}
    School([exercise])(state).check_answer(exercise, "auf")
    assert state["topic_weights"]["warten"] == 2.0


def test_topic_weight_not_below_one() -> None:
    exercise = make_exercise("warten", answer="auf")
    state = {"topic_weights": {"warten": 1.0}}
    School([exercise])(state).check_answer(exercise, "auf")
    assert state["topic_weights"]["warten"] == 1.0


def test_check_returns_correct_mark_on_right_answer() -> None:
    exercise = make_exercise(answer="auf")
    assert School([exercise])({}).check_answer(exercise, "auf") == Mark(
        correct=True, show_recall=False
    )


def test_check_returns_correct_mark_on_wrong_answer() -> None:
    exercise = make_exercise(answer="auf")
    assert School([exercise])({}).check_answer(exercise, "für") == Mark(
        correct=False, show_recall=False
    )


def test_check_sets_show_recall_when_exercise_has_recall() -> None:
    exercise = make_exercise(
        answer="auf",
        recall="Ich ___ (der Bus).",
        recall_answer=["Ich warte auf den Bus."],
    )
    assert School([exercise])({}).check_answer(exercise, "für") == Mark(
        correct=False, show_recall=True
    )
