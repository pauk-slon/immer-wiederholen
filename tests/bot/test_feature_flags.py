from wiederholen.bot.feature_flags import has_feature, parse_feature_flags


def test_parse_feature_flags_empty_string_yields_no_flags() -> None:
    assert parse_feature_flags("") == {}


def test_parse_feature_flags_parses_a_single_flag() -> None:
    assert parse_feature_flags("ai_exercises:1,2") == {
        "ai_exercises": frozenset({1, 2}),
    }


def test_parse_feature_flags_parses_multiple_flags() -> None:
    assert parse_feature_flags("ai_exercises:1,2;other_flag:3") == {
        "ai_exercises": frozenset({1, 2}),
        "other_flag": frozenset({3}),
    }


def test_parse_feature_flags_tolerates_a_trailing_semicolon() -> None:
    assert parse_feature_flags("ai_exercises:1;") == {
        "ai_exercises": frozenset({1}),
    }


def test_parse_feature_flags_tolerates_surrounding_whitespace() -> None:
    assert parse_feature_flags(" ai_exercises : 1 , 2 ; other_flag : 3 ") == {
        "ai_exercises": frozenset({1, 2}),
        "other_flag": frozenset({3}),
    }


def test_parse_feature_flags_a_flag_with_no_chat_ids_is_empty() -> None:
    assert parse_feature_flags("ai_exercises:") == {"ai_exercises": frozenset()}


def test_has_feature_is_true_for_a_listed_chat_id() -> None:
    flags = parse_feature_flags("ai_exercises:1,2")
    assert has_feature(flags, "ai_exercises", 1) is True


def test_has_feature_is_false_for_an_unlisted_chat_id() -> None:
    flags = parse_feature_flags("ai_exercises:1,2")
    assert has_feature(flags, "ai_exercises", 3) is False


def test_has_feature_is_false_for_an_unknown_flag() -> None:
    flags = parse_feature_flags("ai_exercises:1")
    assert has_feature(flags, "other_flag", 1) is False


def test_has_feature_is_false_when_no_flags_are_configured() -> None:
    assert has_feature({}, "ai_exercises", 1) is False
