"""Top-level flashless orchestration."""

from __future__ import annotations

import subprocess
import webbrowser
from dataclasses import dataclass
from pathlib import Path

from .autogen import generate_auto_manifest
from .errors import FlashlessError
from .manifest import discover_manifest, load_manifest
from .report import write_report
from .server import PreviewServer, validate_parity


@dataclass(frozen=True)
class FlashlessOptions:
    manifest: str | None = None
    port: int = 8787
    host: str = "127.0.0.1"
    open_browser: bool = True
    mode: str = "mock"
    fixtures: str | None = None
    run_build: bool = True
    strict: bool = False
    auto: bool = True


def run_flashless(project_path: str | Path, build_dir: str | Path, options: FlashlessOptions) -> int:
    project_dir = Path(project_path).resolve()
    build_dir_path = Path(build_dir)
    if not build_dir_path.is_absolute():
        build_dir_path = project_dir / build_dir_path

    if options.mode.lower() != "mock":
        raise FlashlessError("Only '--mode mock' is supported in v1.")

    if options.run_build:
        _run_idf_build(project_dir, build_dir_path)

    manifest_path = _resolve_manifest_path(project_dir, build_dir_path, options)
    fixtures_override = options.fixtures
    if options.auto and options.manifest is None and fixtures_override is None and _is_auto_manifest(manifest_path):
        fixtures_override = str(manifest_path.parent / "fixtures")

    manifest = load_manifest(manifest_path, project_dir, fixtures_override=fixtures_override)

    validation = validate_parity(manifest)
    if validation.has_errors and options.strict:
        raise FlashlessError(
            "Strict validation failed: "
            f"missingRequiredFiles={list(validation.missing_required_files)} "
            f"missingFixtures={list(validation.missing_fixture_files)} "
            f"unresolvedRoutes={list(validation.unresolved_routes)}"
        )

    try:
        server = PreviewServer(manifest=manifest, host=options.host, port=options.port)
    except OSError as exc:
        raise FlashlessError(f"Failed to bind preview server on {options.host}:{options.port}: {exc}") from exc

    host, port = server.address
    report_path = write_report(
        build_dir=build_dir_path,
        manifest=manifest,
        validation=validation,
        host=host,
        port=port,
        mode=options.mode.lower(),
    )

    url = _to_url(host, port, manifest.ui.base_path)
    print(f"[flashless] Manifest: {manifest.source_path}")
    print(f"[flashless] Report:   {report_path}")
    if validation.has_errors:
        print("[flashless] Validation warnings detected. Use --strict to fail fast.")
        if validation.missing_required_files:
            print(f"[flashless]   missing required files: {', '.join(validation.missing_required_files)}")
        if validation.missing_fixture_files:
            print(f"[flashless]   missing fixtures: {', '.join(validation.missing_fixture_files)}")
        if validation.unresolved_routes:
            print(f"[flashless]   unresolved routes: {', '.join(validation.unresolved_routes)}")

    if options.open_browser:
        webbrowser.open(url)

    print(f"[flashless] Preview running at {url}")
    print("[flashless] Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[flashless] Stopped.")
    finally:
        server.stop()
    return 0


def _run_idf_build(project_dir: Path, build_dir: Path) -> None:
    command = [
        "idf.py",
        "-C",
        str(project_dir),
        "-B",
        str(build_dir),
        "build",
    ]
    print(f"[flashless] Running preflight: {' '.join(command)}")
    try:
        subprocess.run(command, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise FlashlessError("Preflight build failed. Resolve build errors or use --no-build.") from exc


def _to_url(host: str, port: int, base_path: str) -> str:
    printable_host = host
    if host in {"0.0.0.0", "::"}:
        printable_host = "127.0.0.1"
    base = base_path if base_path.startswith("/") else f"/{base_path}"
    return f"http://{printable_host}:{port}{base}"


def _resolve_manifest_path(project_dir: Path, build_dir: Path, options: FlashlessOptions) -> Path:
    if options.manifest is not None:
        return discover_manifest(project_dir, options.manifest)

    try:
        return discover_manifest(project_dir, None)
    except FlashlessError:
        if not options.auto:
            raise
        auto_dir = build_dir / "flashless" / "auto"
        result = generate_auto_manifest(project_dir, auto_dir)
        print(f"[flashless] No manifest found; generated one at {result.manifest_path}")
        print(f"[flashless] Auto-discovered assets at {result.asset_root}")
        return result.manifest_path


def _is_auto_manifest(manifest_path: Path) -> bool:
    return "flashless/auto/flashless.manifest.json" in manifest_path.as_posix()
