from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from flashless.manifest import load_manifest
from flashless.server import PreviewServer, validate_parity


class ServerTests(unittest.TestCase):
    def test_server_serves_assets_routes_and_mock_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)

            asset_root = project / "web" / "dist"
            asset_root.mkdir(parents=True)
            (asset_root / "index.html").write_text(
                "<html>index</html>", encoding="utf-8"
            )
            (asset_root / "assets").mkdir(parents=True)
            (asset_root / "assets" / "app.js").write_text(
                "console.log('ok')", encoding="utf-8"
            )

            fixtures = project / "ui-fixtures"
            fixtures.mkdir(parents=True)
            (fixtures / "health.json").write_text('{"ok": true}', encoding="utf-8")

            manifest_path = project / "flashless.manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "version": "1",
                        "ui": {
                            "basePath": "/",
                            "assetRoot": "web/dist",
                            "entryFile": "index.html",
                            "routes": ["/", "/settings", "/wifi/*"],
                            "spaFallback": True,
                        },
                        "api": {
                            "mode": "mock",
                            "fixturesDir": "ui-fixtures",
                            "map": [
                                {
                                    "method": "GET",
                                    "path": "/api/health",
                                    "fixture": "health.json",
                                    "status": 200,
                                }
                            ],
                        },
                        "validation": {
                            "requiredFiles": ["index.html", "assets/app.js"],
                            "disallowExtraRoutes": False,
                        },
                    }
                ),
                encoding="utf-8",
            )

            manifest = load_manifest(manifest_path, project)
            parity = validate_parity(manifest)
            self.assertFalse(parity.has_errors)

            server = PreviewServer(manifest, "127.0.0.1", 0)
            host, port = server.address
            server.start()
            try:
                index_body = _read_text(f"http://{host}:{port}/")
                self.assertIn("index", index_body)

                route_body = _read_text(f"http://{host}:{port}/settings")
                self.assertIn("index", route_body)

                js_body = _read_text(f"http://{host}:{port}/assets/app.js")
                self.assertIn("console.log", js_body)

                api_body = _read_text(f"http://{host}:{port}/api/health")
                self.assertIn("ok", api_body)
            finally:
                server.stop()

    def test_server_respects_disallow_extra_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)

            asset_root = project / "web" / "dist"
            asset_root.mkdir(parents=True)
            (asset_root / "index.html").write_text(
                "<html>index</html>", encoding="utf-8"
            )

            manifest_path = project / "flashless.manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "version": "1",
                        "ui": {
                            "assetRoot": "web/dist",
                            "routes": ["/"],
                            "spaFallback": True,
                        },
                        "validation": {
                            "requiredFiles": ["index.html"],
                            "disallowExtraRoutes": True,
                        },
                    }
                ),
                encoding="utf-8",
            )

            manifest = load_manifest(manifest_path, project)
            server = PreviewServer(manifest, "127.0.0.1", 0)
            host, port = server.address
            server.start()
            try:
                try:
                    _read_text(f"http://{host}:{port}/not-allowed")
                except HTTPError as err:
                    self.assertEqual(err.code, 404)
                    err.close()
                else:
                    self.fail("Expected HTTP 404 for non-declared route")
            finally:
                server.stop()

    def test_server_serves_streamed_fixture_and_static_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)

            asset_root = project / "web" / "dist"
            asset_root.mkdir(parents=True)
            static_payload = bytes(range(256)) * 1024
            (asset_root / "big.bin").write_bytes(static_payload)
            (asset_root / "index.html").write_text(
                "<html>index</html>", encoding="utf-8"
            )

            fixtures = project / "ui-fixtures"
            fixtures.mkdir(parents=True)
            fixture_payload = bytes(range(128)) * 1024
            (fixtures / "blob.bin").write_bytes(fixture_payload)

            manifest_path = project / "flashless.manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "version": "1",
                        "ui": {
                            "assetRoot": "web/dist",
                            "routes": ["/"],
                            "spaFallback": True,
                        },
                        "api": {
                            "fixturesDir": "ui-fixtures",
                            "map": [
                                {
                                    "method": "GET",
                                    "path": "/api/blob",
                                    "fixture": "blob.bin",
                                    "status": 200,
                                    "headers": {
                                        "Content-Type": "application/octet-stream",
                                        "X-Fixture": "yes",
                                    },
                                }
                            ],
                        },
                    }
                ),
                encoding="utf-8",
            )

            manifest = load_manifest(manifest_path, project)
            server = PreviewServer(manifest, "127.0.0.1", 0)
            host, port = server.address
            server.start()
            try:
                static_body, static_headers = _read_bytes_with_headers(
                    f"http://{host}:{port}/big.bin"
                )
                self.assertEqual(static_body, static_payload)
                self.assertEqual(
                    static_headers.get("Content-Length"), str(len(static_payload))
                )

                fixture_body, fixture_headers = _read_bytes_with_headers(
                    f"http://{host}:{port}/api/blob"
                )
                self.assertEqual(fixture_body, fixture_payload)
                self.assertEqual(
                    fixture_headers.get("Content-Length"), str(len(fixture_payload))
                )
                self.assertEqual(fixture_headers.get("X-Fixture"), "yes")
            finally:
                server.stop()

    def test_server_injects_live_reload_script_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            asset_root = project / "web" / "dist"
            asset_root.mkdir(parents=True)
            (asset_root / "index.html").write_text(
                "<html><body>index</body></html>", encoding="utf-8"
            )

            manifest_path = project / "flashless.manifest.json"
            manifest_path.write_text(
                json.dumps({"version": "1", "ui": {"assetRoot": "web/dist"}}),
                encoding="utf-8",
            )

            manifest = load_manifest(manifest_path, project)
            server = PreviewServer(manifest, "127.0.0.1", 0)
            host, port = server.address
            server.start()
            try:
                body = _read_text(f"http://{host}:{port}/")
                self.assertIn("EventSource", body)
                self.assertIn("/__flashless/reload", body)
            finally:
                server.stop()

    def test_server_disables_live_reload_script_when_configured(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            asset_root = project / "web" / "dist"
            asset_root.mkdir(parents=True)
            (asset_root / "index.html").write_text(
                "<html><body>index</body></html>", encoding="utf-8"
            )

            manifest_path = project / "flashless.manifest.json"
            manifest_path.write_text(
                json.dumps({"version": "1", "ui": {"assetRoot": "web/dist"}}),
                encoding="utf-8",
            )

            manifest = load_manifest(manifest_path, project)
            server = PreviewServer(manifest, "127.0.0.1", 0, live_reload=False)
            host, port = server.address
            server.start()
            try:
                body = _read_text(f"http://{host}:{port}/")
                self.assertNotIn("EventSource", body)
                self.assertNotIn("/__flashless/reload", body)
            finally:
                server.stop()

    def test_live_reload_endpoint_reports_version_bumps(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            asset_root = project / "web" / "dist"
            asset_root.mkdir(parents=True)
            index_path = asset_root / "index.html"
            index_path.write_text("<html><body>index</body></html>", encoding="utf-8")

            manifest_path = project / "flashless.manifest.json"
            manifest_path.write_text(
                json.dumps({"version": "1", "ui": {"assetRoot": "web/dist"}}),
                encoding="utf-8",
            )

            manifest = load_manifest(manifest_path, project)
            server = PreviewServer(
                manifest,
                "127.0.0.1",
                0,
                live_reload=True,
                live_reload_interval=0.05,
            )
            host, port = server.address
            server.start()
            try:
                url = f"http://{host}:{port}/__flashless/reload"
                version = _read_sse_version(url)
                index_path.write_text(
                    "<html><body>updated</body></html>",
                    encoding="utf-8",
                )
                bumped = _wait_for_sse_version(url, version, timeout=2.0)
                self.assertGreater(bumped, version)
            finally:
                server.stop()


def _read_text(url: str) -> str:
    request = Request(url, method="GET")
    with urlopen(request, timeout=5) as response:  # noqa: S310 - local test URL only
        return response.read().decode("utf-8")


def _read_bytes_with_headers(url: str) -> tuple[bytes, dict[str, str]]:
    request = Request(url, method="GET")
    with urlopen(request, timeout=5) as response:  # noqa: S310 - local test URL only
        return response.read(), dict(response.headers.items())


def _read_sse_version(url: str) -> int:
    request = Request(url, method="GET")
    with urlopen(request, timeout=5) as response:  # noqa: S310 - local test URL only
        headers = dict(response.headers.items())
        assert "text/event-stream" in headers.get("Content-Type", "")
        while True:
            line = response.readline().decode("utf-8")
            if not line:
                raise AssertionError("Expected SSE data event")
            if line.startswith("data:"):
                return int(line.split(":", 1)[1].strip())


def _wait_for_sse_version(url: str, after: int, timeout: float) -> int:
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = _read_sse_version(url)
        if value > after:
            return value
        time.sleep(0.05)
    raise AssertionError("Live reload version did not increase")


if __name__ == "__main__":
    unittest.main()
