from __future__ import annotations

import json
import tempfile
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
            (asset_root / "index.html").write_text("<html>index</html>", encoding="utf-8")
            (asset_root / "assets").mkdir(parents=True)
            (asset_root / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")

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
            (asset_root / "index.html").write_text("<html>index</html>", encoding="utf-8")

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


def _read_text(url: str) -> str:
    request = Request(url, method="GET")
    with urlopen(request, timeout=5) as response:  # noqa: S310 - local test URL only
        return response.read().decode("utf-8")


if __name__ == "__main__":
    unittest.main()
