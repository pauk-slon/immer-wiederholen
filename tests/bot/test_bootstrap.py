from unittest.mock import Mock

import pytest
from anthropic import AsyncAnthropic

from tests.plugins.curriculum import make_exercise
from wiederholen.bot.bootstrap import (
    check_lesson_recall_config,
    load_anthropic_client,
    load_cue_store,
    load_feature_flags,
)
from wiederholen.school import CachedCueStore, Course


def test_load_feature_flags_defaults_to_empty_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("BOT_FEATURE_FLAGS", raising=False)

    assert load_feature_flags() == {}


def test_load_feature_flags_parses_the_env_var(monkeypatch) -> None:
    monkeypatch.setenv("BOT_FEATURE_FLAGS", "some_flag:1,2")

    assert load_feature_flags() == {"some_flag": frozenset({1, 2})}


def test_load_anthropic_client_is_none_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    assert load_anthropic_client() is None


def test_load_anthropic_client_builds_a_client_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    client = load_anthropic_client()

    assert isinstance(client, AsyncAnthropic)


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


def test_lesson_recall_config_needs_nothing_without_an_api_key() -> None:
    check_lesson_recall_config({}, None, Course([make_exercise()]))
    check_lesson_recall_config(
        {"lesson_recall_unlimited": frozenset()}, None, Course([make_exercise()])
    )


_WITH_GUIDE = Course([make_exercise()], lesson_recall_guide="Guide")


def test_lesson_recall_config_passes_with_a_client_and_a_guide() -> None:
    check_lesson_recall_config(
        {"lesson_recall_unlimited": frozenset({1})},
        Mock(spec=AsyncAnthropic),
        _WITH_GUIDE,
    )


def test_lesson_recall_unlimited_flag_without_an_api_key_fails() -> None:
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        check_lesson_recall_config(
            {"lesson_recall_unlimited": frozenset({1})}, None, _WITH_GUIDE
        )


def test_an_api_key_without_a_guide_fails() -> None:
    with pytest.raises(RuntimeError, match="lesson_recall.md"):
        check_lesson_recall_config(
            {}, Mock(spec=AsyncAnthropic), Course([make_exercise()])
        )
