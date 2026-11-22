from pathlib import Path
from unittest.mock import Mock

import pytest
from anthropic import AsyncAnthropic

from tests.plugins.curriculum import make_exercise
from wiederholen.bot.bootstrap import (
    check_lesson_recall_config,
    load_anthropic_client,
    load_authoring_guide,
    load_cue_store,
    load_feature_flags,
)
from wiederholen.school import CachedCueStore, Course


def test_load_feature_flags_defaults_to_empty_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("BOT_FEATURE_FLAGS", raising=False)

    assert load_feature_flags() == {}


def test_load_feature_flags_parses_the_env_var(monkeypatch) -> None:
    monkeypatch.setenv("BOT_FEATURE_FLAGS", "ai_exercises:1,2")

    assert load_feature_flags() == {"ai_exercises": frozenset({1, 2})}


def test_load_anthropic_client_is_none_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    assert load_anthropic_client() is None


def test_load_anthropic_client_builds_a_client_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    client = load_anthropic_client()

    assert isinstance(client, AsyncAnthropic)


def test_load_anthropic_client_limits_the_wait_for_a_generation(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    client = load_anthropic_client()

    assert client is not None
    assert client.timeout == 60.0
    assert client.max_retries == 1


def test_load_cue_store_is_none_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("R2_ACCOUNT_ID", raising=False)

    assert load_cue_store() is None


def test_load_cue_store_builds_a_cached_r2_store_when_configured(
    monkeypatch,
) -> None:
    monkeypatch.setenv("R2_ACCOUNT_ID", "acc")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("R2_BUCKET", "images")
    monkeypatch.setenv("R2_PUBLIC_URL_BASE", "https://images.example.com")

    store = load_cue_store()

    assert isinstance(store, CachedCueStore)


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


def test_load_authoring_guide_cuts_off_the_deploying_section(
    monkeypatch, tmp_path: Path
) -> None:
    guide_path = tmp_path / "CLAUDE.md"
    guide_path.write_text(
        "# intro\n\n## Exercises\n\nsome rules\n\n"
        "## Deploying\n\ncompose.yaml stuff\n\n## Landing page\n\nmore stuff"
    )
    monkeypatch.setenv("AUTHORING_GUIDE_PATH", str(guide_path))

    guide = load_authoring_guide()

    assert guide is not None
    assert "some rules" in guide
    assert "compose.yaml" not in guide
    assert "Landing page" not in guide


_WITH_GUIDE = Course([make_exercise()], lesson_recall_guide="Guide")


def test_lesson_recall_config_needs_nothing_without_the_flag() -> None:
    check_lesson_recall_config({}, None, Course([make_exercise()]))
    check_lesson_recall_config(
        {"lesson_recall": frozenset()}, None, Course([make_exercise()])
    )


def test_lesson_recall_config_passes_with_a_client_and_a_guide() -> None:
    check_lesson_recall_config(
        {"lesson_recall": frozenset({1})}, Mock(spec=AsyncAnthropic), _WITH_GUIDE
    )


def test_lesson_recall_flag_without_an_api_key_fails() -> None:
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        check_lesson_recall_config({"lesson_recall": frozenset({1})}, None, _WITH_GUIDE)


def test_lesson_recall_flag_without_a_guide_fails() -> None:
    with pytest.raises(RuntimeError, match="lesson_recall.md"):
        check_lesson_recall_config(
            {"lesson_recall": frozenset({1})},
            Mock(spec=AsyncAnthropic),
            Course([make_exercise()]),
        )
