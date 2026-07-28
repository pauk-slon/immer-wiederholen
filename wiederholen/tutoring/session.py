import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import Enum
from functools import cached_property
from typing import Final

from wiederholen.tutoring.curriculum import Course, Exercise, Recall
from wiederholen.tutoring.journal import Journal, ScheduleEntry


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
    total: int
    new: int
    learning: int
    mastered: int
    due: int


class Tutor:
    MAX_INTERVAL_DAYS: Final = 60
    REMIND_AFTER: Final = timedelta(hours=24)
    NEW_PER_DAY: Final = 7

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
        return entry is None or "introduced_at" not in entry

    def _new_introduced_today_count(self) -> int:
        today = datetime.now(UTC).date().isoformat()
        return sum(
            1
            for word, topic in self._word_topics
            if (entry := self._journal.get_schedule_entry(word, topic)) is not None
            and entry.get("introduced_at") == today
        )

    def next_exercise(self) -> Exercise | None:
        today = datetime.now(UTC).date()
        due_word_topics = [
            (word, topic)
            for word, topic in self._word_topics
            if self._get_due_date(word, topic) <= today
        ]
        if due_word_topics:
            if self._new_introduced_today_count() >= self.NEW_PER_DAY:
                due_word_topics = [
                    (word, topic)
                    for word, topic in due_word_topics
                    if not self._is_new(word, topic)
                ]
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
        today = datetime.now(UTC).date()
        return sum(
            1
            for word, topic in self._word_topics
            if self._get_due_date(word, topic) <= today
        )

    def progress(self) -> Progress:
        new = 0
        learning = 0
        mastered = 0
        for word, topic in self._word_topics:
            entry = self._journal.get_schedule_entry(word, topic)
            if entry is None:
                new += 1
            elif entry["interval_days"] >= self.MAX_INTERVAL_DAYS:
                mastered += 1
            else:
                learning += 1
        return Progress(
            total=len(self._word_topics),
            new=new,
            learning=learning,
            mastered=mastered,
            due=self._due_topics_count(),
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
        today = datetime.now(UTC).date()
        dependent_entry = self._journal.get_schedule_entry(word, topic)
        if dependent_entry is None:
            topic_schedule = self._journal.get_topic_schedule(word, create_if_missing=True)
            topic_schedule[topic] = ScheduleEntry(
                interval_days=0,
                due_date=today.isoformat(),
            )
        elif date.fromisoformat(dependent_entry["due_date"]) > today:
            dependent_entry["due_date"] = today.isoformat()

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
