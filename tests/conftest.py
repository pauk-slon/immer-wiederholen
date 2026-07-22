from contextlib import contextmanager, AbstractContextManager
from pathlib import Path
from typing import Any, Generator, Protocol

import pytest
import yaml


pytest_plugins = [
    "tests.plugins.telegram",
    "tests.plugins.aiogram",
    "tests.plugins.exercises",
]


class TmpYamlFile(Protocol):
    def __call__(
        self,
        data: Any,
        *,
        filename: str = "data.yaml",
    ) -> AbstractContextManager[Path]: ...


@pytest.fixture
def tmp_yaml_file(tmp_path: Path) -> TmpYamlFile:
    @contextmanager
    def factory(data: Any, *, filename: str = "data.yaml") -> Generator[Path]:
        text = yaml.safe_dump(data)
        yaml_file = tmp_path / filename
        yaml_file.write_text(text)
        yield yaml_file
        yaml_file.unlink(missing_ok=True)

    return factory
