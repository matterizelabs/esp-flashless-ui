"""Report generation for flashless."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .manifest import Manifest
from .server import ValidationResult


def write_report(
    *,
    build_dir: Path,
    manifest: Manifest,
    validation: ValidationResult,
    host: str,
    port: int,
    mode: str,
) -> Path:
    report_dir = build_dir / "flashless"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "report.json"

    data = {
        "manifest": {
            "path": str(manifest.source_path),
            "sha256": _sha256(manifest.source_path),
            "version": manifest.version,
        },
        "server": {
            "host": host,
            "port": port,
            "mode": mode,
            "basePath": manifest.ui.base_path,
            "assetRoot": str(manifest.ui.asset_root),
        },
        "validation": {
            "missingRequiredFiles": list(validation.missing_required_files),
            "missingFixtures": list(validation.missing_fixture_files),
            "unresolvedRoutes": list(validation.unresolved_routes),
            "hasErrors": validation.has_errors,
        },
        "routes": list(manifest.ui.routes),
        "api": {
            "mode": manifest.api.mode,
            "fixturesDir": str(manifest.api.fixtures_dir),
            "mappingCount": len(manifest.api.mappings),
        },
    }

    report_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return report_path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
