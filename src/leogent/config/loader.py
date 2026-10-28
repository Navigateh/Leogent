import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError

from leogent.config.models import AppConfig, ProviderConfig, TransformersProviderConfig
from leogent.config.paths import find_project_config, user_config_path
from leogent.domain.errors import ConfigurationError

JsonMapping = dict[str, Any]


def _provider_mappings(data: JsonMapping) -> dict[str, JsonMapping]:
    providers = data.get("providers")
    if not isinstance(providers, dict):
        return {}
    mappings: dict[str, JsonMapping] = {}
    for name, value in cast(dict[object, object], providers).items():
        if isinstance(name, str) and isinstance(value, dict):
            mappings[name] = cast(JsonMapping, value)
    return mappings


def _read_json_mapping(path: Path | None) -> JsonMapping:
    if path is None or not path.exists():
        return {}
    if not path.is_file():
        raise ConfigurationError(f"Configuration path is not a file: {path}")
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as error:
        raise ConfigurationError(f"Unable to read configuration file: {path}") from error
    except json.JSONDecodeError as error:
        raise ConfigurationError(
            f"Configuration must be valid JSON: {path}:{error.lineno}:{error.colno}"
        ) from error
    if not isinstance(raw, dict):
        raise ConfigurationError(f"Configuration must be a JSON object: {path}")
    raw_mapping = cast(dict[object, object], raw)
    if not all(isinstance(key, str) for key in raw_mapping):
        raise ConfigurationError(f"Configuration keys must be strings: {path}")
    return {str(key): value for key, value in raw_mapping.items()}


def _merge_mappings(base: JsonMapping, override: JsonMapping) -> JsonMapping:
    merged = dict(base)
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _merge_mappings(
                cast(JsonMapping, current),
                cast(JsonMapping, value),
            )
        else:
            merged[key] = value
    return merged


def _format_validation_error(error: ValidationError) -> str:
    details: list[str] = []
    for item in error.errors(
        include_input=False,
        include_url=False,
        include_context=False,
    ):
        location = ".".join(str(part) for part in item["loc"])
        details.append(f"{location}: {item['msg']}")
    return "; ".join(details)


def _resolve_provider_paths(
    merged: JsonMapping,
    global_data: JsonMapping,
    project_data: JsonMapping,
    global_path: Path | None,
    project_path: Path | None,
) -> None:
    project_providers = _provider_mappings(project_data)
    global_providers = _provider_mappings(global_data)
    for name, provider in _provider_mappings(merged).items():
        if provider.get("type") != "transformers":
            continue
        raw_path = provider.get("model_path")
        if not isinstance(raw_path, str):
            continue
        project_override = project_providers.get(name, {})
        if "model_path" in project_override and project_path is not None:
            base_directory = project_path.parent
        elif name in global_providers and global_path is not None:
            base_directory = global_path.parent
        elif project_path is not None:
            base_directory = project_path.parent
        else:
            continue
        model_path = Path(raw_path).expanduser()
        if not model_path.is_absolute():
            model_path = base_directory / model_path
        provider["model_path"] = str(model_path.resolve())


def load_config(
    global_path: Path | None,
    project_path: Path | None,
    environ: Mapping[str, str] | None = None,
) -> AppConfig:
    if not any(path is not None and path.exists() for path in (global_path, project_path)):
        raise ConfigurationError(
            "No Leogent configuration found. Create a global config or .leogent/config.json."
        )

    global_data = _read_json_mapping(global_path)
    project_data = _read_json_mapping(project_path)
    merged = _merge_mappings(global_data, project_data)
    _resolve_provider_paths(
        merged,
        global_data,
        project_data,
        global_path,
        project_path,
    )
    environment = os.environ if environ is None else environ
    default_provider = environment.get("LEOGENT_DEFAULT_PROVIDER", "").strip()
    if default_provider:
        merged["default_provider"] = default_provider

    try:
        return AppConfig.model_validate(merged)
    except ValidationError as error:
        raise ConfigurationError(
            f"Invalid Leogent configuration: {_format_validation_error(error)}"
        ) from None


def load_config_from_search(
    start: Path,
    global_path: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> AppConfig:
    resolved_global_path = (
        global_path if global_path is not None else user_config_path() / "config.json"
    )
    return load_config(
        resolved_global_path,
        find_project_config(start),
        environ,
    )


def resolve_api_key(
    profile: ProviderConfig,
    environ: Mapping[str, str] | None = None,
) -> str | None:
    if isinstance(profile, TransformersProviderConfig):
        return None
    if profile.api_key_env is None:
        return None
    environment = os.environ if environ is None else environ
    value = environment.get(profile.api_key_env)
    return value or None
