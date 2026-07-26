import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import Enum
from functools import cached_property
from typing import Final

from wiederholen.tutoring.curriculum import Course, Exercise, Recall
from wiederholen.tutoring.journal import Journal, _ScheduleEntry


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

    def __init__(self, course: Course, journal: dict) -> None:
        self._course = course
        self._journal = Journal(journal)

    @staticmethod
    def _compose_schedule_key(exercise: Exercise) -> str:
        return f"{exercise.word}:{exercise.topic}"

    def _get_due_date(self, key: str) -> date:
        entry = self._journal.get_schedule_entry(key)
        if entry is None:
            exercise = self._exercises_by_schedule_key[key][0]
            if exercise.topic in self._course.gated_topics:
                return date.max
            return date.min
        return date.fromisoformat(entry["due_date"])

    @cached_property
    def _exercises_by_schedule_key(self) -> dict[str, list[Exercise]]:
        result: dict[str, list[Exercise]] = {}
        for exercise in self._course.exercises:
            result.setdefault(self._compose_schedule_key(exercise), []).append(exercise)
        return result

    def next_exercise(self) -> Exercise:
        today = date.today()
        due_schedule_keys = [
            schedule_key
            for schedule_key in self._exercises_by_schedule_key
            if self._get_due_date(schedule_key) <= today
        ]
        if due_schedule_keys:
            schedule_key = random.choice(due_schedule_keys)
        else:
            earliest_due_date = min(
                self._get_due_date(schedule_key)
                for schedule_key in self._exercises_by_schedule_key
            )
            earliest_schedule_keys = [
                schedule_key
                for schedule_key in self._exercises_by_schedule_key
                if self._get_due_date(schedule_key) == earliest_due_date
            ]
            schedule_key = random.choice(earliest_schedule_keys)
        candidates = self._exercises_by_schedule_key[schedule_key]
        last_exercise = self._journal.get_last_exercise()
        if last_exercise is not None:
            if filtered_exercises := [
                exercise
                for exercise in candidates
                if exercise.question != last_exercise["question"]
            ]:
                candidates = filtered_exercises
        return random.choice(candidates)

    def due_topics_count(self) -> int:
        today = date.today()
        return sum(
            1
            for schedule_key in self._exercises_by_schedule_key
            if self._get_due_date(schedule_key) <= today
        )

    def progress(self) -> Progress:
        new = 0
        learning = 0
        mastered = 0
        for schedule_key in self._exercises_by_schedule_key:
            entry = self._journal.get_schedule_entry(schedule_key)
            if entry is None:
                new += 1
            elif entry["interval_days"] >= self.MAX_INTERVAL_DAYS:
                mastered += 1
            else:
                learning += 1
        return Progress(
            total=len(self._exercises_by_schedule_key),
            new=new,
            learning=learning,
            mastered=mastered,
            due=self.due_topics_count(),
        )

    def _schedule_next_repetition(self, exercise: Exercise, correct: bool) -> None:
        schedule_entry = self._journal.get_schedule_entry(
            self._compose_schedule_key(exercise),
            create_if_missing=True,
        )
        if correct:
            interval = min(
                max(schedule_entry["interval_days"] * 2, 1), self.MAX_INTERVAL_DAYS
            )
            due_date = date.today() + timedelta(days=interval)
        else:
            interval = 1
            due_date = date.today()
        schedule_entry["interval_days"] = interval
        schedule_entry["due_date"] = due_date.isoformat()

    def _expedite_chained_topics(self, exercise: Exercise) -> None:
        today = date.today()
        for dependent_topic in self._course.chained_topics.get(exercise.topic, []):
            dependent_key = f"{exercise.word}:{dependent_topic}"
            if dependent_key not in self._exercises_by_schedule_key:
                continue
            dependent_entry = self._journal.get_schedule_entry(dependent_key)
            if dependent_entry is None:
                word_schedule = self._journal.get_word_schedule(create_if_missing=True)
                word_schedule[dependent_key] = _ScheduleEntry(
                    interval_days=0,
                    due_date=today.isoformat(),
                )
            elif date.fromisoformat(dependent_entry["due_date"]) > today:
                dependent_entry["due_date"] = today.isoformat()

    def check_answer(self, exercise: Exercise, answer: str) -> Mark:
        correct = answer.strip().lower() == exercise.answer.strip().lower()
        if not exercise.recalls:
            recall_mode = RecallMode.none
        elif correct:
            recall_mode = RecallMode.optional
        else:
            recall_mode = RecallMode.required
        mark = Mark(correct=correct, recall=recall_mode)
        self._journal.record_mark(
            exercise.question, was_recall_optional=recall_mode == RecallMode.optional
        )
        self._schedule_next_repetition(exercise, correct)
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
                self._compose_schedule_key(exercise),
                create_if_missing=True,
            )
            interval = max(schedule_entry["interval_days"] // 2, 1)
            schedule_entry["interval_days"] = interval
            schedule_entry["due_date"] = (
                date.today() + timedelta(days=interval)
            ).isoformat()
        candidates = exercise.recalls
        if last_exercise.get("recall_question") is not None:
            if filtered_recalls := [
                recall
                for recall in candidates
                if recall.question != last_exercise.get("recall_question")
            ]:
                candidates = filtered_recalls
        recall = random.choice(candidates)
        last_exercise["recall_question"] = recall.question
        return recall

    def should_remind(self) -> bool:
        if self.due_topics_count() <= 0:
            return False
        last_exercise = self._journal.get_last_exercise()
        if last_exercise is None:
            return False
        last_answered_at = datetime.fromisoformat(last_exercise["answered_at"])
        if datetime.now(UTC) - last_answered_at < self.REMIND_AFTER:
            return False
        last_reminded_at = self._journal.last_reminded_at
        if last_reminded_at is not None and last_reminded_at >= last_answered_at:
            return False
        return True

    def record_reminder_sent(self) -> None:
        self._journal.last_reminded_at = datetime.now(UTC)
