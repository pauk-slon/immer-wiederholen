from tests.plugins.curriculum import make_exercise
from wiederholen.school.curriculum import Course, shuffle_word_bank


def test_restricted_to_keeps_only_exercises_for_the_given_topics() -> None:
    government = make_exercise(word="warten", topic="government")
    partizip = make_exercise(word="sprechen", topic="partizip_ii")
    course = Course([government, partizip])

    restricted = course.restricted_to(["government"])

    assert restricted.exercises == [government]


def test_restricted_to_accepts_several_topics() -> None:
    government = make_exercise(word="warten", topic="government")
    partizip = make_exercise(word="sprechen", topic="partizip_ii")
    praeteritum = make_exercise(word="sprechen", topic="praeteritum")
    course = Course([government, partizip, praeteritum])

    restricted = course.restricted_to(["partizip_ii", "praeteritum"])

    assert list(restricted.exercises) == [partizip, praeteritum]


def test_restricted_to_leaves_chains_gates_and_instructions_untouched() -> None:
    government = make_exercise(word="warten", topic="government")
    meaning = make_exercise(word="auf", topic="preposition_meaning")
    course = Course(
        [government, meaning],
        answer_chained_topics={"government": ["preposition_meaning"]},
        gated_topics=frozenset({"preposition_meaning"}),
        topic_instructions={"preposition_meaning": {"ru": "x", "en": "y"}},
        ai_generatable_topics=frozenset({"government"}),
    )

    restricted = course.restricted_to(["government"])

    # Excluded here, but not stripped from the config maps — a chain to it
    # simply never finds an exercise to expedite (see restricted_to()'s own
    # docstring-equivalent comment), the same as any other dependent topic
    # with no exercises.
    assert restricted.answer_chained_topics == {"government": ["preposition_meaning"]}
    assert restricted.gated_topics == frozenset({"preposition_meaning"})
    assert restricted.topic_instructions == {
        "preposition_meaning": {"ru": "x", "en": "y"}
    }
    assert restricted.ai_generatable_topics == frozenset({"government"})


def test_shuffle_word_bank_returns_a_permutation_of_the_input() -> None:
    word_bank = ["sie", "wohnt", "in Hamburg"]

    shuffled = shuffle_word_bank(word_bank)

    assert sorted(shuffled) == sorted(word_bank)


def test_shuffle_word_bank_never_returns_the_original_order() -> None:
    word_bank = ["sie", "wohnt", "in Hamburg"]

    for _ in range(50):
        assert shuffle_word_bank(word_bank) != word_bank


def test_shuffle_word_bank_returns_a_single_chunk_unchanged() -> None:
    # No other permutation exists to prefer — reshuffling would otherwise
    # loop forever comparing a one-element list against itself.
    assert shuffle_word_bank(["Hallo"]) == ["Hallo"]
