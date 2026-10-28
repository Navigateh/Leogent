import os
from collections.abc import Mapping
from pathlib import Path

from platformdirs import user_config_path as platform_user_config_path
from platformdirs import user_data_path as platform_user_data_path


def user_config_path() -> Path:
    return Path(platform_user_config_path("leogent"))


def data_directory(environ: Mapping[str, str] | None = None) -> Path:
    environment = os.environ if environ is None else environ
    override = environment.get("LEOGENT_HOME", "").strip()
    if override:
        return Path(override).expanduser()
    return Path(platform_user_data_path("leogent"))


def find_project_config(start: Path) -> Path | None:
    current = start.expanduser().resolve()
    if not current.is_dir():
        current = current.parent
    while True:
        candidate = current / ".leogent" / "config.json"
        if candidate.is_file():
            return candidate
        if current.parent == current:
            return None
        current = current.parent
