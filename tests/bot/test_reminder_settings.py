from datetime import timedelta

from wiederholen.bot.reminder_settings import get_remind_after


def test_defaults_to_24h_when_never_chosen() -> None:
    assert get_remind_after({}) == timedelta(hours=24)


def test_returns_the_chosen_interval() -> None:
    assert get_remind_after({"remind_after_hours": 4}) == timedelta(hours=4)


def test_returns_none_when_turned_off() -> None:
    assert get_remind_after({"remind_after_hours": 0}) is None


def test_falls_back_to_the_default_for_an_unoffered_value() -> None:
    assert get_remind_after({"remind_after_hours": 5}) == timedelta(hours=24)
