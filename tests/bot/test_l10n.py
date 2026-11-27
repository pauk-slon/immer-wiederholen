from datetime import UTC, datetime, timedelta

import pytest

from wiederholen.bot.l10n import (
    LOCALES,
    RU,
    append_streak_line,
    format_count,
    format_score,
    format_wait,
)
from wiederholen.school import Language, Streak


@pytest.mark.parametrize(
    ("n", "expected"),
    [
        (0, "0 слов"),
        (1, "1 слово"),
        (2, "2 слова"),
        (3, "3 слова"),
        (4, "4 слова"),
        (5, "5 слов"),
        (10, "10 слов"),
        (11, "11 слов"),
        (12, "12 слов"),
        (14, "14 слов"),
        (21, "21 слово"),
        (22, "22 слова"),
        (25, "25 слов"),
        (100, "100 слов"),
        (101, "101 слово"),
        (111, "111 слов"),
        (122, "122 слова"),
    ],
)
def test_format_count_ru_words(n: int, expected: str) -> None:
    assert format_count(n, "words", "ru") == expected


@pytest.mark.parametrize(
    ("n", "expected"),
    [
        (1, "1 задание"),
        (2, "2 задания"),
        (5, "5 заданий"),
        (11, "11 заданий"),
        (21, "21 задание"),
    ],
)
def test_format_count_ru_exercises(n: int, expected: str) -> None:
    assert format_count(n, "exercises", "ru") == expected


@pytest.mark.parametrize(
    ("n", "expected"),
    [
        (0, "0 words"),
        (1, "1 word"),
        (2, "2 words"),
        (11, "11 words"),
        (21, "21 words"),
    ],
)
def test_format_count_en_words(n: int, expected: str) -> None:
    assert format_count(n, "words", "en") == expected


@pytest.mark.parametrize(
    ("n", "expected"),
    [
        (1, "1 exercise"),
        (2, "2 exercises"),
        (0, "0 exercises"),
    ],
)
def test_format_count_en_exercises(n: int, expected: str) -> None:
    assert format_count(n, "exercises", "en") == expected


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        (1, "1 из 1 задания"),
        (2, "1 из 2 заданий"),
        (5, "1 из 5 заданий"),
        (11, "1 из 11 заданий"),
        (21, "1 из 21 задания"),
    ],
)
def test_format_score_ru(size: int, expected: str) -> None:
    assert format_score(1, size, "ru") == expected


@pytest.mark.parametrize(
    ("size", "expected"),
    [(1, "1 of 1 exercise"), (2, "1 of 2 exercises")],
)
def test_format_score_en(size: int, expected: str) -> None:
    assert format_score(1, size, "en") == expected


@pytest.mark.parametrize("language", sorted(LOCALES))
def test_the_summaries_of_a_lesson_and_a_lesson_recall_differ(
    language: Language,
) -> None:
    locale = LOCALES[language]
    assert (
        locale.lesson_summary.split("{")[0]
        != (locale.lesson_recall_summary.split("{")[0])
    )


def test_append_streak_line_leaves_the_text_without_a_streak() -> None:
    assert append_streak_line("text", None, "ru", RU.streak_text) == "text"


@pytest.mark.parametrize(
    ("breaks_in", "hours"),
    [
        (timedelta(hours=10, minutes=1), 11),
        (timedelta(minutes=1), 1),
        # breaks_at passed between streak() and this call
        (timedelta(seconds=-1), 1),
    ],
)
def test_append_streak_line_rounds_the_hours_up_to_at_least_one(
    breaks_in: timedelta, hours: int
) -> None:
    streak = Streak(days=3, breaks_at=datetime.now(UTC) + breaks_in)

    text = append_streak_line("text", streak, "ru", RU.reminder_streak_text)

    assert text == "text\n\n" + RU.reminder_streak_text.format(
        days="3 дня", hours=hours
    )


@pytest.mark.parametrize(
    ("seconds", "language", "expected"),
    [
        (10, "ru", "1 мин"),
        (40 * 60, "ru", "40 мин"),
        (40 * 60 + 1, "ru", "41 мин"),
        (61 * 60, "ru", "61 мин"),
        (119 * 60, "ru", "119 мин"),
        (119 * 60 + 1, "ru", "2 ч"),
        (3 * 3600, "ru", "3 ч"),
        (3 * 3600 + 1, "ru", "4 ч"),
        (40 * 60, "en", "40 min"),
        (23 * 3600, "en", "23 h"),
    ],
)
def test_format_wait_rounds_up(
    seconds: float, language: Language, expected: str
) -> None:
    assert format_wait(seconds, language) == expected
