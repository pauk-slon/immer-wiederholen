from dataclasses import dataclass
from typing import Final

from wiederholen.i18n import Language


@dataclass(frozen=True)
class Locale:
    start: str
    correct: str
    wrong: str
    recall_prompt: str
    recall_correct: str
    recall_wrong: str
    cmd_start: str
    cmd_wiederholen: str
    btn_recall: str
    cmd_language: str


RU: Final = Locale(
    start="Привет! Я помогу тебе запомнить иностранные слова через интервальное повторение.\n\nИспользуй /wiederholen чтобы начать.",
    correct="✓ Правильно!",
    wrong="✗ Неправильно. Правильный ответ: {answer}",
    recall_prompt="Восстановите фразу:\n{recall}",
    recall_correct="✓ Правильно!",
    recall_wrong="✗ Неправильно. Правильный вариант:\n{answer}",
    cmd_start="Начать",
    cmd_wiederholen="Следующее задание",
    btn_recall="Закрепить",
    cmd_language="Сменить язык",
)

EN: Final = Locale(
    start="Hi! I'll help you memorize foreign words using spaced repetition.\n\nUse /wiederholen to start.",
    correct="✓ Correct!",
    wrong="✗ Wrong. The correct answer is: {answer}",
    recall_prompt="Reconstruct the phrase:\n{recall}",
    recall_correct="✓ Correct!",
    recall_wrong="✗ Wrong. Correct answer:\n{answer}",
    cmd_start="Start",
    cmd_wiederholen="Next exercise",
    btn_recall="Practice",
    cmd_language="Change language",
)

LOCALES: Final[dict[Language, Locale]] = {"ru": RU, "en": EN}
DEFAULT_LANGUAGE: Final[Language] = "ru"
