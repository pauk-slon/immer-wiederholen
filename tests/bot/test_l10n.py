import pytest

from wiederholen.bot.l10n import format_count


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
        (1, "1 упражнение"),
        (2, "2 упражнения"),
        (5, "5 упражнений"),
        (11, "11 упражнений"),
        (21, "21 упражнение"),
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
