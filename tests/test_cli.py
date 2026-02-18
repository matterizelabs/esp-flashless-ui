from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from flashless import cli


class CliTests(unittest.TestCase):
    def test_run_parser_accepts_allow_absolute_paths_flag(self):
        parser = cli.build_parser()
        args = parser.parse_args(
            [
                "run",
                "--project-dir",
                ".",
                "--allow-absolute-paths",
            ]
        )
        self.assertTrue(args.allow_absolute_paths)

    def test_run_parser_accepts_no_live_reload_flag(self):
        parser = cli.build_parser()
        args = parser.parse_args(["run", "--project-dir", ".", "--no-live-reload"])
        self.assertTrue(args.no_live_reload)

    def test_main_passes_allow_absolute_paths_to_run_flashless(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch(
                "flashless.cli.run_flashless", return_value=0
            ) as patched_run:
                result = cli.main(
                    [
                        "run",
                        "--project-dir",
                        tmp,
                        "--build-dir",
                        "build",
                        "--no-build",
                        "--no-open",
                        "--allow-absolute-paths",
                    ]
                )

        self.assertEqual(result, 0)
        _, _, options = patched_run.call_args.args
        self.assertTrue(options.allow_absolute_paths)

    def test_main_enables_live_reload_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch(
                "flashless.cli.run_flashless", return_value=0
            ) as patched_run:
                result = cli.main(
                    [
                        "run",
                        "--project-dir",
                        tmp,
                        "--build-dir",
                        "build",
                        "--no-build",
                        "--no-open",
                    ]
                )

        self.assertEqual(result, 0)
        _, _, options = patched_run.call_args.args
        self.assertTrue(options.live_reload)

    def test_main_disables_live_reload_when_flag_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch(
                "flashless.cli.run_flashless", return_value=0
            ) as patched_run:
                result = cli.main(
                    [
                        "run",
                        "--project-dir",
                        tmp,
                        "--build-dir",
                        "build",
                        "--no-build",
                        "--no-open",
                        "--no-live-reload",
                    ]
                )

        self.assertEqual(result, 0)
        _, _, options = patched_run.call_args.args
        self.assertFalse(options.live_reload)


if __name__ == "__main__":
    unittest.main()
