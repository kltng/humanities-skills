import io
import json
import os
import sys
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.zotero_api import ZoteroLocal


class FakeResponse(io.BytesIO):
    def __init__(self, body: bytes, content_type: str = "text/plain"):
        super().__init__(body)
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeUrlopenMixin:
    def setUp(self):
        self._urlopen = urllib.request.urlopen
        self.calls = []
        self.reply = lambda req: FakeResponse(b"@book{a,\n}\n")

        def fake(req, timeout=None):
            self.calls.append(req)
            return self.reply(req)
        urllib.request.urlopen = fake
        self._env = os.environ.pop("ZOTERO_DEBUG_BRIDGE_TOKEN", None)

    def tearDown(self):
        urllib.request.urlopen = self._urlopen
        if self._env is not None:
            os.environ["ZOTERO_DEBUG_BRIDGE_TOKEN"] = self._env

    def params(self, i=-1):
        return urllib.parse.parse_qs(urllib.parse.urlparse(self.calls[i].full_url).query)


class ExportTest(FakeUrlopenMixin, unittest.TestCase):
    """Issue #23: export without keys is limited by default."""

    def test_default_limit(self):
        ZoteroLocal(min_interval=0).export_items()
        self.assertEqual(self.params()["limit"], ["100"])
        self.assertNotIn("start", self.params())

    def test_limit_and_start(self):
        ZoteroLocal(min_interval=0).export_items(format="ris", limit=5, start=10, tag="x")
        p = self.params()
        self.assertEqual((p["format"], p["limit"], p["start"], p["tag"]), (["ris"], ["5"], ["10"], ["x"]))

    def test_limit_none_exports_all(self):
        ZoteroLocal(min_interval=0).export_items(limit=None)
        self.assertNotIn("limit", self.params())

    def test_keys_ignore_limit(self):
        out = ZoteroLocal(min_interval=0).export_items(keys=["AAAAAAAA", "BBBBBBBB"])
        self.assertEqual(len(self.calls), 2)
        self.assertNotIn("limit", self.params())
        self.assertEqual(out.count("@book"), 2)


class DebugBridgeTest(FakeUrlopenMixin, unittest.TestCase):
    """Issue #23: the Debug Bridge is a separate add-on that needs a token."""

    def http_error(self, code, body):
        def reply(req):
            raise urllib.error.HTTPError(req.full_url, code, "err", {}, io.BytesIO(body))
        self.reply = reply

    def test_sends_text_plain_and_token(self):
        self.reply = lambda req: FakeResponse(b'"ok"', "application/json")
        z = ZoteroLocal(min_interval=0, debug_bridge_token="secret")
        self.assertTrue(z.check_debug_bridge())
        req = self.calls[0]
        self.assertTrue(req.full_url.endswith("/debug-bridge/execute"))
        self.assertEqual(req.get_header("Content-type"), "text/plain")
        self.assertEqual(req.get_header("Authorization"), "Bearer secret")

    def test_token_from_env(self):
        os.environ["ZOTERO_DEBUG_BRIDGE_TOKEN"] = "envtok"
        try:
            self.reply = lambda req: FakeResponse(b'"ok"', "application/json")
            ZoteroLocal(min_interval=0).check_bbt()  # old name still works
            self.assertEqual(self.calls[0].get_header("Authorization"), "Bearer envtok")
        finally:
            del os.environ["ZOTERO_DEBUG_BRIDGE_TOKEN"]

    def test_not_installed(self):
        self.http_error(404, b"")
        with self.assertRaisesRegex(RuntimeError, "Debug Bridge add-on not installed"):
            ZoteroLocal(min_interval=0)._debug_bridge("return 1;")
        self.assertFalse(ZoteroLocal(min_interval=0).check_debug_bridge())

    def test_missing_token(self):
        self.http_error(401, b"bearer token required")
        with self.assertRaisesRegex(RuntimeError, "ZOTERO_DEBUG_BRIDGE_TOKEN"):
            ZoteroLocal(min_interval=0)._debug_bridge("return 1;")

    def test_token_not_configured_in_zotero(self):
        self.http_error(500, b"token not configured")
        with self.assertRaisesRegex(RuntimeError, "extensions.zotero.debug-bridge.token"):
            ZoteroLocal(min_interval=0)._debug_bridge("return 1;")

    def test_create_collection_decodes_double_json(self):
        # The add-on JSON-encodes the script's return value, which is itself a JSON string.
        body = json.dumps(json.dumps({"key": "ABCD1234", "name": "明代"})).encode()
        self.reply = lambda req: FakeResponse(body, "application/json")
        col = ZoteroLocal(min_interval=0, debug_bridge_token="t").create_collection("明代")
        self.assertEqual(col, {"key": "ABCD1234", "name": "明代"})
        self.assertIn(json.dumps("明代"), self.calls[0].data.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
