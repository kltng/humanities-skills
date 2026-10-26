import io
import json
import sys
import unittest
import urllib.parse
import urllib.request
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.jbdb_api import JBDBAPI


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


PERSON = {"cPersonid": 2563, "cName": "本居宣長", "cNameRomaji": "Motoori Norinaga",
          "cByNengoCode": 240, "cByNengoYear": 15, "cDyNengoCode": 249, "cDyNengoYear": 13,
          "cFemale": False, "cDeathAge": 72, "cOccupationCodes": [4]}

FIXTURES = {
    "NengoCodes/240": {"cNengoId": 240, "cNengoName": "享保", "cStartYearMinusOne": 1715},
    "NengoCodes/249": {"cNengoId": 249, "cNengoName": "寛政", "cStartYearMinusOne": 1788},
    "OccupationCodes/4": {"cOccupationCode": 4, "cOccupationDescTrans": "Scholar"},
    "AltnameData": [],
    "KinData": [{"cPersonid": 2563, "cKinCode": 1, "cKinId": 2562}],
    "NonkinData": [{"cPersonid": 2563, "cNonkinCode": 12, "cNonkinId": 1096},
                   {"cPersonid": 2563, "cNonkinCode": 12, "cNonkinId": 2763}],
    "KinshipCodes/1": {"cKincode": 1, "cKinrelTrans": "father of"},
    "NonkinshipCodes/12": {"cNonkincode": 12, "cNonkinrelTrans": "student/disciple of"},
}


class JBDBTest(unittest.TestCase):
    def setUp(self):
        self._urlopen = urllib.request.urlopen
        self.urls = []

        def fake(req, timeout=None):
            url = req.full_url
            self.urls.append(url)
            parsed = urllib.parse.urlparse(url)
            path = parsed.path.split("/api/", 1)[1]
            filt = json.loads(urllib.parse.parse_qs(parsed.query).get("filter", ["{}"])[0])
            if path == "BiogMains":
                where = filt.get("where", {})
                pid = where.get("cPersonid")
                if isinstance(pid, dict):
                    rows = [{"cPersonid": 2562, "cName": "本居春庭", "cNameRomaji": "Motoori Haruniwa"},
                            {"cPersonid": 1096, "cName": "賀茂真淵", "cNameRomaji": "Kamo no Mabuchi"}]
                    body = [r for r in rows if r["cPersonid"] in pid["inq"]]
                else:
                    body = [PERSON] if pid == 2563 else []
            else:
                body = FIXTURES[path]
            return FakeResponse(json.dumps(body, ensure_ascii=False).encode())
        urllib.request.urlopen = fake

    def tearDown(self):
        urllib.request.urlopen = self._urlopen

    def test_base_url_is_app_host(self):
        api = JBDBAPI(min_request_interval=0)
        api.query_by_id(2563)
        self.assertTrue(self.urls[0].startswith("https://app.jbdb.jp/api/BiogMains?filter="))

    def test_query_by_id_uses_filter_and_handles_missing(self):
        api = JBDBAPI(min_request_interval=0)
        self.assertEqual(api.query_by_id(2563)["cNameRomaji"], "Motoori Norinaga")
        self.assertIsNone(api.query_by_id(1))

    def test_get_names_batches_ids(self):
        api = JBDBAPI(min_request_interval=0)
        names = api.get_names([2562, 1096, 2562, 0, None])
        self.assertEqual(len(self.urls), 1)
        self.assertEqual(set(names), {2562, 1096})

    def test_summarize_resolves_names_in_one_call(self):
        api = JBDBAPI(min_request_interval=0)
        text = api.summarize(PERSON)
        self.assertIn("1730–1801", text)
        self.assertIn("father of → 本居春庭 (Motoori Haruniwa) [ID 2562]", text)
        self.assertIn("student/disciple of → 賀茂真淵 (Kamo no Mabuchi) [ID 1096]", text)
        # 2763 is missing from the name lookup: fall back to the bare ID.
        self.assertIn("student/disciple of → person ID 2763", text)
        self.assertEqual(sum("cPersonid%22%3A%20%7B%22inq" in u for u in self.urls), 1)
        # The non-kin code 12 is looked up once (cache).
        self.assertEqual(sum(u.endswith("NonkinshipCodes/12") for u in self.urls), 1)

    def test_summarize_without_names(self):
        api = JBDBAPI(min_request_interval=0)
        text = api.summarize(PERSON, resolve_names=False)
        self.assertIn("father of → person ID 2562", text)
        self.assertFalse(any("inq" in urllib.parse.unquote(u) for u in self.urls))


if __name__ == "__main__":
    unittest.main()
