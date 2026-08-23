"""`SelectablePairs` — `next_exercise()`'s word/topic selection engine,
factored out because its logic is entirely pairs-derived: it needs only a
handful of externally-supplied primitives (`introduced_words`, `budget`,
`last_pair`), never `Tutor`/`StudentRecord` state directly. `Tutor` gathers
those few values once and passes them in, rather than this class reaching
into student_record itself — which keeps it student_record-agnostic, same
as the rest of this package.
"""

import random
from dataclasses import dataclass


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
        # - free: introduced via some topic already (StudentRecord.get_words_already_introduced()
        #   — a single scan of the record, not a per-word lookup) — regardless of
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
