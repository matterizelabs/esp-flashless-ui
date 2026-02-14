from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from flashless.errors import FlashlessError
from flashless.manifest import discover_manifest, load_manifest, route_matches


class ManifestTests(unittest.TestCase):
    def test_discover_manifest_prefers_project_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "flashless.manifest.json").write_text('{"version":"1","ui":{"assetRoot":"web"}}', encoding="utf-8")
            (project / "web").mkdir()
            found = discover_manifest(project, None)
            self.assertEqual(found, project / "flashless.manifest.json")

    def test_load_manifest_with_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            asset_root = project / "web" / "dist"
            asset_root.mkdir(parents=True)
            (asset_root / "index.html").write_text("<html></html>", encoding="utf-8")

            manifest_path = project / "flashless.manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "version": "1",
                        "ui": {
                            "assetRoot": "web/dist",
                            "routes": ["/", "/settings"],
                        },
                    }
                ),
                encoding="utf-8",
            )

            manifest = load_manifest(manifest_path, project)
            self.assertEqual(manifest.ui.base_path, "/")
            self.assertEqual(manifest.ui.entry_file, "index.html")
            self.assertEqual(manifest.ui.routes, ("/", "/settings"))

    def test_load_manifest_rejects_invalid_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "web").mkdir()
            manifest_path = project / "flashless.manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "version": "2",
                        "ui": {"assetRoot": "web"},
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(FlashlessError):
                load_manifest(manifest_path, project)

    def test_route_match_wildcard(self):
        self.assertTrue(route_matches("/wifi/*", "/wifi/scan"))
        self.assertFalse(route_matches("/wifi/*", "/network/scan"))


if __name__ == "__main__":
    unittest.main()
