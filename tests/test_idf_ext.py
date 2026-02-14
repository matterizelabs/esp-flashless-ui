from __future__ import annotations

import unittest

import idf_ext


class IdfExtTests(unittest.TestCase):
    def test_resolve_bind_port_from_bind_port_kwarg(self):
        self.assertEqual(idf_ext._resolve_bind_port({"bind_port": 9001}), 9001)

    def test_resolve_bind_port_supports_legacy_port_kwarg(self):
        self.assertEqual(idf_ext._resolve_bind_port({"port": "8832"}), 8832)

    def test_resolve_bind_port_falls_back_to_default(self):
        self.assertEqual(idf_ext._resolve_bind_port({}), 8787)


if __name__ == "__main__":
    unittest.main()
