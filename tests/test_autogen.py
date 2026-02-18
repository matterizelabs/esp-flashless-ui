from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from flashless.autogen import generate_auto_manifest
from flashless.errors import FlashlessError
from flashless.manifest import load_manifest
from flashless.server import validate_parity


class AutoGenTests(unittest.TestCase):
    def test_generate_auto_manifest_from_cmake_and_http_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)

            comp = project / "components" / "web"
            assets = comp / "assets"
            assets.mkdir(parents=True)
            (assets / "index.html").write_text("<html></html>", encoding="utf-8")
            (assets / "app.js").write_text("console.log('ok')", encoding="utf-8")
            (assets / "styles.css").write_text("body{}", encoding="utf-8")

            (comp / "CMakeLists.txt").write_text(
                'idf_component_register(SRCS "web.c" EMBED_TXTFILES "assets/index.html" "assets/app.js" "assets/styles.css")',
                encoding="utf-8",
            )

            (comp / "web.c").write_text(
                """
                #include \"esp_http_server.h\"
                httpd_uri_t status_uri = {
                    .uri = \"/api/status\",
                    .method = HTTP_GET,
                    .handler = 0,
                };
                httpd_uri_t root_uri = {
                    .uri = \"/\",
                    .method = HTTP_GET,
                    .handler = 0,
                };
                httpd_uri_t ws_uri = {
                    .uri = \"/ws\",
                    .method = HTTP_GET,
                    .is_websocket = true,
                    .handler = 0,
                };
                """,
                encoding="utf-8",
            )

            auto_dir = project / "build" / "flashless" / "auto"
            result = generate_auto_manifest(project, auto_dir)

            self.assertTrue(result.manifest_path.exists())
            self.assertTrue((result.fixtures_dir / "get_api_status.json").exists())

            manifest = load_manifest(result.manifest_path, project)
            parity = validate_parity(manifest)
            self.assertFalse(parity.has_errors)

            manifest_json = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest_json["ui"]["assetRoot"], "components/web/assets")
            self.assertEqual(
                manifest_json["api"]["fixturesDir"], "build/flashless/auto/fixtures"
            )
            self.assertEqual(manifest_json["ui"]["routes"], ["/"])
            self.assertEqual(manifest_json["api"]["map"][0]["path"], "/api/status")

    def test_generate_auto_manifest_ignores_heavy_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)

            ignored_node = project / "node_modules" / "pkg"
            ignored_node.mkdir(parents=True)
            (ignored_node / "index.html").write_text(
                "<html>ignored</html>", encoding="utf-8"
            )

            ignored_venv = project / ".venv" / "web"
            ignored_venv.mkdir(parents=True)
            (ignored_venv / "index.html").write_text(
                "<html>ignored</html>", encoding="utf-8"
            )

            assets = project / "main" / "web"
            assets.mkdir(parents=True)
            (assets / "index.html").write_text("<html>ok</html>", encoding="utf-8")
            (assets / "app.js").write_text("console.log('ok')", encoding="utf-8")

            auto_dir = project / "build" / "flashless" / "auto"
            result = generate_auto_manifest(project, auto_dir)

            manifest_json = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest_json["ui"]["assetRoot"], "main/web")

    def test_generate_auto_manifest_stops_after_scan_file_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            assets = project / "web"
            assets.mkdir(parents=True)
            (assets / "index.html").write_text("<html>ok</html>", encoding="utf-8")

            sources = project / "main"
            sources.mkdir(parents=True)
            for idx in range(5):
                (sources / f"file_{idx}.c").write_text(
                    '#include "esp_http_server.h"\n', encoding="utf-8"
                )

            auto_dir = project / "build" / "flashless" / "auto"
            with mock.patch("flashless.autogen._MAX_SCAN_FILES", 2):
                with self.assertRaises(FlashlessError) as ctx:
                    generate_auto_manifest(project, auto_dir)

            self.assertIn("scanned too many files", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
