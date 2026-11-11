import io
import json
import sys
import unittest
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.cbeta_api import CBETAAPI  # noqa: E402


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


WORK_T0235 = {"work": "T0235", "canon": "T", "vol": "T08", "title": "金剛般若波羅蜜經",
              "byline": "後秦 鳩摩羅什譯", "creators_with_id": "鳩摩羅什(A001583)",
              "time_from": 402, "time_to": 412}
SHILIAN = {"authorityID": "A000919", "name": "師鍊", "monk": "y", "zenSchool": "臨濟宗",
           "zenSect": "楊岐派", "bornDateBegin": "unknown", "diedDateBegin": "unknown",
           "dynasty": "日本", "names": "[日文] こかんしれん\n[中文] 虎關師鍊",
           "note": "見<a href=\"https://ja.wikipedia.org/\">wiki</a>"}


class CBETATest(unittest.TestCase):
    def setUp(self):
        self._urlopen = urllib.request.urlopen
        self.urls = []

        def fake(req, timeout=None, context=None):
            url = req.full_url
            self.urls.append(url)
            p = urllib.parse.urlparse(url)
            qs = {k: v[0] for k, v in urllib.parse.parse_qs(p.query).items()}
            if p.netloc == "authority.dila.edu.tw":
                ident = qs.get("id", "")
                if ident in ("師鍊", "A000919"):
                    body = json.dumps({"data1": SHILIAN}, ensure_ascii=False)
                elif ident == "空海":
                    body = json.dumps({"data1": {"authorityID": "A000759", "name": "空海"},
                                       "data2": {"authorityID": "A003966", "name": "廣漩"}},
                                      ensure_ascii=False)
                elif ident == "嵩山x":
                    body = 'abc({"data1": {"authorityID": "PL1", "name": "嵩山"}})'
                elif ident == "師錬":
                    body = "null"
                else:
                    body = '{"data1": ""}'
            elif p.netloc == "query.wikidata.org":
                body = json.dumps({"results": {"bindings": [
                    {"item": {"value": "http://www.wikidata.org/entity/Q222227"},
                     "itemLabel": {"value": "空海"}}]}})
            else:
                path = p.path.split("/stable/", 1)[1]
                if path == "works":
                    body = json.dumps({"num_found": 1 if qs.get("work") == "T0235" else 0,
                                       "results": [WORK_T0235] if qs.get("work") == "T0235" else []},
                                      ensure_ascii=False)
                elif path == "search/kwic" and "work" not in qs:
                    body = json.dumps({"success": False, "error": "缺少必要參數： work 佛典編號"},
                                      ensure_ascii=False)
                elif path == "search/variants":
                    body = json.dumps({"results": [{"q": "師鍊", "hits": 75}]}, ensure_ascii=False)
                elif path == "juans/goto":
                    body = json.dumps({"num_found": 1, "results": [
                        {"vol": "T08", "lb": "0748c17", "work": "T0235", "juan": 1,
                         "linehead": "T08n0235_p0748c17"}]})
                elif path == "juans":
                    body = json.dumps({"results": [
                        '<html><body><span class="lb" id="x">T08n0251_p0848a01</span>'
                        "<p>觀自在菩薩，</p><p>行深般若</p></body></html>"]}, ensure_ascii=False)
                elif path == "lines":
                    body = json.dumps({"results": [{"linehead": qs.get("linehead"), "html": "x"}]})
                else:
                    body = json.dumps({"num_found": 0, "results": []})
            return FakeResponse(body.encode("utf-8"))

        urllib.request.urlopen = fake
        self.api = CBETAAPI(min_request_interval=0, max_retries=0)

    def tearDown(self):
        urllib.request.urlopen = self._urlopen

    def test_base_url_is_cbdata(self):
        self.api.work("T0235")
        self.assertTrue(self.urls[0].startswith("https://cbdata.dila.edu.tw/stable/works?work=T0235"))

    def test_work_found_and_missing(self):
        self.assertEqual(self.api.work("T0235")["title"], "金剛般若波羅蜜經")
        self.assertIsNone(self.api.work("T9999"))

    def test_person_by_name_and_id(self):
        self.assertEqual(self.api.person("師鍊")[0]["authorityID"], "A000919")
        self.assertEqual([r["authorityID"] for r in self.api.person("空海")], ["A000759", "A003966"])

    def test_person_no_match_shapes(self):
        self.assertEqual(self.api.person("師錬"), [])      # server answers "null"
        self.assertEqual(self.api.person("林羅山"), [])    # server answers {"data1": ""}

    def test_jsonp_wrapper_is_stripped(self):
        self.assertEqual(self.api.place("嵩山x")[0]["name"], "嵩山")

    def test_chinese_sent_as_utf8(self):
        self.api.person("空海")
        self.assertIn("id=%E7%A9%BA%E6%B5%B7", self.urls[0])

    def test_query_length_limit(self):
        with self.assertRaises(ValueError):
            self.api.search("字" * 41)
        with self.assertRaises(ValueError):
            self.api.search("  ")

    def test_api_error_raises(self):
        with self.assertRaises(ValueError):
            self.api._cbeta("search/kwic", {"q": "空海"})

    def test_variants(self):
        self.assertEqual(self.api.search_variants("師錬")[0]["q"], "師鍊")

    def test_goto_and_cite(self):
        loc = self.api.goto("CBETA, T08, no. 235, p. 748c17")
        self.assertEqual(loc["linehead"], "T08n0235_p0748c17")
        self.assertEqual(CBETAAPI.cite(WORK_T0235, loc["lb"]), "CBETA, T08, no. 235, p. 748c17")

    def test_juan_text_strips_line_ids(self):
        text = self.api.juan_text("T0251", 1)
        self.assertNotIn("T08n0251", text)
        self.assertIn("觀自在菩薩", text)

    def test_lines_requires_args(self):
        with self.assertRaises(ValueError):
            self.api.lines()
        self.assertEqual(self.api.lines("T08n0235_p0748c17")[0]["linehead"], "T08n0235_p0748c17")

    def test_wikidata_for_person(self):
        self.assertEqual(self.api.wikidata_for_person("A000759"), [{"qid": "Q222227", "label": "空海"}])
        with self.assertRaises(ValueError):
            self.api.wikidata_for_person("空海")

    def test_ssl_context_keeps_verification(self):
        import ssl
        ctx = self.api._ssl
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(ctx.check_hostname)
        self.assertFalse(ctx.verify_flags & getattr(ssl, "VERIFY_X509_STRICT", 0))

    def test_summarize_person_removes_html(self):
        s = CBETAAPI.summarize_person(SHILIAN)
        self.assertIn("師鍊 (A000919)", s)
        self.assertIn("虎關師鍊", s)
        self.assertNotIn("<a", s)


if __name__ == "__main__":
    unittest.main()
