"""Project-level idf.py extension loader for managed components.

This file is copied to `${PROJECT_DIR}/idf_ext.py` by the flashless component
on ESP-IDF 5.x projects when no project-level extension file exists.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any


def _load_module(path: Path) -> ModuleType | None:
    spec = importlib.util.spec_from_file_location(f"managed_ext_{path.parent.name}", path)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _merge_actions(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    base.setdefault("global_options", [])
    base.setdefault("actions", {})

    for opt in extra.get("global_options", []) or []:
        if opt not in base["global_options"]:
            base["global_options"].append(opt)

    for name, action in (extra.get("actions", {}) or {}).items():
        base["actions"][name] = action

    return base


def action_extensions(base_actions: dict[str, Any], project_path: str) -> dict[str, Any]:
    managed_components = Path(project_path) / "managed_components"
    merged: dict[str, Any] = {"global_options": [], "actions": {}}

    if not managed_components.exists():
        return merged

    for ext_path in sorted(managed_components.glob("*/idf_ext.py")):
        try:
            module = _load_module(ext_path)
            if module is None or not hasattr(module, "action_extensions"):
                continue
            ext_actions = module.action_extensions(base_actions, project_path)
            if isinstance(ext_actions, dict):
                _merge_actions(merged, ext_actions)
        except Exception:
            # Keep idf.py usable even if one component extension is broken.
            continue

    return merged
