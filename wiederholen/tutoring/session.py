import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from functools import cached_property
from typing import Final, Literal

from wiederholen.tutoring.curriculum import Course, Exercise, Recall
from wiederholen.tutoring.journal import Journal


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
    answered_today: int
    correct_today: int


@dataclass(frozen=True)
class ExerciseAnswered:
    word: str
    topic: str
    correct: bool
    is_new: bool
    recall_mode: RecallMode
    repetition_interval_before: int
    repetition_interval_after: int


@dataclass(frozen=True)
class TopicUnlocked:
    source_topic: str
    dependent_topic: str
    via: Literal["chain", "gate"]


@dataclass(frozen=True)
class NoExerciseAvailable:
    # "nothing_available": no due review and no available new pair at all.
    # "daily_cap_reached": pairs exist, but the new-word budget is
    #   exhausted and no already-introduced word is available either.
    reason: Literal["nothing_available", "daily_cap_reached"]


TutoringEvent = ExerciseAnswered | TopicUnlocked | NoExerciseAvailable


@dataclass(frozen=True)
class SelectablePairs:
    # Today's three-way partition for next_exercise()'s word/topic pick —
    # split first by whether a pair is due today, then, for due pairs, by
    # introduced status. not_scheduled pairs are always not introduced too
    # (there's no way to be introduced without a schedule entry), so there's
    # no fourth "not scheduled and introduced" cell.
    due_introduced: set[tuple[str, str]]
    due_not_introduced: set[tuple[str, str]]
    not_scheduled: set[tuple[str, str]]

    @property
    def all_pairs(self) -> set[tuple[str, str]]:
        return self.due_introduced | self.due_not_introduced | self.not_scheduled

    @property
    def not_introduced(self) -> set[tuple[str, str]]:
        return self.due_not_introduced | self.not_scheduled

    def __bool__(self) -> bool:
        return bool(self.all_pairs)

    def _get_word_tiers(
        self,
        introduced_words: set[str],
    ) -> tuple[set[str], set[str], set[str]]:
        # Three tiers, by how "free" a word is to select without spending the
        # daily new-word budget:
        # - free: introduced via some topic already (Journal.get_words_already_introduced()
        #   — a single journal scan, not a per-word lookup) — regardless of
        #   whether that's the topic that's due/available today.
        # - queued: never introduced, but already has a schedule entry
        #   (expedited via a chain/gate) — prioritized over... A not-yet-
        #   introduced entry is always due today (see _expedite_dependent()),
        #   so "has any entry" and "has a due entry" coincide here.
        # - fresh: no schedule entry anywhere, genuinely never touched.
        today_relevant_words = {word for word, _ in self.all_pairs}
        free_words = today_relevant_words & introduced_words
        remaining_words = today_relevant_words - free_words
        queued_words = {word for word, _ in self.due_not_introduced} - introduced_words
        fresh_words = remaining_words - queued_words
        return free_words, queued_words, fresh_words

    def select_word(
        self,
        introduced_words: set[str],
        budget: int,
        last_pair: tuple[str, str] | None,
    ) -> str | None:
        free_words, queued_words, fresh_words = self._get_word_tiers(introduced_words)
        queued_list = list(queued_words)
        taken_queued = (
            queued_list
            if len(queued_list) <= budget
            else random.sample(queued_list, budget)
        )
        remaining_budget = max(budget - len(taken_queued), 0)
        fresh_list = list(fresh_words)
        taken_fresh = (
            fresh_list
            if len(fresh_list) <= remaining_budget
            else random.sample(fresh_list, remaining_budget)
        )
        candidates = free_words | set(taken_queued) | set(taken_fresh)
        if last_pair is not None:
            last_word, _ = last_pair
            without_last_word = {word for word in candidates if word != last_word}
            if without_last_word:
                candidates = without_last_word
        if not candidates:
            return None
        return random.choice(list(candidates))

    def select_topic(self, word: str, last_pair: tuple[str, str] | None) -> str:
        due_topics = [topic for w, topic in self.due_introduced if w == word]
        candidate_topics = due_topics or [
            topic for w, topic in self.not_introduced if w == word
        ]
        if last_pair is not None and last_pair[0] == word:
            without_last_topic = [t for t in candidate_topics if t != last_pair[1]]
            if without_last_topic:
                candidate_topics = without_last_topic
        return random.choice(candidate_topics)


class Tutor:
    MAX_REPETITION_INTERVAL_DAYS: Final = 60
    REMIND_AFTER: Final = timedelta(hours=24)
    NEW_WORDS_PER_DAY: Final = 7
    EXTRA_NEW_WORDS_GRANT: Final = 3

    def __init__(self, course: Course, journal: dict) -> None:
        self._course = course
        self._today = datetime.now(UTC).date()
        self._journal = Journal(journal, today=self._today)

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
        return self._journal.get_words_introduced_today() & course_words

    def _get_effective_cap(self) -> int:
        return self.NEW_WORDS_PER_DAY + self._journal.get_extra_new_words_today()

    def grant_extra_new_words(self) -> None:
        if len(self._get_words_introduced_today()) < self._get_effective_cap():
            # The cap isn't actually binding right now — most likely a stale
            # "study more" button clicked after the cap reset for a new day.
            # Granting here would silently raise today's cap without the
            # learner having asked for it today.
            return
        self._journal.add_extra_new_words_today(self.EXTRA_NEW_WORDS_GRANT)

    def _get_due_pairs(self, introduced: bool | None = None) -> set[tuple[str, str]]:
        return {
            pair
            for pair in self._journal.iter_scheduled_pairs(
                only_due_today=True,
                introduced=introduced,
            )
            if pair in self._course_pairs
        }

    def _get_available_not_scheduled_pairs(self) -> set[tuple[str, str]]:
        scheduled_pairs = set(self._journal.iter_scheduled_pairs())
        not_scheduled_pairs = self._course_pairs - scheduled_pairs
        return {
            (word, topic)
            for word, topic in not_scheduled_pairs
            if topic not in self._course.gated_topics
        }

    def _get_last_pair(self) -> tuple[str, str] | None:
        last_exercise = self._journal.get_last_exercise()
        if last_exercise is None:
            return None
        word = last_exercise.get("word")
        topic = last_exercise.get("topic")
        if word is None or topic is None:
            return None
        return (word, topic)

    def next_exercise(self) -> tuple[Exercise | None, list[TutoringEvent]]:
        selectable_pairs = SelectablePairs(
            due_introduced=self._get_due_pairs(introduced=True),
            due_not_introduced=self._get_due_pairs(introduced=False),
            not_scheduled=self._get_available_not_scheduled_pairs(),
        )
        if not selectable_pairs:
            return None, [NoExerciseAvailable(reason="nothing_available")]
        budget = max(
            self._get_effective_cap() - len(self._get_words_introduced_today()),
            0,
        )
        last_pair = self._get_last_pair()
        selected_word = selectable_pairs.select_word(
            self._journal.get_words_already_introduced(),
            budget,
            last_pair,
        )
        if selected_word is None:
            return None, [NoExerciseAvailable(reason="daily_cap_reached")]
        selected_topic = selectable_pairs.select_topic(selected_word, last_pair)
        candidates = self._exercises_by_word_topic[selected_word][selected_topic]
        last_exercise = self._journal.get_last_exercise()
        if last_exercise is not None and (
            filtered_exercises := [
                exercise
                for exercise in candidates
                if exercise.question != last_exercise["question"]
            ]
        ):
            candidates = filtered_exercises
        return random.choice(candidates), []

    def progress(self) -> Progress:
        learning = 0
        mastered = 0
        for word, topics in self._exercises_by_word_topic.items():
            repetition_intervals = [
                self._journal.get_repetition_interval(word, topic) for topic in topics
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
        answered_today, correct_today = self._journal.get_answer_stats_today()
        return Progress(
            remaining_today=len(self._get_due_pairs()),
            new_today=len(self._get_words_introduced_today()),
            learning=learning,
            mastered=mastered,
            answered_today=answered_today,
            correct_today=correct_today,
        )

    def _next_repetition(self, repetition_interval_before: int, correct: bool) -> int:
        if correct:
            return min(
                max(repetition_interval_before * 2, 1),
                self.MAX_REPETITION_INTERVAL_DAYS,
            )
        return 1

    def _expedite_dependent(self, word: str, topic: str) -> bool:
        if topic not in self._exercises_by_word_topic.get(word, {}):
            return False
        if self._journal.get_repetition_interval(word, topic) is not None:
            return False
        self._journal.schedule_pair(word, topic, repetition_interval=0)
        return True

    def _topic_unlocked_event(
        self, source_topic: str, dependent_topic: str
    ) -> TopicUnlocked:
        via: Literal["chain", "gate"] = (
            "gate" if dependent_topic in self._course.gated_topics else "chain"
        )
        return TopicUnlocked(
            source_topic=source_topic,
            dependent_topic=dependent_topic,
            via=via,
        )

    def _expedite_chained_topics(self, exercise: Exercise) -> list[TopicUnlocked]:
        events: list[TopicUnlocked] = []
        for dependent_topic in self._course.word_chained_topics.get(exercise.topic, []):
            if self._expedite_dependent(exercise.word, dependent_topic):
                events.append(
                    self._topic_unlocked_event(exercise.topic, dependent_topic)
                )
        for dependent_topic in self._course.answer_chained_topics.get(
            exercise.topic,
            [],
        ):
            if self._expedite_dependent(exercise.answer, dependent_topic):
                events.append(
                    self._topic_unlocked_event(exercise.topic, dependent_topic)
                )
        return events

    def check_answer(
        self,
        exercise: Exercise,
        answer: str,
    ) -> tuple[Mark, list[TutoringEvent]]:
        correct = answer.strip().lower() == exercise.answer.strip().lower()
        if not exercise.recalls:
            recall_mode = RecallMode.none
        elif correct:
            recall_mode = RecallMode.optional
        else:
            recall_mode = RecallMode.required
        is_new, repetition_interval_before = self._journal.record_mark(
            exercise.question,
            exercise.word,
            exercise.topic,
            correct=correct,
            was_recall_optional=recall_mode == RecallMode.optional,
        )
        repetition_interval_after = self._next_repetition(
            repetition_interval_before, correct
        )
        self._journal.schedule_pair(
            exercise.word,
            exercise.topic,
            repetition_interval=repetition_interval_after,
            # A same-day "learning step" before real spacing kicks in —
            # otherwise a correct first answer would leave nothing to
            # review again that same day (the first-day content shortage
            # new learners used to hit). A correct answer on an
            # already-started pair spaces out by schedule_pair()'s own
            # repetition_interval default instead.
            due_interval=0 if (is_new or not correct) else None,
        )
        events: list[TutoringEvent] = [
            ExerciseAnswered(
                word=exercise.word,
                topic=exercise.topic,
                correct=correct,
                is_new=is_new,
                recall_mode=recall_mode,
                repetition_interval_before=repetition_interval_before,
                repetition_interval_after=repetition_interval_after,
            ),
            *self._expedite_chained_topics(exercise),
        ]
        return Mark(correct=correct, recall=recall_mode), events

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
            repetition_interval = self._journal.get_repetition_interval(
                exercise.word,
                exercise.topic,
            )
            self._journal.schedule_pair(
                exercise.word,
                exercise.topic,
                repetition_interval=max((repetition_interval or 0) // 2, 1),
            )
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
        if not self._get_due_pairs() and not self._get_available_not_scheduled_pairs():
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
