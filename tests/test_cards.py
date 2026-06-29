from wiederholen.cards import Card, School


def make_card(topic: str = "warten", answer: str = "auf") -> Card:
    return Card(
        question=f"Ich ___ {topic}.",
        topic=topic,
        distractors=["für", "an", "um"],
        answer=answer,
        explanation={"ru": f"{topic} + Akk", "en": f"{topic} + Acc"},
    )


def test_ask_returns_card_from_list() -> None:
    cards = [make_card("warten"), make_card("hoffen")]
    assert School(cards)({}).ask() in cards


def test_ask_with_single_card() -> None:
    card = make_card()
    assert School([card])({}).ask() is card


def test_ask_prefers_higher_weight_topic() -> None:
    warten = make_card("warten")
    hoffen = make_card("hoffen")
    state = {"topic_weights": {"warten": 1000.0, "hoffen": 1.0}}
    teacher = School([warten, hoffen])(state)
    counts: dict[str, int] = {"warten": 0, "hoffen": 0}
    for _ in range(200):
        counts[teacher.ask().topic] += 1
    assert counts["warten"] > counts["hoffen"]


def test_wrong_answer_doubles_topic_weight() -> None:
    card = make_card("warten", answer="auf")
    state: dict = {}
    School([card])(state).check(card, "für")
    assert state["topic_weights"]["warten"] == 2.0


def test_correct_answer_halves_topic_weight() -> None:
    card = make_card("warten", answer="auf")
    state = {"topic_weights": {"warten": 4.0}}
    School([card])(state).check(card, "auf")
    assert state["topic_weights"]["warten"] == 2.0


def test_topic_weight_not_below_one() -> None:
    card = make_card("warten", answer="auf")
    state = {"topic_weights": {"warten": 1.0}}
    School([card])(state).check(card, "auf")
    assert state["topic_weights"]["warten"] == 1.0


def test_check_returns_true_on_correct_answer() -> None:
    card = make_card(answer="auf")
    assert School([card])({}).check(card, "auf") is True


def test_check_returns_false_on_wrong_answer() -> None:
    card = make_card(answer="auf")
    assert School([card])({}).check(card, "für") is False
