from dataclasses import dataclass
from typing import Final, Literal

type Language = Literal["ru", "en"]


@dataclass(frozen=True)
class Locale:
    start: str
    correct: str
    wrong: str
    cmd_start: str
    cmd_wiederholen: str
    cmd_language: str


RU: Final = Locale(
    start="Привет! Я помогу тебе запомнить иностранные слова через интервальное повторение.\n\nИспользуй /wiederholen чтобы начать.",
    correct="✓ Правильно!",
    wrong="✗ Неправильно. Правильный ответ: {answer}",
    cmd_start="Начать",
    cmd_wiederholen="Следующее задание",
    cmd_language="Сменить язык",
)

EN: Final = Locale(
    start="Hi! I'll help you memorize foreign words using spaced repetition.\n\nUse /wiederholen to start.",
    correct="✓ Correct!",
    wrong="✗ Wrong. The correct answer is: {answer}",
    cmd_start="Start",
    cmd_wiederholen="Next exercise",
    cmd_language="Change language",
)
