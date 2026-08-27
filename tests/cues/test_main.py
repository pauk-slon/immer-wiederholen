from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from tests.conftest import TmpYamlFile
from tests.plugins.curriculum import ExerciseData, make_exercise_data
from wiederholen.cues.__main__ import main, run


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_yaml_file: TmpYamlFile) -> Generator[None]:
    monkeypatch.setenv("R2_ACCOUNT_ID", "acc")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("R2_BUCKET", "images")
    monkeypatch.setenv("R2_PUBLIC_URL_BASE", "https://images.example.com")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "token")
    yield None


@pytest.fixture
def course_path(tmp_yaml_file: TmpYamlFile, exercises: list[ExerciseData]):
    topics_data = {"preposition_meaning": {"cue_generation": True}}
    with (
        tmp_yaml_file(exercises, filename="exercises.yaml") as exercises_path,
        tmp_yaml_file(topics_data, filename="topics.yaml"),
    ):
        yield exercises_path.parent


@pytest.fixture
def exercises() -> list[ExerciseData]:
    return [
        make_exercise_data(
            word="fahren",
            topic="preposition_meaning",
            description={"ru": "x", "en": "A train in a tunnel."},
        )
    ]


def _mock_store(*, existing_url: str | None = None) -> Mock:
    store = Mock()
    store.get_cue_url = AsyncMock(return_value=existing_url)
    store.upload_cue = AsyncMock()
    return store


async def test_generates_an_image_for_an_eligible_exercise_without_one(
    monkeypatch, course_path
) -> None:
    monkeypatch.setenv("COURSE_PATH", str(course_path))
    store = _mock_store(existing_url=None)
    with (
        patch("wiederholen.cues.__main__.R2CueStore", return_value=store),
        patch(
            "wiederholen.cues.__main__.generate_exercise_cue",
            AsyncMock(return_value=b"png-bytes"),
        ),
    ):
        await run()

    store.upload_cue.assert_awaited_once()
    exercise_arg, bytes_arg = store.upload_cue.call_args.args
    assert exercise_arg.word == "fahren"
    assert bytes_arg == b"png-bytes"


async def test_skips_an_exercise_that_already_has_an_image(
    monkeypatch, course_path
) -> None:
    monkeypatch.setenv("COURSE_PATH", str(course_path))
    store = _mock_store(existing_url="https://images.example.com/already-there")
    generate = AsyncMock(return_value=b"png-bytes")
    with (
        patch("wiederholen.cues.__main__.R2CueStore", return_value=store),
        patch("wiederholen.cues.__main__.generate_exercise_cue", generate),
    ):
        await run()

    generate.assert_not_awaited()
    store.upload_cue.assert_not_awaited()


async def test_skips_an_exercise_whose_topic_is_not_eligible(
    monkeypatch, tmp_yaml_file: TmpYamlFile
) -> None:
    exercise = make_exercise_data(word="warten", topic="government")
    with tmp_yaml_file([exercise], filename="exercises.yaml") as path:
        monkeypatch.setenv("COURSE_PATH", str(path.parent))
        store = _mock_store()
        with patch("wiederholen.cues.__main__.R2CueStore", return_value=store):
            await run()

    store.get_cue_url.assert_not_awaited()


async def test_skips_when_generation_returns_none(monkeypatch, course_path) -> None:
    monkeypatch.setenv("COURSE_PATH", str(course_path))
    store = _mock_store(existing_url=None)
    with (
        patch("wiederholen.cues.__main__.R2CueStore", return_value=store),
        patch(
            "wiederholen.cues.__main__.generate_exercise_cue",
            AsyncMock(return_value=None),
        ),
    ):
        await run()

    store.upload_cue.assert_not_awaited()


async def test_a_failed_generation_does_not_stop_the_run(
    monkeypatch, tmp_yaml_file: TmpYamlFile
) -> None:
    exercises = [
        make_exercise_data(
            word="fahren",
            topic="preposition_meaning",
            description={"ru": "x", "en": "fails"},
        ),
        make_exercise_data(
            word="gehen",
            topic="preposition_meaning",
            description={"ru": "x", "en": "succeeds"},
        ),
    ]
    topics_data = {"preposition_meaning": {"cue_generation": True}}
    with (
        tmp_yaml_file(exercises, filename="exercises.yaml") as path,
        tmp_yaml_file(topics_data, filename="topics.yaml"),
    ):
        monkeypatch.setenv("COURSE_PATH", str(path.parent))
        store = _mock_store(existing_url=None)
        generate = AsyncMock(side_effect=[httpx.HTTPError("boom"), b"png-bytes"])
        with (
            patch("wiederholen.cues.__main__.R2CueStore", return_value=store),
            patch("wiederholen.cues.__main__.generate_exercise_cue", generate),
        ):
            await run()

    assert store.upload_cue.await_count == 1


def test_main_configures_logging_and_runs(monkeypatch) -> None:
    run_mock = AsyncMock()
    with (
        patch("wiederholen.cues.__main__.run", run_mock),
        patch("wiederholen.cues.__main__.logging.basicConfig") as basic_config,
    ):
        main()

    basic_config.assert_called_once()
    run_mock.assert_awaited_once()
