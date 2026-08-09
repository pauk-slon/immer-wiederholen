from wiederholen.bot.bootstrap import load_feature_flags


def test_load_feature_flags_defaults_to_empty_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("FEATURE_FLAGS", raising=False)

    assert load_feature_flags() == {}


def test_load_feature_flags_parses_the_env_var(monkeypatch) -> None:
    monkeypatch.setenv("FEATURE_FLAGS", "ai_exercises:1,2")

    assert load_feature_flags() == {"ai_exercises": frozenset({1, 2})}
