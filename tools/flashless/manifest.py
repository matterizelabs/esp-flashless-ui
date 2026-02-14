"""Manifest discovery and validation for flashless."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import FlashlessError


@dataclass(frozen=True)
class ApiMapping:
    method: str
    path: str
    fixture: str
    status: int
    headers: dict[str, str]


@dataclass(frozen=True)
class UiSettings:
    base_path: str
    asset_root: Path
    entry_file: str
    routes: tuple[str, ...]
    spa_fallback: bool
    cache_policy: dict[str, Any]


@dataclass(frozen=True)
class ApiSettings:
    mode: str
    fixtures_dir: Path
    mappings: tuple[ApiMapping, ...]


@dataclass(frozen=True)
class ValidationSettings:
    required_files: tuple[str, ...]
    disallow_extra_routes: bool


@dataclass(frozen=True)
class Manifest:
    source_path: Path
    version: str
    ui: UiSettings
    api: ApiSettings
    validation: ValidationSettings


def discover_manifest(project_dir: Path, override: str | None) -> Path:
    if override:
        manifest_path = Path(override)
        if not manifest_path.is_absolute():
            manifest_path = project_dir / manifest_path
        return manifest_path

    candidates = (
        project_dir / "flashless.manifest.json",
        project_dir / "web" / "flashless.manifest.json",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate

    hint = (
        "Missing flashless manifest. Create one at 'flashless.manifest.json' or 'web/flashless.manifest.json'. "
        "You can copy 'examples/flashless.manifest.json' from the component."
    )
    raise FlashlessError(hint)


def load_manifest(manifest_path: Path, project_dir: Path, fixtures_override: str | None = None) -> Manifest:
    if not manifest_path.exists():
        raise FlashlessError(f"Manifest file not found: {manifest_path}")

    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FlashlessError(f"Manifest is not valid JSON: {manifest_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise FlashlessError("Manifest root must be a JSON object.")

    version = raw.get("version")
    if version != "1":
        raise FlashlessError("Manifest 'version' must be the string '1'.")

    ui_raw = _as_object(raw, "ui")
    api_raw = _as_object(raw, "api", required=False)
    validation_raw = _as_object(raw, "validation", required=False)

    base_path = _normalize_base_path(ui_raw.get("basePath", "/"))
    asset_root = _resolve_project_path(project_dir, _as_string(ui_raw, "assetRoot"))
    entry_file = _as_string(ui_raw, "entryFile", default="index.html")
    routes = _as_route_list(ui_raw.get("routes", ["/"]))
    spa_fallback = _as_bool(ui_raw.get("spaFallback", True), field="ui.spaFallback")

    cache_policy_raw = ui_raw.get("cachePolicy", {})
    if cache_policy_raw is None:
        cache_policy_raw = {}
    if not isinstance(cache_policy_raw, dict):
        raise FlashlessError("Manifest field 'ui.cachePolicy' must be an object.")

    cache_policy = {
        "maxAgeSeconds": _as_int(cache_policy_raw.get("maxAgeSeconds", 0), "ui.cachePolicy.maxAgeSeconds", minimum=0),
        "etag": _as_bool(cache_policy_raw.get("etag", True), field="ui.cachePolicy.etag"),
        "gzip": _as_bool(cache_policy_raw.get("gzip", False), field="ui.cachePolicy.gzip"),
    }

    mode = "mock"
    mappings_raw: list[dict[str, Any]] = []
    fixtures_dir = project_dir / "ui-fixtures"
    if api_raw:
        mode = _as_string(api_raw, "mode", default="mock").lower()
        if mode not in {"mock", "proxy"}:
            raise FlashlessError("Manifest field 'api.mode' must be either 'mock' or 'proxy'.")
        fixtures_dir = _resolve_project_path(project_dir, _as_string(api_raw, "fixturesDir", default="ui-fixtures"))
        mappings_raw = _as_list(api_raw.get("map", []), "api.map")

    if fixtures_override:
        fixtures_dir = _resolve_project_path(project_dir, fixtures_override)

    mappings: list[ApiMapping] = []
    for index, mapping_raw in enumerate(mappings_raw):
        if not isinstance(mapping_raw, dict):
            raise FlashlessError(f"Manifest field 'api.map[{index}]' must be an object.")
        method = _as_string(mapping_raw, "method").upper()
        path = _normalize_route(_as_string(mapping_raw, "path"))
        fixture = _as_string(mapping_raw, "fixture")
        status = _as_int(mapping_raw.get("status", 200), f"api.map[{index}].status", minimum=100)
        headers_raw = mapping_raw.get("headers", {})
        if not isinstance(headers_raw, dict):
            raise FlashlessError(f"Manifest field 'api.map[{index}].headers' must be an object.")
        headers = {str(k): str(v) for k, v in headers_raw.items()}
        mappings.append(ApiMapping(method=method, path=path, fixture=fixture, status=status, headers=headers))

    required_files = (entry_file,)
    disallow_extra_routes = False
    if validation_raw:
        required_files = tuple(_as_path_list(validation_raw.get("requiredFiles", [entry_file]), "validation.requiredFiles"))
        disallow_extra_routes = _as_bool(
            validation_raw.get("disallowExtraRoutes", False), field="validation.disallowExtraRoutes"
        )

    manifest = Manifest(
        source_path=manifest_path,
        version=version,
        ui=UiSettings(
            base_path=base_path,
            asset_root=asset_root,
            entry_file=entry_file,
            routes=tuple(routes),
            spa_fallback=spa_fallback,
            cache_policy=cache_policy,
        ),
        api=ApiSettings(mode=mode, fixtures_dir=fixtures_dir, mappings=tuple(mappings)),
        validation=ValidationSettings(required_files=required_files, disallow_extra_routes=disallow_extra_routes),
    )
    validate_manifest_paths(manifest)
    return manifest


def validate_manifest_paths(manifest: Manifest) -> None:
    if not manifest.ui.asset_root.exists() or not manifest.ui.asset_root.is_dir():
        raise FlashlessError(
            f"Asset root does not exist or is not a directory: {manifest.ui.asset_root}. "
            "Run your frontend build or update ui.assetRoot in the manifest."
        )


def _as_object(raw: dict[str, Any], field: str, required: bool = True) -> dict[str, Any]:
    value = raw.get(field)
    if value is None:
        if required:
            raise FlashlessError(f"Manifest field '{field}' is required.")
        return {}
    if not isinstance(value, dict):
        raise FlashlessError(f"Manifest field '{field}' must be an object.")
    return value


def _as_list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise FlashlessError(f"Manifest field '{field}' must be an array.")
    return value


def _as_string(raw: dict[str, Any], field: str, default: str | None = None) -> str:
    value = raw.get(field, default)
    if value is None or not isinstance(value, str) or not value.strip():
        raise FlashlessError(f"Manifest field '{field}' must be a non-empty string.")
    return value.strip()


def _as_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise FlashlessError(f"Manifest field '{field}' must be a boolean.")
    return value


def _as_int(value: Any, field: str, minimum: int | None = None) -> int:
    if not isinstance(value, int):
        raise FlashlessError(f"Manifest field '{field}' must be an integer.")
    if minimum is not None and value < minimum:
        raise FlashlessError(f"Manifest field '{field}' must be >= {minimum}.")
    return value


def _as_path_list(value: Any, field: str) -> list[str]:
    items = _as_list(value, field)
    result: list[str] = []
    for index, item in enumerate(items):
        if not isinstance(item, str) or not item.strip():
            raise FlashlessError(f"Manifest field '{field}[{index}]' must be a non-empty string.")
        result.append(item)
    return result


def _as_route_list(value: Any) -> list[str]:
    routes = _as_list(value, "ui.routes")
    normalized: list[str] = []
    for index, route in enumerate(routes):
        if not isinstance(route, str) or not route.strip():
            raise FlashlessError(f"Manifest field 'ui.routes[{index}]' must be a non-empty string.")
        normalized.append(_normalize_route(route))
    return normalized


def _normalize_base_path(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FlashlessError("Manifest field 'ui.basePath' must be a non-empty string.")
    cleaned = "/" + value.strip().strip("/")
    if cleaned == "":
        cleaned = "/"
    if value.strip() == "/":
        return "/"
    return cleaned


def _normalize_route(route: str) -> str:
    cleaned = "/" + route.strip().lstrip("/")
    if route.strip() == "/":
        return "/"
    if cleaned != "/" and cleaned.endswith("/") and not cleaned.endswith("/*"):
        cleaned = cleaned[:-1]
    return cleaned


def _resolve_project_path(project_dir: Path, path_value: str) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = project_dir / path
    return path.resolve()


def route_matches(pattern: str, route: str) -> bool:
    if pattern == route:
        return True
    if pattern.endswith("/*"):
        prefix = pattern[:-1]
        return route.startswith(prefix)
    return False
