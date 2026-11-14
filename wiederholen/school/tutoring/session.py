import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import cached_property
from typing import Final, Literal

from wiederholen.school.curriculum import Course, Exercise, Recall, fold_case
from wiederholen.school.tutoring.events import (
    ExerciseAnswered,
    ExerciseSelected,
    LessonFinished,
    LessonStarted,
    NoExerciseAvailable,
    RecallMode,
    StreakBroken,
    StreakExtended,
    TopicUnlocked,
    emit,
)
from wiederholen.school.tutoring.lesson import Lesson
from wiederholen.school.tutoring.selection import SelectablePairs
from wiederholen.school.tutoring.student_record import StudentRecord


@dataclass(frozen=True)
class FinishedLesson:
    size: int
    correct: int
    # This lesson added a day to the streak or started a new one
    extends_streak: bool


@dataclass(frozen=True)
class Mark:
    is_correct: bool
    recall: RecallMode
    # Set when this answer finished a lesson
    finished_lesson: FinishedLesson | None = None


@dataclass(frozen=True)
class LessonProgress:
    # The shown exercise is the position-th of size
    position: int
    size: int


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
    LESSON_SIZE: Final = 1

    def __init__(
        self,
        course: Course,
        student_record: dict,
        *,
        lesson: dict | None = None,
        lesson_size: int = LESSON_SIZE,
    ) -> None:
        # lesson is the frontend's own dict, changed in place like
        # student_record. Without one, a lesson lasts only as long as this
        # Tutor, which is enough for callers that never show exercises
        if lesson_size < 1:
            raise ValueError(f"lesson_size must be at least 1, got {lesson_size}")
        self._course = course
        self._today = datetime.now(UTC).date()
        self._student_record = StudentRecord(student_record, today=self._today)
        self._lesson = Lesson(
            lesson if lesson is not None else {}, now=datetime.now(UTC)
        )
        self._lesson_size = lesson_size

    @cached_property
    def _exercises_by_word_topic(self) -> dict[str, dict[str, list[Exercise]]]:
        result: dict[str, dict[str, list[Exercise]]] = {}
        for exercise in self._course.exercises:
            result.setdefault(exercise.word, {}).setdefault(exercise.topic, []).append(
                exercise
            )
        return result

    @cached_property
    def _exercises_by_content_key(self) -> dict[str, Exercise]:
        return {exercise.content_key: exercise for exercise in self._course.exercises}

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

    def _get_last_practiced_at(self) -> datetime | None:
        # A finished lesson is practice for the streak (see ADR 0027). A
        # record from before lessons has no last_lesson_finished_at. Until
        # then every answer finished a lesson of one exercise, so its last
        # answer is the same time
        last_lesson_finished_at = self._student_record.last_lesson_finished_at
        if last_lesson_finished_at is not None:
            return last_lesson_finished_at
        return self._get_last_answered_at()

    def streak(self) -> Streak | None:
        last_practiced_at = self._get_last_practiced_at()
        stored_streak = self._student_record.get_streak()
        if last_practiced_at is None or stored_streak is None:
            return None
        breaks_at = last_practiced_at + self.STREAK_BREAKS_AFTER
        if datetime.now(UTC) > breaks_at:
            return None
        days, _counted_at = stored_streak
        return Streak(days=days, breaks_at=breaks_at)

    def _update_streak(
        self, previous_practiced_at: datetime | None, practiced_at: datetime
    ) -> bool:
        # Without the learner's time zone, a day is counted when a lesson is
        # finished at least STREAK_DAY_AFTER after the lesson that counted
        # the previous day. So two sessions a day, such as 8:00 and 20:00,
        # add one day, not two
        stored_streak = self._student_record.get_streak()
        if (
            stored_streak is None
            or previous_practiced_at is None
            or practiced_at - previous_practiced_at > self.STREAK_BREAKS_AFTER
        ):
            if stored_streak is not None:
                emit(StreakBroken(days=stored_streak[0]))
            self._student_record.set_streak(1, practiced_at)
            emit(StreakExtended(days=1))
            return True
        days, counted_at = stored_streak
        if practiced_at - counted_at < self.STREAK_DAY_AFTER:
            return False
        self._student_record.set_streak(days + 1, practiced_at)
        emit(StreakExtended(days=days + 1))
        return True

    def _get_last_pair(self) -> tuple[str, str] | None:
        last_exercise = self._student_record.get_last_exercise()
        if last_exercise is None:
            return None
        word = last_exercise.get("word")
        topic = last_exercise.get("topic")
        if word is None or topic is None:
            return None
        return (word, topic)

    def _select_lesson_exercises(self) -> list[Exercise]:
        # The single-exercise pick, repeated: each exercise counts as the
        # last answer for the next pick, a pair is taken at most once, and
        # a new word spends the daily budget as soon as it is taken
        due_introduced = self._get_due_pairs(is_introduced=True)
        due_not_introduced = self._get_due_pairs(is_introduced=False)
        not_scheduled = self._get_available_not_scheduled_pairs()
        introduced_words = self._student_record.get_words_already_introduced()
        budget = max(
            self._get_effective_cap() - len(self._get_words_introduced_today()),
            0,
        )
        last_pair = self._get_last_pair()
        last_exercise = self._student_record.get_last_exercise()
        last_question = last_exercise["question"] if last_exercise is not None else None
        selected: list[Exercise] = []
        while len(selected) < self._lesson_size:
            taken_pairs = {(exercise.word, exercise.topic) for exercise in selected}
            selectable_pairs = SelectablePairs(
                due_introduced=due_introduced - taken_pairs,
                due_not_introduced=due_not_introduced - taken_pairs,
                not_scheduled=not_scheduled - taken_pairs,
            )
            if not selectable_pairs:
                if not selected:
                    emit(NoExerciseAvailable(reason="nothing_available"))
                break
            selected_word = selectable_pairs.select_word(
                introduced_words, budget, last_pair
            )
            if selected_word is None:
                if not selected:
                    emit(NoExerciseAvailable(reason="daily_cap_reached"))
                break
            if selected_word not in introduced_words:
                introduced_words = introduced_words | {selected_word}
                budget -= 1
            selected_topic = selectable_pairs.select_topic(selected_word, last_pair)
            candidates = self._exercises_by_word_topic[selected_word][selected_topic]
            if filtered_exercises := [
                exercise
                for exercise in candidates
                if exercise.question != last_question
            ]:
                candidates = filtered_exercises
            exercise = random.choice(candidates)
            selected.append(exercise)
            last_pair = (selected_word, selected_topic)
            last_question = exercise.question
        return selected

    def _take_lesson_exercise(self) -> Exercise | None:
        # A key that the course doesn't have is skipped: the exercise was
        # edited or removed, or its topic is no longer selected
        self._lesson.retain_exercise_keys(self._exercises_by_content_key)
        if (exercise_key := self._lesson.take_exercise_key()) is None:
            return None
        return self._exercises_by_content_key[exercise_key]

    def next_exercise(self) -> Exercise | None:
        exercise = self._take_lesson_exercise()
        if exercise is None:
            lesson_exercises = self._select_lesson_exercises()
            if not lesson_exercises:
                return None
            self._lesson.start([exercise.content_key for exercise in lesson_exercises])
            emit(LessonStarted(size=len(lesson_exercises)))
            exercise = self._take_lesson_exercise()
            assert exercise is not None
        introduced_pairs = set(
            self._student_record.iter_scheduled_pairs(is_introduced=True)
        )
        emit(
            ExerciseSelected(
                word=exercise.word,
                topic=exercise.topic,
                question=exercise.question,
                is_new=(exercise.word, exercise.topic) not in introduced_pairs,
            )
        )
        return exercise

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
        # Read before record_mark() replaces last_exercise's answered_at,
        # which a record from before lessons falls back to
        previous_practiced_at = self._get_last_practiced_at()
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
        self._lesson.record_answer(is_correct=is_correct)
        if not self._lesson.finish():
            return Mark(is_correct=is_correct, recall=recall_mode)
        emit(LessonFinished(size=self._lesson.size, correct=self._lesson.correct))
        self._student_record.last_lesson_finished_at = answered_at
        extends_streak = self._update_streak(previous_practiced_at, answered_at)
        return Mark(
            is_correct=is_correct,
            recall=recall_mode,
            finished_lesson=FinishedLesson(
                size=self._lesson.size,
                correct=self._lesson.correct,
                extends_streak=extends_streak,
            ),
        )

    def lesson_progress(self) -> LessonProgress | None:
        # Where the exercise that next_exercise() gave last is in its lesson
        if not self._lesson.is_current() or self._lesson.size == 0:
            return None
        return LessonProgress(position=self._lesson.given, size=self._lesson.size)

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
        if (
            last_reminded_at is None or last_reminded_at < last_answered_at
        ) and now - last_answered_at >= remind_after:
            return True
        # The streak reminder counts from the last finished lesson, as
        # breaks_at does, and the usual reminder from the last answer. So an
        # answer in an unfinished lesson doesn't put the streak reminder off
        streak = self.streak()
        last_practiced_at = self._get_last_practiced_at()
        if streak is None or last_practiced_at is None:
            return False
        streak_reminder_at = last_practiced_at + self.STREAK_REMIND_AFTER
        return (
            streak.days >= self.STREAK_REMIND_MIN_DAYS
            and streak_reminder_at
            <= now
            < streak_reminder_at + self.STREAK_REMIND_WINDOW
            and (
                last_reminded_at is None
                or last_reminded_at <= streak_reminder_at - self.STREAK_REMIND_MIN_GAP
            )
        )

    def record_reminder_sent(self) -> None:
        self._student_record.last_reminded_at = datetime.now(UTC)
