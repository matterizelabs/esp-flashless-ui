from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

import idf_ext


class IdfExtTests(unittest.TestCase):
    def test_resolve_bind_port_from_bind_port_kwarg(self):
        self.assertEqual(idf_ext._resolve_bind_port({"bind_port": 9001}), 9001)

    def test_resolve_bind_port_supports_legacy_port_kwarg(self):
        self.assertEqual(idf_ext._resolve_bind_port({"port": "8832"}), 8832)

    def test_resolve_bind_port_falls_back_to_default(self):
        self.assertEqual(idf_ext._resolve_bind_port({}), 8787)

    def test_action_includes_allow_absolute_paths_option(self):
        actions = idf_ext.action_extensions({}, "/tmp")
        option_names = [
            name
            for option in actions["actions"]["flashless"]["options"]
            for name in option["names"]
        ]
        self.assertIn("--allow-absolute-paths", option_names)

    def test_callback_passes_allow_absolute_paths_to_options(self):
        with mock.patch("idf_ext.run_flashless", return_value=0) as patched_run:
            actions = idf_ext.action_extensions({}, "/tmp/project")
            callback = actions["actions"]["flashless"]["callback"]
            args = SimpleNamespace(build_dir="build")
            result = callback(None, None, args, allow_absolute_paths=True)

        self.assertEqual(result, 0)
        _, _, options = patched_run.call_args.args
        self.assertTrue(options.allow_absolute_paths)


if __name__ == "__main__":
    unittest.main()
