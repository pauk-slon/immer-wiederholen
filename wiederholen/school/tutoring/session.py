import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import cached_property
from typing import Final, Literal

from wiederholen.school.curriculum import Course, Exercise, Recall, fold_case
from wiederholen.school.tutoring.events import (
    ExerciseAnswered,
    NoExerciseAvailable,
    RecallMode,
    StreakBroken,
    StreakExtended,
    TopicUnlocked,
    emit,
)
from wiederholen.school.tutoring.selection import SelectablePairs
from wiederholen.school.tutoring.student_record import StudentRecord


@dataclass(frozen=True)
class Mark:
    is_correct: bool
    recall: RecallMode


@dataclass(frozen=True)
class Progress:
    remaining_today: int
    new_today: int
    learning: int
    mastered: int
    answered_today: int
    correct_today: int


@dataclass(frozen=True)
class Streak:
    days: int
    breaks_at: datetime


def _is_answer_correct(exercise: Exercise, answer: str) -> bool:
    if not exercise.distractors:
        return any(
            fold_case(answer) == fold_case(correct) for correct in exercise.answer
        )
    # Case can change the meaning, so two options can differ only in case, and an
    # exact match with an option wins. An answer typed instead of chosen, which a
    # phone may capitalize, matches without case only if no other option does
    options = [*exercise.answer, *exercise.distractors]
    if answer.strip() in (option.strip() for option in options):
        return answer.strip() in (correct.strip() for correct in exercise.answer)
    matches = [option for option in options if fold_case(option) == fold_case(answer)]
    return len(matches) == 1 and matches[0] in exercise.answer


class Tutor:
    MAX_REPETITION_INTERVAL_DAYS: Final = 60
    REMIND_AFTER: Final = timedelta(hours=24)
    NEW_WORDS_PER_DAY: Final = 7
    NEW_WORD_BUDGET_GRANT: Final = 3
    STREAK_BREAKS_AFTER: Final = timedelta(hours=36)
    STREAK_DAY_AFTER: Final = timedelta(hours=18)
    STREAK_REMIND_AFTER: Final = timedelta(hours=24)
    STREAK_REMIND_WINDOW: Final = timedelta(hours=1)
    STREAK_REMIND_MIN_GAP: Final = timedelta(hours=6)
    STREAK_REMIND_MIN_DAYS: Final = 2

    def __init__(self, course: Course, student_record: dict) -> None:
        self._course = course
        self._today = datetime.now(UTC).date()
        self._student_record = StudentRecord(student_record, today=self._today)

    @cached_property
    def _exercises_by_word_topic(self) -> dict[str, dict[str, list[Exercise]]]:
        result: dict[str, dict[str, list[Exercise]]] = {}
        for exercise in self._course.exercises:
            result.setdefault(exercise.word, {}).setdefault(exercise.topic, []).append(
                exercise
            )
        return result

    @cached_property
    def _course_pairs(self) -> set[tuple[str, str]]:
        return {
            (word, topic)
            for word, topics in self._exercises_by_word_topic.items()
            for topic in topics
        }

    def _get_words_introduced_today(self) -> set[str]:
        course_words = {word for word, _ in self._course_pairs}
        return self._student_record.get_words_introduced_today() & course_words

    def _get_effective_cap(self) -> int:
        return self.NEW_WORDS_PER_DAY + self._student_record.get_new_word_budget()

    def grant_new_word_budget(self) -> None:
        if len(self._get_words_introduced_today()) < self._get_effective_cap():
            # Likely a stale "study more" tap after the cap already reset —
            # granting would silently raise it without being asked.
            return
        self._student_record.bump_new_word_budget(self.NEW_WORD_BUDGET_GRANT)

    def _get_due_pairs(self, is_introduced: bool | None = None) -> set[tuple[str, str]]:
        return {
            pair
            for pair in self._student_record.iter_scheduled_pairs(
                only_due_today=True,
                is_introduced=is_introduced,
            )
            if pair in self._course_pairs
        }

    def _get_available_not_scheduled_pairs(self) -> set[tuple[str, str]]:
        scheduled_pairs = set(self._student_record.iter_scheduled_pairs())
        not_scheduled_pairs = self._course_pairs - scheduled_pairs
        return {
            (word, topic)
            for word, topic in not_scheduled_pairs
            if topic not in self._course.gated_topics
        }

    def _get_last_answered_at(self) -> datetime | None:
        if (last_exercise := self._student_record.get_last_exercise()) is None:
            return None
        return datetime.fromisoformat(last_exercise["answered_at"])

    def streak(self) -> Streak | None:
        last_answered_at = self._get_last_answered_at()
        stored_streak = self._student_record.get_streak()
        if last_answered_at is None or stored_streak is None:
            return None
        breaks_at = last_answered_at + self.STREAK_BREAKS_AFTER
        if datetime.now(UTC) > breaks_at:
            return None
        days, _counted_at = stored_streak
        return Streak(days=days, breaks_at=breaks_at)

    def _update_streak(
        self, previous_answered_at: datetime | None, answered_at: datetime
    ) -> None:
        # Without the learner's time zone, a day is counted when an answer
        # comes at least STREAK_DAY_AFTER after the answer that counted the
        # previous day. So two sessions a day, such as 8:00 and 20:00, add
        # one day, not two
        stored_streak = self._student_record.get_streak()
        if (
            stored_streak is None
            or previous_answered_at is None
            or answered_at - previous_answered_at > self.STREAK_BREAKS_AFTER
        ):
            if stored_streak is not None:
                emit(StreakBroken(days=stored_streak[0]))
            self._student_record.set_streak(1, answered_at)
            emit(StreakExtended(days=1))
            return
        days, counted_at = stored_streak
        if answered_at - counted_at >= self.STREAK_DAY_AFTER:
            self._student_record.set_streak(days + 1, answered_at)
            emit(StreakExtended(days=days + 1))

    def _get_last_pair(self) -> tuple[str, str] | None:
        last_exercise = self._student_record.get_last_exercise()
        if last_exercise is None:
            return None
        word = last_exercise.get("word")
        topic = last_exercise.get("topic")
        if word is None or topic is None:
            return None
        return (word, topic)

    def next_exercise(self) -> Exercise | None:
        selectable_pairs = SelectablePairs(
            due_introduced=self._get_due_pairs(is_introduced=True),
            due_not_introduced=self._get_due_pairs(is_introduced=False),
            not_scheduled=self._get_available_not_scheduled_pairs(),
        )
        if not selectable_pairs:
            emit(NoExerciseAvailable(reason="nothing_available"))
            return None
        budget = max(
            self._get_effective_cap() - len(self._get_words_introduced_today()),
            0,
        )
        last_pair = self._get_last_pair()
        selected_word = selectable_pairs.select_word(
            self._student_record.get_words_already_introduced(),
            budget,
            last_pair,
        )
        if selected_word is None:
            emit(NoExerciseAvailable(reason="daily_cap_reached"))
            return None
        selected_topic = selectable_pairs.select_topic(selected_word, last_pair)
        candidates = self._exercises_by_word_topic[selected_word][selected_topic]
        last_exercise = self._student_record.get_last_exercise()
        if last_exercise is not None and (
            filtered_exercises := [
                exercise
                for exercise in candidates
                if exercise.question != last_exercise["question"]
            ]
        ):
            candidates = filtered_exercises
        return random.choice(candidates)

    def progress(self) -> Progress:
        learning = 0
        mastered = 0
        for word, topics in self._exercises_by_word_topic.items():
            repetition_intervals = [
                self._student_record.get_repetition_interval(word, topic)
                for topic in topics
            ]
            if all(
                repetition_interval is None
                for repetition_interval in repetition_intervals
            ):
                continue
            if all(
                repetition_interval is not None
                and repetition_interval >= self.MAX_REPETITION_INTERVAL_DAYS
                for repetition_interval in repetition_intervals
            ):
                mastered += 1
            else:
                learning += 1
        answered_today, correct_today = self._student_record.get_answer_stats_today()
        return Progress(
            remaining_today=len(self._get_due_pairs()),
            new_today=len(self._get_words_introduced_today()),
            learning=learning,
            mastered=mastered,
            answered_today=answered_today,
            correct_today=correct_today,
        )

    def _calc_next_repetition_interval(
        self,
        *,
        prev_repetition_interval: int | None,
        is_answer_correct: bool,
    ) -> int:
        if not is_answer_correct or prev_repetition_interval is None:
            return 0
        return min(
            max(prev_repetition_interval * 2, 1),
            self.MAX_REPETITION_INTERVAL_DAYS,
        )

    def _expedite_dependent(self, word: str, topic: str) -> bool:
        if topic not in self._exercises_by_word_topic.get(word, {}):
            return False
        if self._student_record.get_repetition_interval(word, topic) is not None:
            return False
        self._student_record.schedule_pair(word, topic, repetition_interval=0)
        return True

    def _emit_topic_unlocked(self, source_topic: str, dependent_topic: str) -> None:
        via: Literal["chain", "gate"] = (
            "gate" if dependent_topic in self._course.gated_topics else "chain"
        )
        emit(
            TopicUnlocked(
                source_topic=source_topic,
                dependent_topic=dependent_topic,
                via=via,
            )
        )

    def _expedite_chained_topics(self, exercise: Exercise) -> None:
        for dependent_topic in self._course.word_chained_topics.get(exercise.topic, []):
            if self._expedite_dependent(exercise.word, dependent_topic):
                self._emit_topic_unlocked(exercise.topic, dependent_topic)
        for dependent_topic in self._course.answer_chained_topics.get(
            exercise.topic,
            [],
        ):
            if self._expedite_dependent(exercise.primary_answer, dependent_topic):
                self._emit_topic_unlocked(exercise.topic, dependent_topic)

    def check_answer(
        self,
        exercise: Exercise,
        answer: str,
    ) -> Mark:
        is_correct = _is_answer_correct(exercise, answer)
        if not exercise.recalls:
            recall_mode = RecallMode.none
        elif is_correct:
            recall_mode = RecallMode.optional
        else:
            recall_mode = RecallMode.required
        # Read before record_mark() replaces last_exercise's answered_at
        previous_answered_at = self._get_last_answered_at()
        answered_at = datetime.now(UTC)
        is_new, prev_repetition_interval = self._student_record.record_mark(
            exercise.question,
            exercise.word,
            exercise.topic,
            is_answer_correct=is_correct,
            is_recall_optional=recall_mode == RecallMode.optional,
            answered_at=answered_at,
        )
        next_repetition_interval = self._calc_next_repetition_interval(
            prev_repetition_interval=prev_repetition_interval,
            is_answer_correct=is_correct,
        )
        self._student_record.schedule_pair(
            exercise.word,
            exercise.topic,
            repetition_interval=next_repetition_interval,
            # A same-day "learning step" before real spacing kicks in —
            # otherwise a correct first answer would leave nothing to
            # review again that same day (the first-day content shortage
            # new learners used to hit). A correct answer on an
            # already-started pair spaces out by schedule_pair()'s own
            # repetition_interval default instead.
            due_interval=0 if (is_new or not is_correct) else None,
        )
        emit(
            ExerciseAnswered(
                word=exercise.word,
                topic=exercise.topic,
                is_correct=is_correct,
                is_new=is_new,
                recall_mode=recall_mode,
                prev_repetition_interval=prev_repetition_interval,
                next_repetition_interval=next_repetition_interval,
            )
        )
        self._expedite_chained_topics(exercise)
        self._update_streak(previous_answered_at, answered_at)
        return Mark(is_correct=is_correct, recall=recall_mode)

    def check_recall(self, recall: Recall, text: str) -> bool:
        def normalize(s: str) -> str:
            return " ".join(s.casefold().strip(".,!?").split())

        normalized = normalize(text)
        return any(normalize(a) == normalized for a in recall.answer)

    def request_recall(self, exercise: Exercise) -> Recall:
        last_exercise = self._student_record.get_last_exercise()
        assert last_exercise is not None
        if (
            last_exercise["is_recall_optional"]
            and "recall_question" not in last_exercise
        ):
            repetition_interval = self._student_record.get_repetition_interval(
                exercise.word,
                exercise.topic,
            )
            self._student_record.schedule_pair(
                exercise.word,
                exercise.topic,
                repetition_interval=max((repetition_interval or 0) // 2, 1),
            )
        candidates = exercise.recalls
        if "recall_question" in last_exercise and (
            filtered_recalls := [
                recall
                for recall in candidates
                if recall.question != last_exercise["recall_question"]
            ]
        ):
            candidates = filtered_recalls
        recall = random.choice(candidates)
        last_exercise["recall_question"] = recall.question
        return recall

    def get_hint(self, exercise: Exercise) -> str | None:
        if not exercise.grammar_classes:
            return None
        classes = set(exercise.grammar_classes)
        candidate_words = {
            other.word
            for other in self._course.exercises
            if other.topic == exercise.topic
            and other.word != exercise.word
            and other.grammar_classes
            and classes & set(other.grammar_classes)
        }
        scored = [
            (word, interval)
            for word in candidate_words
            if (
                interval := self._student_record.get_repetition_interval(
                    word, exercise.topic
                )
            )
            is not None
            and interval > 1
        ]
        if not scored:
            return None
        best_interval = max(interval for _, interval in scored)
        return random.choice(
            [word for word, interval in scored if interval == best_interval]
        )

    def should_remind(self, remind_after: timedelta = REMIND_AFTER) -> bool:
        if not self._get_due_pairs() and not self._get_available_not_scheduled_pairs():
            return False
        if (last_answered_at := self._get_last_answered_at()) is None:
            return False
        now = datetime.now(UTC)
        last_reminded_at = self._student_record.last_reminded_at
        if last_reminded_at is None or last_reminded_at < last_answered_at:
            return now - last_answered_at >= remind_after
        # Already reminded since the last answer. A real streak gets one more
        # reminder, at the time of day when the learner last practiced. The
        # window keeps a late sweep from sending it at night, and the gap keeps
        # it from following a first reminder that came late
        streak = self.streak()
        streak_reminder_at = last_answered_at + self.STREAK_REMIND_AFTER
        return (
            streak is not None
            and streak.days >= self.STREAK_REMIND_MIN_DAYS
            and streak_reminder_at
            <= now
            < streak_reminder_at + self.STREAK_REMIND_WINDOW
            and last_reminded_at <= streak_reminder_at - self.STREAK_REMIND_MIN_GAP
        )

    def record_reminder_sent(self) -> None:
        self._student_record.last_reminded_at = datetime.now(UTC)
