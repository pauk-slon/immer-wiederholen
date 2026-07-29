from dataclasses import dataclass
from typing import Any, Final

from wiederholen.i18n import LANGUAGES, Language


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
    cmd_progress: str
    cmd_reset: str
    reset_confirm_prompt: str
    reset_confirm_button: str
    reset_cancel_button: str
    reset_done: str
    reset_cancelled: str
    bot_name: str
    bot_short_description: str
    reminder_text: str
    progress_text: str
    description_prompt: str
    nothing_due_text: str


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
    cmd_progress="Прогресс",
    cmd_reset="Сбросить прогресс",
    reset_confirm_prompt="Точно сбросить весь прогресс? Это действие нельзя отменить",
    reset_confirm_button="Да, сбросить",
    reset_cancel_button="Отмена",
    reset_done="✅ Прогресс сброшен",
    reset_cancelled="Отменено",
    bot_name="Immer wiederholen!",
    bot_short_description="Учи немецкие слова с интервальным повторением",
    reminder_text="🔔 Есть что повторить! Загляни и сделай /wiederholen!",
    progress_text=(
        "📊 Твой прогресс\n"
        "\n"
        "🎯 Осталось сегодня: {remaining_today}\n"
        "🆕 Новых сегодня: {new_today}\n"
        "📈 В процессе: {learning}\n"
        "✅ Выучено: {mastered}"
    ),
    description_prompt="💭 {description} Введи пропущенное слово.",
    nothing_due_text="🎉 На сегодня всё! Загляни завтра — будут новые слова и повторения.",
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
    cmd_progress="Progress",
    cmd_reset="Reset progress",
    reset_confirm_prompt="Are you sure you want to reset all progress? This can't be undone",
    reset_confirm_button="Yes, reset",
    reset_cancel_button="Cancel",
    reset_done="✅ Progress has been reset",
    reset_cancelled="Cancelled",
    bot_name="Immer wiederholen!",
    bot_short_description="Learn German vocabulary with spaced repetition",
    reminder_text="🔔 Something to review! Come back and do /wiederholen!",
    progress_text=(
        "📊 Your progress\n"
        "\n"
        "🎯 Left today: {remaining_today}\n"
        "🆕 New today: {new_today}\n"
        "📈 Learning: {learning}\n"
        "✅ Mastered: {mastered}"
    ),
    description_prompt="💭 {description} Enter the missing word.",
    nothing_due_text="🎉 That's all for today! Come back tomorrow for new words and reviews.",
)

LOCALES: Final[dict[Language, Locale]] = {"ru": RU, "en": EN}
DEFAULT_LANGUAGE: Final[Language] = "ru"


def get_language(state: dict[str, Any]) -> Language:
    raw_language = state.get("language")
    return raw_language if raw_language in LANGUAGES else DEFAULT_LANGUAGE
