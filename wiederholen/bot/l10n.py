from dataclasses import dataclass
from typing import Final, Any

from wiederholen.i18n import Language, LANGUAGES


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
    btn_recall_retry: str
    cmd_language: str
    bot_name: str
    bot_short_description: str
    reminder_text: str


RU: Final = Locale(
    start="Привет! Я помогу тебе запомнить иностранные слова через интервальное повторение.\n\nИспользуй /wiederholen чтобы начать.",
    correct="🟢 Правильно!",
    wrong="🔴 Неправильно. Правильный ответ: {answer}",
    recall_prompt="Восстановите фразу:\n{recall}",
    recall_correct="🟢 Правильно!",
    recall_wrong="🔴 Неправильно. Правильный вариант:\n{answer}",
    cmd_start="Начать",
    cmd_wiederholen="Следующее задание",
    btn_recall="Закрепить",
    btn_recall_retry="Попробовать ещё раз",
    cmd_language="Сменить язык",
    bot_name="Immer wiederholen!",
    bot_short_description="Учи немецкие слова с интервальным повторением",
    reminder_text="🔔 Есть что повторить! Загляни и сделай /wiederholen!",
)

EN: Final = Locale(
    start="Hi! I'll help you memorize foreign words using spaced repetition.\n\nUse /wiederholen to start.",
    correct="🟢 Correct!",
    wrong="🔴 Wrong. The correct answer is: {answer}",
    recall_prompt="Reconstruct the phrase:\n{recall}",
    recall_correct="🟢 Correct!",
    recall_wrong="🔴 Wrong. Correct answer:\n{answer}",
    cmd_start="Start",
    cmd_wiederholen="Next exercise",
    btn_recall="Drill",
    btn_recall_retry="Try again",
    cmd_language="Change language",
    bot_name="Immer wiederholen!",
    bot_short_description="Learn German vocabulary with spaced repetition",
    reminder_text="🔔 Something to review! Come back and do /wiederholen!",
)

LOCALES: Final[dict[Language, Locale]] = {"ru": RU, "en": EN}
DEFAULT_LANGUAGE: Final[Language] = "ru"


def get_language(state: dict[str, Any]) -> Language:
    raw_language = state.get("language")
    return raw_language if raw_language in LANGUAGES else DEFAULT_LANGUAGE
