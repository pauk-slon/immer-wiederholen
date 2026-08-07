import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import Enum
from functools import cached_property
from typing import Final, Literal

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
    interval_days_before: int
    interval_days_after: int


@dataclass(frozen=True)
class TopicUnlocked:
    source_topic: str
    dependent_topic: str
    via: Literal["chain", "gate"]


TutoringEvent = ExerciseAnswered | TopicUnlocked


class Tutor:
    MAX_INTERVAL_DAYS: Final = 60
    REMIND_AFTER: Final = timedelta(hours=24)
    NEW_WORDS_PER_DAY: Final = 7
    EXTRA_NEW_WORDS_GRANT: Final = 3

    def __init__(self, course: Course, journal: dict) -> None:
        self._course = course
        self._today = datetime.now(UTC).date()
        self._journal = Journal(journal, today=self._today)

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
        today = self._today.isoformat()
        return {
            word
            for word, topic in self._word_topics
            if (entry := self._journal.get_schedule_entry(word, topic)) is not None
            and entry.get("introduced_at") == today
        }

    def _new_words_introduced_today_count(self) -> int:
        return len(self._words_introduced_today())

    def grant_extra_new_words(self) -> None:
        extra_today = self._journal.get_extra_new_words_today()
        cap = self.NEW_WORDS_PER_DAY + extra_today
        if len(self._words_introduced_today()) < cap:
            # The cap isn't actually binding right now — most likely a stale
            # "study more" button clicked after the cap reset for a new day.
            # Granting here would silently raise today's cap without the
            # learner having asked for it today.
            return
        self._journal.add_extra_new_words_today(self.EXTRA_NEW_WORDS_GRANT)

    def _due_review_pairs(self) -> list[tuple[str, str]]:
        return [
            (word, topic)
            for word, topic in self._word_topics
            if not self._is_new(word, topic)
            and self._get_due_date(word, topic) <= self._today
        ]

    def _available_new_pairs(self) -> list[tuple[str, str]]:
        return [
            (word, topic)
            for word, topic in self._word_topics
            if self._is_new(word, topic)
            and self._get_due_date(word, topic) <= self._today
        ]

    def _last_pair(self) -> tuple[str, str] | None:
        last_exercise = self._journal.get_last_exercise()
        if last_exercise is None:
            return None
        word = last_exercise.get("word")
        topic = last_exercise.get("topic")
        if word is None or topic is None:
            return None
        return (word, topic)

    def _has_introduced_topic(self, word: str) -> bool:
        # True once the learner has actually answered *any* topic of this
        # word at least once — not merely "has a schedule entry", which a
        # chain/gate can create via _expedite_dependent() without the
        # learner ever having seen it (see introduced_at's own rationale).
        return any(
            (entry := self._journal.get_schedule_entry(word, topic)) is not None
            and entry.get("introduced_at") is not None
            for topic in self._exercises_by_word_topic.get(word, {})
        )

    def _has_any_schedule_entry(self, word: str) -> bool:
        return any(
            self._journal.get_schedule_entry(word, topic) is not None
            for topic in self._exercises_by_word_topic.get(word, {})
        )

    def _word_selection_pools(
        self,
        due_review: list[tuple[str, str]],
        available_new: list[tuple[str, str]],
    ) -> tuple[set[str], set[str], set[str]]:
        # Three tiers, by how "free" a word is to select without spending the
        # daily new-word budget:
        # - free: relevant today (due, or has an available new topic — the
        #   latter defaults to date.min so it's always "available", see
        #   _get_due_date) AND has been actually introduced via some topic —
        #   whether or not that's the same topic that's due/available today.
        #   E.g. a word whose only progressing topic isn't due today, but
        #   which also has a completely untouched topic, still counts as
        #   free via that untouched topic's trivial availability.
        # - queued: relevant today, never introduced, but already has a
        #   schedule entry (expedited via a chain/gate) — prioritized over...
        # - fresh: relevant today, no schedule entry anywhere — genuinely
        #   never touched.
        today_relevant_words = {word for word, _ in due_review + available_new}
        free_words = {
            word for word in today_relevant_words if self._has_introduced_topic(word)
        }
        remaining_words = today_relevant_words - free_words
        queued_words = {
            word for word in remaining_words if self._has_any_schedule_entry(word)
        }
        fresh_words = remaining_words - queued_words
        return free_words, queued_words, fresh_words

    def _select_word(
        self,
        due_review: list[tuple[str, str]],
        available_new: list[tuple[str, str]],
    ) -> str | None:
        free_words, queued_words, fresh_words = self._word_selection_pools(
            due_review, available_new
        )
        budget = max(
            self.NEW_WORDS_PER_DAY
            + self._journal.get_extra_new_words_today()
            - len(self._words_introduced_today()),
            0,
        )
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
        last_pair = self._last_pair()
        if last_pair is not None:
            last_word, _ = last_pair
            without_last_word = {word for word in candidates if word != last_word}
            if without_last_word:
                candidates = without_last_word
        if not candidates:
            return None
        return random.choice(list(candidates))

    def _select_topic(
        self,
        word: str,
        due_review: list[tuple[str, str]],
        available_new: list[tuple[str, str]],
    ) -> str:
        due_topics = [topic for w, topic in due_review if w == word]
        candidate_topics = due_topics or [
            topic for w, topic in available_new if w == word
        ]
        last_pair = self._last_pair()
        if last_pair is not None and last_pair[0] == word:
            without_last_topic = [t for t in candidate_topics if t != last_pair[1]]
            if without_last_topic:
                candidate_topics = without_last_topic
        return random.choice(candidate_topics)

    def next_exercise(self) -> Exercise | None:
        due_review = self._due_review_pairs()
        available_new = self._available_new_pairs()
        due_word_topics = due_review + available_new
        if due_word_topics:
            word = self._select_word(due_review, available_new)
            if word is None:
                return None
            topic = self._select_topic(word, due_review, available_new)
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
        # This is meant to actually predict today's remaining work, unlike
        # next_exercise()'s own word-sampling (_select_word()), which only
        # samples as many words as it needs for one pick at a time: pairs of
        # an already-started word count in full (no budget left to spend on
        # them), but not-yet-started words are capped to the remaining daily
        # budget — one pair per slot, since we can't predict in advance how
        # many topics a chain might cascade into — and further bounded by how
        # many such words actually exist, so a small course doesn't get
        # inflated up to the raw budget number.
        today_words = self._words_introduced_today()
        available = self._available_new_pairs()
        started_word_pairs = sum(1 for word, _ in available if word in today_words)
        not_yet_started_words = {
            word for word, _ in available if word not in today_words
        }
        cap = self.NEW_WORDS_PER_DAY + self._journal.get_extra_new_words_today()
        remaining_word_budget = max(cap - len(today_words), 0)
        return started_word_pairs + min(
            remaining_word_budget, len(not_yet_started_words)
        )

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
        answered_today, correct_today = self._journal.get_answer_stats_today()
        return Progress(
            remaining_today=len(self._due_review_pairs()) + self._new_remaining_today(),
            new_today=self._new_words_introduced_today_count(),
            learning=learning,
            mastered=mastered,
            answered_today=answered_today,
            correct_today=correct_today,
        )

    def _schedule_next_repetition(
        self, exercise: Exercise, correct: bool, *, is_new: bool
    ) -> int:
        schedule_entry = self._journal.get_schedule_entry(
            exercise.word,
            exercise.topic,
            create_if_missing=True,
        )
        if is_new:
            schedule_entry["introduced_at"] = self._today.isoformat()
        if correct:
            interval = min(
                max(schedule_entry["interval_days"] * 2, 1), self.MAX_INTERVAL_DAYS
            )
        else:
            interval = 1
        # A wrong answer is always due again today (unchanged). A pair's very
        # first answer is *also* always due today even if correct — a
        # same-day "learning step" before real spacing kicks in, rather than
        # pushing a correct first answer a full day out and leaving nothing
        # to review again that same day (the first-day content shortage new
        # learners used to hit). Only a correct answer on an already-started
        # pair actually spaces out by the computed interval.
        due_date = (
            self._today
            if (is_new or not correct)
            else self._today + timedelta(days=interval)
        )
        schedule_entry["interval_days"] = interval
        schedule_entry["due_date"] = due_date.isoformat()
        return interval

    def _expedite_dependent(self, word: str, topic: str) -> bool:
        if topic not in self._exercises_by_word_topic.get(word, {}):
            return False
        if self._journal.get_schedule_entry(word, topic) is not None:
            return False
        topic_schedule = self._journal.get_topic_schedule(word, create_if_missing=True)
        topic_schedule[topic] = ScheduleEntry(
            interval_days=0,
            due_date=self._today.isoformat(),
        )
        return True

    def _topic_unlocked_event(
        self, source_topic: str, dependent_topic: str
    ) -> TopicUnlocked:
        via: Literal["chain", "gate"] = (
            "gate" if dependent_topic in self._course.gated_topics else "chain"
        )
        return TopicUnlocked(
            source_topic=source_topic, dependent_topic=dependent_topic, via=via
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
        self, exercise: Exercise, answer: str
    ) -> tuple[Mark, list[TutoringEvent]]:
        correct = answer.strip().lower() == exercise.answer.strip().lower()
        if not exercise.recalls:
            recall_mode = RecallMode.none
        elif correct:
            recall_mode = RecallMode.optional
        else:
            recall_mode = RecallMode.required
        mark = Mark(correct=correct, recall=recall_mode)
        self._journal.record_answer_today(correct=correct)
        existing_entry = self._journal.get_schedule_entry(exercise.word, exercise.topic)
        interval_days_before = (
            existing_entry["interval_days"] if existing_entry is not None else 0
        )
        is_new = self._is_new(exercise.word, exercise.topic)
        self._journal.record_mark(
            exercise.question,
            exercise.word,
            exercise.topic,
            was_recall_optional=recall_mode == RecallMode.optional,
        )
        interval_days_after = self._schedule_next_repetition(
            exercise, correct, is_new=is_new
        )
        events: list[TutoringEvent] = [
            ExerciseAnswered(
                word=exercise.word,
                topic=exercise.topic,
                correct=correct,
                is_new=is_new,
                recall_mode=recall_mode,
                interval_days_before=interval_days_before,
                interval_days_after=interval_days_after,
            ),
            *self._expedite_chained_topics(exercise),
        ]
        return mark, events

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
                self._today + timedelta(days=interval)
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
