"""Preview HTTP server for flashless."""

from __future__ import annotations

import json
import mimetypes
import os
import posixpath
import threading
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .errors import FlashlessError
from .manifest import Manifest, route_matches

_STREAM_CHUNK_SIZE = 64 * 1024
_LIVE_RELOAD_ENDPOINT = "/__flashless/reload"
_LIVE_RELOAD_KEEPALIVE_SECONDS = 15.0


@dataclass(frozen=True)
class ValidationResult:
    missing_required_files: tuple[str, ...]
    missing_fixture_files: tuple[str, ...]
    unresolved_routes: tuple[str, ...]

    @property
    def has_errors(self) -> bool:
        return bool(
            self.missing_required_files
            or self.missing_fixture_files
            or self.unresolved_routes
        )


def validate_parity(manifest: Manifest) -> ValidationResult:
    missing_required = []
    for rel in manifest.validation.required_files:
        if not _safe_join(manifest.ui.asset_root, rel).exists():
            missing_required.append(rel)

    missing_fixture = []
    for mapping in manifest.api.mappings:
        fixture_path = _safe_join(manifest.api.fixtures_dir, mapping.fixture)
        if not fixture_path.exists():
            missing_fixture.append(mapping.fixture)

    unresolved_routes = []
    for route in manifest.ui.routes:
        if route.endswith("/*"):
            continue
        candidate = _route_to_asset_candidate(route)
        if candidate and _safe_join(manifest.ui.asset_root, candidate).exists():
            continue
        if (
            manifest.ui.spa_fallback
            and _safe_join(manifest.ui.asset_root, manifest.ui.entry_file).exists()
        ):
            continue
        unresolved_routes.append(route)

    return ValidationResult(
        missing_required_files=tuple(sorted(set(missing_required))),
        missing_fixture_files=tuple(sorted(set(missing_fixture))),
        unresolved_routes=tuple(sorted(set(unresolved_routes))),
    )


class PreviewServer:
    def __init__(
        self,
        manifest: Manifest,
        host: str,
        port: int,
        request_log_level: str = "errors",
        live_reload: bool = True,
        live_reload_interval: float = 1.0,
    ):
        self._manifest = manifest
        self._host = host
        self._port = port
        self._request_log_level = request_log_level
        self._live_reload = live_reload
        self._live_reload_interval = live_reload_interval
        self._reload_state = _ReloadState()
        self._watcher_thread: threading.Thread | None = None
        self._watcher_stop = threading.Event()
        self._httpd = ThreadingHTTPServer((host, port), self._build_handler())
        self._thread: threading.Thread | None = None

    @property
    def address(self) -> tuple[str, int]:
        return self._httpd.server_address

    def serve_forever(self) -> None:
        try:
            self._httpd.serve_forever(poll_interval=0.2)
        finally:
            self._httpd.server_close()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._start_watcher()
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_watcher()
        if self._thread is None:
            self._httpd.server_close()
            return

        self._httpd.shutdown()
        self._thread.join(timeout=2)
        self._thread = None

    def _start_watcher(self) -> None:
        if not self._live_reload or self._watcher_thread is not None:
            return
        self._watcher_stop.clear()
        self._watcher_thread = threading.Thread(
            target=self._watch_for_changes,
            daemon=True,
        )
        self._watcher_thread.start()

    def _stop_watcher(self) -> None:
        if self._watcher_thread is None:
            return
        self._watcher_stop.set()
        self._watcher_thread.join(timeout=2)
        self._watcher_thread = None

    def _watch_for_changes(self) -> None:
        watched_roots = [
            self._manifest.ui.asset_root,
            self._manifest.api.fixtures_dir,
        ]
        snapshot = _snapshot_files(watched_roots)
        while not self._watcher_stop.wait(self._live_reload_interval):
            next_snapshot = _snapshot_files(watched_roots)
            if next_snapshot != snapshot:
                snapshot = next_snapshot
                self._reload_state.bump()

    def _build_handler(self):
        manifest = self._manifest
        request_log_level = self._request_log_level
        live_reload = self._live_reload
        reload_state = self._reload_state
        api_map = {(m.method.upper(), m.path): m for m in manifest.api.mappings}
        base_path = manifest.ui.base_path
        reload_path = _join_base_path(base_path, _LIVE_RELOAD_ENDPOINT)

        class Handler(BaseHTTPRequestHandler):
            server_version = "flashless/1.0"

            def do_GET(self):
                self._dispatch("GET")

            def do_POST(self):
                self._dispatch("POST")

            def do_PUT(self):
                self._dispatch("PUT")

            def do_DELETE(self):
                self._dispatch("DELETE")

            def do_PATCH(self):
                self._dispatch("PATCH")

            def log_message(self, format: str, *args: Any) -> None:
                status_code: int | None = None
                if len(args) >= 2:
                    try:
                        status_code = int(args[1])
                    except (TypeError, ValueError):
                        status_code = None

                if not _should_log_request(request_log_level, status_code):
                    return
                print(f"[flashless] {self.address_string()} - {format % args}")

            def _dispatch(self, method: str) -> None:
                parsed = urlparse(self.path)
                request_path = _normalize_http_path(unquote(parsed.path))

                if (
                    live_reload
                    and method.upper() == "GET"
                    and request_path == reload_path
                ):
                    return self._serve_reload_stream()

                mapped = api_map.get((method.upper(), request_path))
                if mapped is not None:
                    return self._serve_fixture(
                        mapped.fixture, mapped.status, mapped.headers
                    )

                if (
                    base_path != "/"
                    and not request_path.startswith(base_path + "/")
                    and request_path != base_path
                ):
                    return self._respond_not_found(request_path)

                rel_route = _relative_to_base(request_path, base_path)

                static_candidate = self._resolve_static_candidate(rel_route)
                if (
                    static_candidate is not None
                    and static_candidate.exists()
                    and static_candidate.is_file()
                ):
                    return self._serve_file(static_candidate)

                is_declared = any(
                    route_matches(pattern, rel_route) for pattern in manifest.ui.routes
                )
                if is_declared or (
                    manifest.ui.spa_fallback
                    and not manifest.validation.disallow_extra_routes
                ):
                    entry = _safe_join(manifest.ui.asset_root, manifest.ui.entry_file)
                    if entry.exists() and entry.is_file():
                        return self._serve_file(entry)

                return self._respond_not_found(request_path)

            def _resolve_static_candidate(self, rel_route: str) -> Path | None:
                if rel_route in {"", "/"}:
                    return _safe_join(manifest.ui.asset_root, manifest.ui.entry_file)

                normalized = rel_route.lstrip("/")
                candidate = _safe_join(manifest.ui.asset_root, normalized)
                if candidate.exists() and candidate.is_file():
                    return candidate

                if not os.path.splitext(normalized)[1]:
                    html_candidate = _safe_join(
                        manifest.ui.asset_root, normalized + ".html"
                    )
                    if html_candidate.exists() and html_candidate.is_file():
                        return html_candidate
                return None

            def _serve_fixture(
                self, fixture_rel: str, status: int, headers: dict[str, str]
            ) -> None:
                fixture_path = _safe_join(manifest.api.fixtures_dir, fixture_rel)
                if not fixture_path.exists() or not fixture_path.is_file():
                    return self._respond_json(
                        {"error": f"Missing fixture: {fixture_rel}"},
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                    )

                size = fixture_path.stat().st_size
                self.send_response(status)
                content_type = headers.get("Content-Type") or _guess_content_type(
                    fixture_path
                )
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(size))
                for name, value in headers.items():
                    if name.lower() in {"content-length", "content-type"}:
                        continue
                    self.send_header(name, value)
                self.end_headers()
                self._stream_file(fixture_path)

            def _serve_file(self, file_path: Path) -> None:
                content_type = _guess_content_type(file_path)
                if live_reload and content_type.startswith("text/html"):
                    return self._serve_html_with_reload(file_path)

                size = file_path.stat().st_size
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(size))
                self.send_header(
                    "Cache-Control",
                    f"public, max-age={manifest.ui.cache_policy['maxAgeSeconds']}",
                )
                if manifest.ui.cache_policy.get("etag", True):
                    stat = file_path.stat()
                    self.send_header(
                        "ETag", f'W/"{stat.st_mtime_ns:x}-{stat.st_size:x}"'
                    )
                self.end_headers()
                self._stream_file(file_path)

            def _serve_html_with_reload(self, file_path: Path) -> None:
                payload = file_path.read_text(encoding="utf-8", errors="ignore")
                payload += _live_reload_script(reload_path)
                body = payload.encode("utf-8")

                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header(
                    "Cache-Control",
                    f"public, max-age={manifest.ui.cache_policy['maxAgeSeconds']}",
                )
                self.end_headers()
                self.wfile.write(body)

            def _serve_reload_stream(self) -> None:
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()

                version = reload_state.get()
                try:
                    self.wfile.write(f"data: {version}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    while True:
                        changed = reload_state.wait_for_change(
                            version,
                            timeout=_LIVE_RELOAD_KEEPALIVE_SECONDS,
                        )
                        if changed is None:
                            self.wfile.write(b": keepalive\n\n")
                            self.wfile.flush()
                            continue
                        version = changed
                        self.wfile.write(f"data: {version}\n\n".encode("utf-8"))
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    return

            def _stream_file(self, file_path: Path) -> None:
                with file_path.open("rb") as handle:
                    while True:
                        chunk = handle.read(_STREAM_CHUNK_SIZE)
                        if not chunk:
                            break
                        self.wfile.write(chunk)

            def _respond_not_found(self, path: str) -> None:
                self._respond_json(
                    {"error": "Not found", "path": path}, HTTPStatus.NOT_FOUND
                )

            def _respond_json(
                self, payload: dict[str, Any], status: HTTPStatus
            ) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        return Handler


def _safe_join(root: Path, relative: str) -> Path:
    rel = relative.strip().replace("\\", "/")
    rel = posixpath.normpath(rel).lstrip("/")
    candidate = (root / rel).resolve()
    root_resolved = root.resolve()
    if root_resolved == candidate or root_resolved in candidate.parents:
        return candidate
    raise FlashlessError(f"Path escapes root directory: {relative}")


def _normalize_http_path(path: str) -> str:
    cleaned = posixpath.normpath(path)
    if not cleaned.startswith("/"):
        cleaned = "/" + cleaned
    return cleaned


def _join_base_path(base_path: str, route_path: str) -> str:
    base = base_path.rstrip("/")
    route = route_path if route_path.startswith("/") else f"/{route_path}"
    if not base:
        return route
    return f"{base}{route}"


def _relative_to_base(request_path: str, base_path: str) -> str:
    if base_path == "/":
        return request_path
    if request_path == base_path:
        return "/"
    return "/" + request_path[len(base_path) + 1 :].lstrip("/")


def _route_to_asset_candidate(route: str) -> str | None:
    if route in {"", "/"}:
        return None
    value = route.lstrip("/")
    if not value:
        return None
    if "." in value.rsplit("/", 1)[-1]:
        return value
    return None


def _guess_content_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def _should_log_request(level: str, status_code: int | None) -> bool:
    if level == "none":
        return False
    if level == "errors":
        if status_code is None:
            return True
        return status_code >= 400
    return True


class _ReloadState:
    def __init__(self) -> None:
        self._version = 0
        self._condition = threading.Condition()

    def bump(self) -> None:
        with self._condition:
            self._version += 1
            self._condition.notify_all()

    def get(self) -> int:
        with self._condition:
            return self._version

    def wait_for_change(self, version: int, timeout: float) -> int | None:
        with self._condition:
            if self._version != version:
                return self._version
            self._condition.wait(timeout=timeout)
            if self._version == version:
                return None
            return self._version


def _snapshot_files(roots: list[Path]) -> dict[Path, tuple[int, int]]:
    snapshot: dict[Path, tuple[int, int]] = {}
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        for dirpath, _, filenames in os.walk(root, followlinks=False):
            for filename in filenames:
                file_path = Path(dirpath) / filename
                try:
                    stat = file_path.stat()
                except OSError:
                    continue
                snapshot[file_path] = (stat.st_mtime_ns, stat.st_size)
    return snapshot


def _live_reload_script(reload_path: str) -> str:
    return (
        "\n<script>(function(){"
        f"var source=new EventSource('{reload_path}');"
        "var version=null;"
        "source.onmessage=function(event){"
        "var next=Number(event.data||'0');"
        "if(version===null){version=next;return;}"
        "if(next>version){window.location.reload();}"
        "version=next;"
        "};"
        "})();</script>"
    )
