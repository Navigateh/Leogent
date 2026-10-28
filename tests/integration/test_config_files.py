import json
from pathlib import Path

import pytest

from leogent.config.loader import load_config_from_search
from leogent.config.paths import data_directory, find_project_config


def _write_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "default_provider": "local",
                "providers": {
                    "local": {
                        "type": "openai-compatible",
                        "base_url": "http://localhost:11434/v1",
                        "model": "local-model",
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def test_find_project_config_uses_nearest_parent(tmp_path: Path) -> None:
    project_config = tmp_path / ".leogent" / "config.json"
    nested = tmp_path / "src" / "package"
    nested.mkdir(parents=True)
    _write_config(project_config)

    assert find_project_config(nested) == project_config


def test_leogent_home_overrides_user_data_directory(tmp_path: Path) -> None:
    custom_home = tmp_path / "custom-data"

    assert data_directory({"LEOGENT_HOME": str(custom_home)}) == custom_home


def test_load_config_from_search_uses_discovered_project_file(tmp_path: Path) -> None:
    project_config = tmp_path / ".leogent" / "config.json"
    nested = tmp_path / "nested"
    nested.mkdir()
    _write_config(project_config)

    config = load_config_from_search(
        start=nested,
        global_path=tmp_path / "missing-global.json",
        environ={},
    )

    assert config.default_provider == "local"


def test_empty_leogent_home_uses_default_data_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LEOGENT_HOME", "")

    result = data_directory()

    assert result.name == "leogent"
    assert result != tmp_path
