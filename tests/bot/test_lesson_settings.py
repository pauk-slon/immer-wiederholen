from wiederholen.bot.lesson_settings import get_lesson_size


def test_defaults_to_5_when_never_chosen() -> None:
    assert get_lesson_size({}) == 5


def test_returns_the_chosen_size() -> None:
    assert get_lesson_size({"lesson_size": 7}) == 7


def test_falls_back_to_the_default_for_an_unoffered_value() -> None:
    assert get_lesson_size({"lesson_size": 10}) == 5
