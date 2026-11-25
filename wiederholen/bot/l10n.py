import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, Literal

from wiederholen.school import LANGUAGES, Language, Streak

_WAIT_UNITS: Final[dict[str, tuple[str, str]]] = {
    "ru": ("мин", "ч"),
    "en": ("min", "h"),
}
_RU_UNIT_FORMS: Final[dict[str, tuple[str, str, str]]] = {
    "exercises": ("задание", "задания", "заданий"),
    "words": ("слово", "слова", "слов"),
    "days": ("день", "дня", "дней"),
}
_EN_UNIT_FORMS: Final[dict[str, tuple[str, str]]] = {
    "exercises": ("exercise", "exercises"),
    "words": ("word", "words"),
    "days": ("day", "days"),
}


def _ru_plural(n: int, one: str, few: str, many: str) -> str:
    n_100 = n % 100
    if 11 <= n_100 <= 14:
        return many
    n_10 = n % 10
    if n_10 == 1:
        return one
    if 2 <= n_10 <= 4:
        return few
    return many


def format_count(
    n: int,
    unit: Literal["exercises", "words", "days"],
    language: Language,
) -> str:
    if language == "ru":
        one, few, many = _RU_UNIT_FORMS[unit]
        word = _ru_plural(n, one, few, many)
    else:
        singular, plural = _EN_UNIT_FORMS[unit]
        word = singular if n == 1 else plural
    return f"{n} {word}"


def format_wait(seconds: float, language: Language) -> str:
    """A wait in minutes under two hours, in hours otherwise, rounded up, so
    that the learner never comes too early. Whole hours would round 61 minutes
    up to 2 h."""
    minutes_unit, hours_unit = _WAIT_UNITS[language]
    minutes = max(1, math.ceil(seconds / 60))
    if minutes < 120:
        return f"{minutes} {minutes_unit}"
    return f"{math.ceil(seconds / 3600)} {hours_unit}"


@dataclass(frozen=True)
class Locale:
    start: str
    # A result starts with a mark instead of a verdict line. The marks differ
    # in shape, not only in color, for learners who don't see colors
    correct_mark: str
    wrong_mark: str
    correct: str
    wrong: str
    # A task to write a sentence has ✍️ and the instruction above the text, as
    # in lesson_recall_sentence
    recall_prompt: str
    recall_wrong: str
    # After a mistake of only extra letters: the learner's text with them
    # struck through, then the answer
    wrong_extra_letters: str
    cmd_start: str
    cmd_wiederholen: str
    btn_recall: str
    btn_recall_retry: str
    btn_recall_skip: str
    btn_study_more: str
    cmd_language: str
    cmd_progress: str
    cmd_reset: str
    cmd_topics: str
    topics_prompt: str
    topics_unavailable: str
    btn_topics_done: str
    topics_selected: str
    topics_all_selected: str
    # After the greeting, when a link selected topic groups (#345)
    topics_change_hint: str
    cmd_reminders: str
    reminders_prompt: str
    btn_remind_after: str
    btn_reminders_off: str
    reminders_set: str
    reminders_off: str
    reset_confirm_prompt: str
    reset_confirm_button: str
    reset_cancel_button: str
    reset_done: str
    reset_cancelled: str
    reminder_text: str
    reminder_streak_text: str
    progress_text: str
    nothing_due_text: str
    unexpected_message: str
    streak_text: str
    lesson_summary: str
    # In the summary of a lesson that gets no practice because of the daily limit
    lesson_recall_limit_text: str
    # After a lesson, the text of the "Next exercise" button
    btn_next_lesson: str
    btn_practice: str
    btn_next_sentence: str
    grammar_class_hint: str
    language_set: str
    lesson_recall_summary: str
    lesson_recall_sentence: str
    btn_lesson_recall_skip: str
    lesson_recall_reference: str
    lesson_recall_correction: str
    lesson_recall_wait: str
    lesson_recall_generation_failed: str
    lesson_recall_check_failed: str
    lesson_recall_too_long: str
    btn_lesson_recall_resend: str


# The texts address the learner as "вы", in lower case as usual in an
# interface. A button that names an action uses the infinitive ("Попробовать
# ещё раз"). A button that leads to another part of the lesson names it with
# a noun ("Следующий урок", "Практика")
#
# Words for what the code calls (ADR 0036):
# | code          | ru       | en       |
# | exercise      | задание  | exercise |
# | lesson        | урок     | lesson   |
# | lesson recall | практика | practice |
# A recall has no noun, only the verb on its button
RU: Final = Locale(
    start="Привет! Я буду давать вам короткие задания и возвращаться к ним, пока вы их не запомните.",
    correct_mark="✅",
    wrong_mark="❌",
    correct="Правильно!",
    wrong="Правильный ответ: {answer}",
    recall_prompt="✍️ Напишите фразу целиком:\n{recall}",
    recall_wrong="Правильный ответ:\n{answer}",
    wrong_extra_letters="{mistake} → {answer}",
    cmd_start="Начать",
    cmd_wiederholen="Следующее задание",
    btn_recall="Закрепить",
    btn_recall_retry="Попробовать ещё раз",
    btn_recall_skip="Пропустить",
    btn_study_more="Позаниматься ещё",
    cmd_language="Сменить язык",
    cmd_progress="Прогресс",
    cmd_reset="Сбросить прогресс",
    cmd_topics="Выбрать темы",
    topics_prompt="Выберите темы для заданий. Если ничего не выбрано — задания будут по всем темам.",
    topics_unavailable="Выбор тем пока недоступен",
    btn_topics_done="Готово",
    topics_selected="✅ Темы: {topics}",
    topics_all_selected="✅ Задания будут по всем темам",
    topics_change_hint="Выбрать другие темы: /topics",
    cmd_reminders="Напоминания",
    reminders_prompt="Через сколько после последнего занятия напомнить позаниматься?",
    btn_remind_after="{hours} ч",
    btn_reminders_off="Не напоминать",
    reminders_set="🔔 Напомню через {hours} ч после последнего занятия",
    reminders_off="🔕 Напоминания выключены",
    reset_confirm_prompt="Точно сбросить весь прогресс? Это действие нельзя отменить.",
    reset_confirm_button="Да, сбросить",
    reset_cancel_button="Отмена",
    reset_done="✅ Прогресс сброшен",
    reset_cancelled="Отменено",
    reminder_text="🔔 Есть что повторить!",
    reminder_streak_text="🔥 Серия: {days}. Прервётся через {hours} ч",
    progress_text=(
        "📊 Ваш прогресс\n"
        "\n"
        "Сегодня\n"
        "✍️ Ответов: {answered_count} (верно: {correct_today})\n"
        "🆕 Новых: {new_today}\n"
        "🎯 Осталось: {remaining_today}\n"
        "\n"
        "Всего\n"
        "📈 В процессе: {learning}\n"
        "✅ Выучено: {mastered}"
    ),
    nothing_due_text="🎉 На сегодня всё! Загляните завтра за новыми заданиями.",
    unexpected_message=(
        "Я не отвечаю на сообщения, только даю задания и проверяю ответы. "
        "Нажмите кнопку, чтобы продолжить."
    ),
    streak_text="🔥 Серия: {days}",
    lesson_summary="🏁 Урок пройден: верно {correct} из {size}",
    lesson_recall_limit_text="⏳ Практика снова будет доступна через {wait}",
    btn_next_lesson="Следующий урок",
    btn_practice="Практика",
    btn_next_sentence="Следующая фраза",
    grammar_class_hint="Так же, как у {word}",
    language_set="🌐 Язык: русский",
    lesson_recall_summary="🏁 Практика: верно {correct} из {size}",
    lesson_recall_sentence="{position}/{size} ✍️ Переведите:\n{text}",
    btn_lesson_recall_skip="Пропустить",
    lesson_recall_reference="Вариант перевода:\n{reference}",
    lesson_recall_correction="Ваш вариант с исправлениями:\n{correction}",
    lesson_recall_wait="⏳ Секунду, я ещё думаю…",
    lesson_recall_generation_failed="⚠️ Не получилось подготовить фразы для перевода.",
    lesson_recall_check_failed="⚠️ Не получилось проверить перевод.",
    lesson_recall_too_long="⚠️ Перевод слишком длинный: не больше {limit} символов.",
    btn_lesson_recall_resend="Проверить снова",
)

EN: Final = Locale(
    start="Hi! I'll give you short exercises and bring them back until you remember them.",
    correct_mark="✅",
    wrong_mark="❌",
    correct="Correct!",
    wrong="The correct answer is: {answer}",
    recall_prompt="✍️ Type the whole sentence:\n{recall}",
    recall_wrong="The correct answer is:\n{answer}",
    wrong_extra_letters="{mistake} → {answer}",
    cmd_start="Start",
    cmd_wiederholen="Next exercise",
    btn_recall="Drill",
    btn_recall_retry="Try again",
    btn_recall_skip="Skip",
    btn_study_more="Study more",
    cmd_language="Change language",
    cmd_progress="Progress",
    cmd_reset="Reset progress",
    cmd_topics="Choose topics",
    topics_prompt="Choose topics for your exercises. If none are selected, exercises cover all topics.",
    topics_unavailable="Choosing topics isn't available yet",
    btn_topics_done="Done",
    topics_selected="✅ Topics: {topics}",
    topics_all_selected="✅ Exercises will cover all topics",
    topics_change_hint="Choose other topics: /topics",
    cmd_reminders="Reminders",
    reminders_prompt="How long after your last session should I remind you to practice?",
    btn_remind_after="{hours} h",
    btn_reminders_off="Don't remind me",
    reminders_set="🔔 I'll remind you {hours} h after your last session",
    reminders_off="🔕 Reminders are off",
    reset_confirm_prompt="Are you sure you want to reset all progress? This can't be undone.",
    reset_confirm_button="Yes, reset",
    reset_cancel_button="Cancel",
    reset_done="✅ Progress has been reset",
    reset_cancelled="Cancelled",
    reminder_text="🔔 Something to review!",
    reminder_streak_text="🔥 Streak: {days}. It ends in {hours} h",
    progress_text=(
        "📊 Your progress\n"
        "\n"
        "Today\n"
        "✍️ Answered: {answered_today} (correct: {correct_today})\n"
        "🆕 New: {new_today}\n"
        "🎯 Left: {remaining_today}\n"
        "\n"
        "Overall\n"
        "📈 Learning: {learning}\n"
        "✅ Mastered: {mastered}"
    ),
    nothing_due_text="🎉 That's all for today! Come back tomorrow for more.",
    unexpected_message=(
        "I don't answer messages, I only give exercises and check your answers. "
        "Tap the button to continue."
    ),
    streak_text="🔥 Streak: {days}",
    lesson_summary="🏁 Lesson complete: {correct} of {size} correct",
    lesson_recall_limit_text="⏳ Practice is available again in {wait}",
    btn_next_lesson="Next lesson",
    btn_practice="Practice",
    btn_next_sentence="Next sentence",
    grammar_class_hint="Same as for {word}",
    language_set="🌐 Language: English",
    lesson_recall_summary="🏁 Practice: {correct} of {size} correct",
    lesson_recall_sentence="{position}/{size} ✍️ Translate:\n{text}",
    btn_lesson_recall_skip="Skip",
    lesson_recall_reference="A possible translation:\n{reference}",
    lesson_recall_correction="Your translation, corrected:\n{correction}",
    lesson_recall_wait="⏳ One moment, I'm still thinking…",
    lesson_recall_generation_failed="⚠️ Couldn't prepare the sentences to translate.",
    lesson_recall_check_failed="⚠️ Couldn't check the translation.",
    lesson_recall_too_long="⚠️ The translation is too long: {limit} characters at most.",
    btn_lesson_recall_resend="Check again",
)

LOCALES: Final[dict[Language, Locale]] = {"ru": RU, "en": EN}
DEFAULT_LANGUAGE: Final[Language] = "ru"


def append_streak_line(
    text: str, streak: Streak | None, language: Language, line: str
) -> str:
    # line is streak_text or reminder_streak_text. Without a streak, the
    # message has no streak line at all
    if streak is None:
        return text
    # Rounded up, and at least 1, so the last hour reads "1 h" and not "0 h",
    # even if breaks_at passed after streak() was read
    hours = max(
        math.ceil((streak.breaks_at - datetime.now(UTC)).total_seconds() / 3600), 1
    )
    days = format_count(streak.days, "days", language)
    return f"{text}\n\n{line.format(days=days, hours=hours)}"


def get_language(state: dict[str, Any]) -> Language:
    raw_language = state.get("language")
    return raw_language if raw_language in LANGUAGES else DEFAULT_LANGUAGE
