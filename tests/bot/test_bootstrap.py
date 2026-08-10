from pathlib import Path

from anthropic import AsyncAnthropic

from wiederholen.bot.bootstrap import (
    load_anthropic_client,
    load_authoring_guide,
    load_feature_flags,
)


def test_load_feature_flags_defaults_to_empty_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("FEATURE_FLAGS", raising=False)

    assert load_feature_flags() == {}


def test_load_feature_flags_parses_the_env_var(monkeypatch) -> None:
    monkeypatch.setenv("FEATURE_FLAGS", "ai_exercises:1,2")

    assert load_feature_flags() == {"ai_exercises": frozenset({1, 2})}


def test_load_anthropic_client_is_none_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    assert load_anthropic_client() is None


def test_load_anthropic_client_builds_a_client_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    client = load_anthropic_client()

    assert isinstance(client, AsyncAnthropic)


def test_load_authoring_guide_is_none_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("AUTHORING_GUIDE_PATH", raising=False)

    assert load_authoring_guide() is None


def test_load_authoring_guide_reads_the_configured_file(
    monkeypatch, tmp_path: Path
) -> None:
    guide_path = tmp_path / "CLAUDE.md"
    guide_path.write_text("some guide text")
    monkeypatch.setenv("AUTHORING_GUIDE_PATH", str(guide_path))

    assert load_authoring_guide() == "some guide text"
