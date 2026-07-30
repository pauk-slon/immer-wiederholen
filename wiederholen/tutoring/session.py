import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import Enum
from functools import cached_property
from typing import Final

from wiederholen.tutoring.curriculum import Course, Exercise, Recall
from wiederholen.tutoring.journal import ExtraNewWords, Journal, ScheduleEntry


class RecallMode(Enum):
    none = "none"
    optional = "optional"
    required = "required"


@dataclass(frozen=True)
class Mark:
    correct: bool
    recall: RecallMode


@dataclass(frozen=True)
class Progress:
    remaining_today: int
    new_today: int
    learning: int
    mastered: int


class Tutor:
    MAX_INTERVAL_DAYS: Final = 60
    REMIND_AFTER: Final = timedelta(hours=24)
    NEW_WORDS_PER_DAY: Final = 7
    EXTRA_NEW_WORDS_GRANT: Final = 3

    def __init__(self, course: Course, journal: dict) -> None:
        self._course = course
        self._journal = Journal(journal)

    def _get_due_date(self, word: str, topic: str) -> date:
        entry = self._journal.get_schedule_entry(word, topic)
        if entry is None:
            exercise = self._exercises_by_word_topic[word][topic][0]
            if exercise.topic in self._course.gated_topics:
                return date.max
            return date.min
        return date.fromisoformat(entry["due_date"])

    @cached_property
    def _exercises_by_word_topic(self) -> dict[str, dict[str, list[Exercise]]]:
        result: dict[str, dict[str, list[Exercise]]] = {}
        for exercise in self._course.exercises:
            result.setdefault(exercise.word, {}).setdefault(exercise.topic, []).append(
                exercise
            )
        return result

    @cached_property
    def _word_topics(self) -> list[tuple[str, str]]:
        return [
            (word, topic)
            for word, topics in self._exercises_by_word_topic.items()
            for topic in topics
        ]

    def _is_new(self, word: str, topic: str) -> bool:
        entry = self._journal.get_schedule_entry(word, topic)
        return entry is None or entry["interval_days"] == 0

    def _words_introduced_today(self) -> set[str]:
        today = datetime.now(UTC).date().isoformat()
        return {
            word
            for word, topic in self._word_topics
            if (entry := self._journal.get_schedule_entry(word, topic)) is not None
            and entry.get("introduced_at") == today
        }

    def _new_words_introduced_today_count(self) -> int:
        return len(self._words_introduced_today())

    def _extra_new_words_today(self) -> int:
        extra = self._journal.get_extra_new_words()
        today = datetime.now(UTC).date().isoformat()
        if extra is None or extra["date"] != today:
            return 0
        return extra["count"]

    def grant_extra_new_words(self) -> None:
        today = datetime.now(UTC).date().isoformat()
        self._journal.set_extra_new_words(
            ExtraNewWords(
                date=today,
                count=self._extra_new_words_today() + self.EXTRA_NEW_WORDS_GRANT,
            )
        )

    def _due_review_pairs(self) -> list[tuple[str, str]]:
        today = datetime.now(UTC).date()
        return [
            (word, topic)
            for word, topic in self._word_topics
            if not self._is_new(word, topic)
            and self._get_due_date(word, topic) <= today
        ]

    def _available_new_pairs(self) -> list[tuple[str, str]]:
        today = datetime.now(UTC).date()
        return [
            (word, topic)
            for word, topic in self._word_topics
            if self._is_new(word, topic) and self._get_due_date(word, topic) <= today
        ]

    def _new_pairs_eligible_today(self) -> list[tuple[str, str]]:
        today_words = self._words_introduced_today()
        cap = self.NEW_WORDS_PER_DAY + self._extra_new_words_today()
        under_cap = len(today_words) < cap
        return [
            (word, topic)
            for word, topic in self._available_new_pairs()
            if word in today_words or under_cap
        ]

    def next_exercise(self) -> Exercise | None:
        due_word_topics = self._due_review_pairs() + self._available_new_pairs()
        if due_word_topics:
            due_word_topics = self._due_review_pairs() + self._new_pairs_eligible_today()
            if not due_word_topics:
                return None
            word, topic = random.choice(due_word_topics)
        else:
            earliest_due_date = min(
                self._get_due_date(word, topic) for word, topic in self._word_topics
            )
            earliest_word_topics = [
                (word, topic)
                for word, topic in self._word_topics
                if self._get_due_date(word, topic) == earliest_due_date
            ]
            word, topic = random.choice(earliest_word_topics)
        candidates = self._exercises_by_word_topic[word][topic]
        last_exercise = self._journal.get_last_exercise()
        if last_exercise is not None and (
            filtered_exercises := [
                exercise
                for exercise in candidates
                if exercise.question != last_exercise["question"]
            ]
        ):
            candidates = filtered_exercises
        return random.choice(candidates)

    def _due_topics_count(self) -> int:
        return len(self._due_review_pairs()) + len(self._available_new_pairs())

    def _new_remaining_today(self) -> int:
        return len(self._new_pairs_eligible_today())

    def progress(self) -> Progress:
        learning = 0
        mastered = 0
        for word, topics in self._exercises_by_word_topic.items():
            entries = [
                self._journal.get_schedule_entry(word, topic) for topic in topics
            ]
            if all(entry is None for entry in entries):
                continue
            if all(
                entry is not None and entry["interval_days"] >= self.MAX_INTERVAL_DAYS
                for entry in entries
            ):
                mastered += 1
            else:
                learning += 1
        return Progress(
            remaining_today=len(self._due_review_pairs()) + self._new_remaining_today(),
            new_today=self._new_words_introduced_today_count(),
            learning=learning,
            mastered=mastered,
        )

    def _schedule_next_repetition(
        self, exercise: Exercise, correct: bool, *, is_new: bool
    ) -> None:
        schedule_entry = self._journal.get_schedule_entry(
            exercise.word,
            exercise.topic,
            create_if_missing=True,
        )
        if is_new:
            schedule_entry["introduced_at"] = datetime.now(UTC).date().isoformat()
        if correct:
            interval = min(
                max(schedule_entry["interval_days"] * 2, 1), self.MAX_INTERVAL_DAYS
            )
            due_date = datetime.now(UTC).date() + timedelta(days=interval)
        else:
            interval = 1
            due_date = datetime.now(UTC).date()
        schedule_entry["interval_days"] = interval
        schedule_entry["due_date"] = due_date.isoformat()

    def _expedite_dependent(self, word: str, topic: str) -> None:
        if topic not in self._exercises_by_word_topic.get(word, {}):
            return
        if self._journal.get_schedule_entry(word, topic) is not None:
            return
        topic_schedule = self._journal.get_topic_schedule(word, create_if_missing=True)
        topic_schedule[topic] = ScheduleEntry(
            interval_days=0,
            due_date=datetime.now(UTC).date().isoformat(),
        )

    def _expedite_chained_topics(self, exercise: Exercise) -> None:
        for dependent_topic in self._course.word_chained_topics.get(exercise.topic, []):
            self._expedite_dependent(exercise.word, dependent_topic)
        for dependent_topic in self._course.answer_chained_topics.get(
            exercise.topic,
            [],
        ):
            self._expedite_dependent(exercise.answer, dependent_topic)

    def check_answer(self, exercise: Exercise, answer: str) -> Mark:
        correct = answer.strip().lower() == exercise.answer.strip().lower()
        if not exercise.recalls:
            recall_mode = RecallMode.none
        elif correct:
            recall_mode = RecallMode.optional
        else:
            recall_mode = RecallMode.required
        mark = Mark(correct=correct, recall=recall_mode)
        is_new = self._is_new(exercise.word, exercise.topic)
        self._journal.record_mark(
            exercise.question,
            was_recall_optional=recall_mode == RecallMode.optional,
        )
        self._schedule_next_repetition(exercise, correct, is_new=is_new)
        self._expedite_chained_topics(exercise)
        return mark

    def check_recall(self, recall: Recall, text: str) -> bool:
        def normalize(s: str) -> str:
            return " ".join(s.lower().strip(".,!?").split())

        normalized = normalize(text)
        return any(normalize(a) == normalized for a in recall.answer)

    def request_recall(self, exercise: Exercise) -> Recall:
        last_exercise = self._journal.get_last_exercise()
        assert last_exercise is not None
        if (
            last_exercise["is_recall_optional"]
            and last_exercise.get("recall_question") is None
        ):
            schedule_entry = self._journal.get_schedule_entry(
                exercise.word,
                exercise.topic,
                create_if_missing=True,
            )
            interval = max(schedule_entry["interval_days"] // 2, 1)
            schedule_entry["interval_days"] = interval
            schedule_entry["due_date"] = (
                datetime.now(UTC).date() + timedelta(days=interval)
            ).isoformat()
        candidates = exercise.recalls
        if last_exercise.get("recall_question") is not None and (
            filtered_recalls := [
                recall
                for recall in candidates
                if recall.question != last_exercise.get("recall_question")
            ]
        ):
            candidates = filtered_recalls
        recall = random.choice(candidates)
        last_exercise["recall_question"] = recall.question
        return recall

    def should_remind(self) -> bool:
        if self._due_topics_count() <= 0:
            return False
        if (last_exercise := self._journal.get_last_exercise()) is None:
            return False
        last_answered_at = datetime.fromisoformat(last_exercise["answered_at"])
        if datetime.now(UTC) - last_answered_at < self.REMIND_AFTER:
            return False
        last_reminded_at = self._journal.last_reminded_at
        return last_reminded_at is None or last_reminded_at < last_answered_at

    def record_reminder_sent(self) -> None:
        self._journal.last_reminded_at = datetime.now(UTC)
