from pathlib import Path
from unittest.mock import patch

from litestar import Litestar

from tests.conftest import TmpYamlFile
from tests.plugins.curriculum import make_exercise_data
from wiederholen.web.__main__ import main


def test_main_runs_uvicorn_with_the_created_app(
    monkeypatch,
    tmp_yaml_file: TmpYamlFile,
) -> None:
    monkeypatch.setenv("WEB_ALLOWED_ORIGINS", "https://example.com")
    monkeypatch.setenv("WEB_COOKIE_DOMAIN", "example.com")
    exercise_data = make_exercise_data(word="warten")
    with (
        tmp_yaml_file([exercise_data], filename="exercises.yaml") as path,
        patch("wiederholen.web.__main__.uvicorn.run") as mock_run,
    ):
        monkeypatch.setenv("COURSE_PATH", str(Path(path).parent))
        main()

    mock_run.assert_called_once()
    app, kwargs = mock_run.call_args[0][0], mock_run.call_args[1]
    assert isinstance(app, Litestar)
    assert kwargs["host"] == "0.0.0.0"
    assert kwargs["port"] == 8000
