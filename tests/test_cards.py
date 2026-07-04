from wiederholen.cards import School

from .conftest import make_card


def test_ask_prefers_higher_weight_topic() -> None:
    cards = [make_card("warten"), make_card("hoffen")]
    state = {"topic_weights": {"warten": 1000.0, "hoffen": 1.0}}
    teacher = School(cards)(state)
    counts: dict[str, int] = {"warten": 0, "hoffen": 0}
    for _ in range(200):
        counts[teacher.ask().topic] += 1
    assert counts["warten"] > counts["hoffen"]


def test_wrong_answer_doubles_topic_weight() -> None:
    card = make_card("warten", answer="auf")
    state: dict = {}
    School([card])(state).check_answer(card, "für")
    assert state["topic_weights"]["warten"] == 2.0


def test_correct_answer_halves_topic_weight() -> None:
    card = make_card("warten", answer="auf")
    state = {"topic_weights": {"warten": 4.0}}
    School([card])(state).check_answer(card, "auf")
    assert state["topic_weights"]["warten"] == 2.0


def test_topic_weight_not_below_one() -> None:
    card = make_card("warten", answer="auf")
    state = {"topic_weights": {"warten": 1.0}}
    School([card])(state).check_answer(card, "auf")
    assert state["topic_weights"]["warten"] == 1.0


def test_check_returns_true_on_correct_answer() -> None:
    card = make_card(answer="auf")
    assert School([card])({}).check_answer(card, "auf") is True


def test_check_returns_false_on_wrong_answer() -> None:
    card = make_card(answer="auf")
    assert School([card])({}).check_answer(card, "für") is False
