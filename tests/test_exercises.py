from wiederholen.exercises import School

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


def test_check_returns_true_on_correct_answer() -> None:
    exercise = make_exercise(answer="auf")
    assert School([exercise])({}).check_answer(exercise, "auf") is True


def test_check_returns_false_on_wrong_answer() -> None:
    exercise = make_exercise(answer="auf")
    assert School([exercise])({}).check_answer(exercise, "für") is False
