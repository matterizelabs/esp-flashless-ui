from __future__ import annotations

import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from flashless.server import _should_log_request


class LoggingTests(unittest.TestCase):
    def test_request_log_none_suppresses_all(self):
        self.assertFalse(_should_log_request("none", 200))
        self.assertFalse(_should_log_request("none", 500))
        self.assertFalse(_should_log_request("none", None))

    def test_request_log_errors_logs_4xx_5xx_only(self):
        self.assertFalse(_should_log_request("errors", 200))
        self.assertFalse(_should_log_request("errors", 302))
        self.assertTrue(_should_log_request("errors", 404))
        self.assertTrue(_should_log_request("errors", 500))
        self.assertTrue(_should_log_request("errors", None))

    def test_request_log_all_logs_everything(self):
        self.assertTrue(_should_log_request("all", 200))
        self.assertTrue(_should_log_request("all", 404))
        self.assertTrue(_should_log_request("all", None))


if __name__ == "__main__":
    unittest.main()
