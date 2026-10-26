import contextlib
import io
import json
import sys
import unittest
import urllib.request
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import timdex_api
from scripts.timdex_api import TimdexAPI, TimdexError, summarize


SAMPLE_RECORD = {
    "timdexRecordId": "alma:9936111333206761",
    "title": "明史研究",
    "source": "MIT Alma",
    "sourceLink": "https://mit.primo.exlibrisgroup.com/discovery/fulldisplay?vid=01MIT_INST:MIT&docid=alma9936111333206761",
    "contentType": ["Language material"],
    "languages": ["Chinese"],
    "alternateTitles": [{"kind": "Varying form", "value": "Ming shi yan jiu"}],
    "contributors": [{"kind": "author", "value": "Zhongguo Ming shi xue hui"}],
    "dates": [{"kind": "Publication date", "value": "1991"}],
    "identifiers": [
        {"kind": "OCLC Number", "value": "(OCoLC)123"},
        {"kind": "ISSN", "value": "1000-0000"},
    ],
    "subjects": [{"kind": "Topical Term", "value": ["China -- History -- Ming dynasty"]}],
    "publishers": [{"name": "中國明史學會", "date": None, "location": "北京市"}],
    "holdings": [{"location": None, "collection": "China Monographic Serials", "callnumber": None, "format": "electronic resource"}],
    "links": [{"kind": "Digital object URL", "url": "https://example.org/x", "text": "China Monographic Serials"}],
    "callNumbers": None,
    "summary": None,
}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class SummarizeTest(unittest.TestCase):
    def test_summary_fields(self):
        rec = summarize(SAMPLE_RECORD)
        self.assertEqual(rec["id"], "alma:9936111333206761")
        self.assertEqual(rec["title"], "明史研究")
        self.assertEqual(rec["alternate_titles"], ["Ming shi yan jiu"])
        self.assertEqual(rec["contributors"], ["Zhongguo Ming shi xue hui"])
        self.assertEqual(rec["publishers"], ["北京市, 中國明史學會"])
        self.assertEqual(rec["subjects"], ["China -- History -- Ming dynasty"])
        self.assertEqual(rec["identifiers"]["ISSN"], ["1000-0000"])
        self.assertEqual(rec["holdings"], [{"collection": "China Monographic Serials", "format": "electronic resource"}])
        self.assertEqual(rec["call_numbers"], [])
        self.assertTrue(rec["url"].startswith("https://mit.primo"))

    def test_empty_record(self):
        rec = summarize({})
        self.assertEqual(rec["title"], "")
        self.assertEqual(rec["holdings"], [])


class BuildArgsTest(unittest.TestCase):
    def test_maps_fields_and_filters(self):
        args = TimdexAPI.build_search_args(
            {"searchterm": "明史", "title": None},
            {"source": "MIT Alma", "language": "chinese", "place": ""},
            mode="hybrid", boolean="and", start=20, limit=500,
        )
        self.assertEqual(args, {
            "searchterm": "明史", "sourceFilter": "MIT Alma", "languagesFilter": "chinese",
            "queryMode": "hybrid", "booleanType": "AND", "from": "20", "perPage": 100,
        })

    def test_bad_input(self):
        with self.assertRaises(ValueError):
            TimdexAPI.build_search_args({"searchterm": None}, {})
        with self.assertRaises(ValueError):
            TimdexAPI.build_search_args({"searchterm": "x"}, {"nonsense": "y"})
        with self.assertRaises(ValueError):
            TimdexAPI.build_search_args({"searchterm": "x"}, {}, mode="magic")


class QueryTest(unittest.TestCase):
    def setUp(self):
        self._urlopen = urllib.request.urlopen

    def tearDown(self):
        urllib.request.urlopen = self._urlopen

    def _reply(self, payload):
        urllib.request.urlopen = lambda req, timeout=None: FakeResponse(json.dumps(payload).encode())

    def test_graphql_errors_raise(self):
        self._reply({"errors": [{"message": "Field 'x' doesn't exist"}]})
        with self.assertRaises(TimdexError):
            TimdexAPI(min_interval=0).query("{ x }")

    def test_search_parses_hits_and_facets(self):
        self._reply({"data": {"search": {
            "hits": 591,
            "aggregations": {"source": [{"key": "mit alma", "docCount": 591}]},
            "records": [SAMPLE_RECORD],
        }}})
        result = TimdexAPI(min_interval=0).search("明史", facets=True)
        self.assertEqual(result["total"], 591)
        self.assertEqual(result["facets"]["source"], [("mit alma", 591)])
        self.assertEqual(result["records"][0]["title"], "明史研究")

    def test_missing_record_returns_none(self):
        self._reply({"data": {"recordId": None}})
        self.assertIsNone(TimdexAPI(min_interval=0).get_record("alma:0"))


class PhraseTest(unittest.TestCase):
    """Issue #3: booleanType does not narrow field searches; phrase=True filters titles."""

    def test_title_matches(self):
        from scripts.timdex_api import title_matches
        self.assertTrue(title_matches({"title": "明史研究論叢"}, "明史"))
        self.assertFalse(title_matches({"title": "香港廟宇碑刻志"}, "文廟"))
        self.assertTrue(title_matches({"title": "x", "alternate_titles": ["Ming shi yan jiu"]}, "ming shi"))
        self.assertFalse(title_matches({"title": "Mingshi"}, "ming shi"))
        self.assertFalse(title_matches({}, "x"))

    def test_phrase_filters_page_and_reports_returned(self):
        payload = {"data": {"search": {"hits": 2, "records": [
            SAMPLE_RECORD, dict(SAMPLE_RECORD, title="香港廟宇碑刻志", alternateTitles=None),
        ]}}}
        urllib.request.urlopen = lambda req, timeout=None: FakeResponse(json.dumps(payload).encode())
        try:
            result = TimdexAPI(min_interval=0).search("明史", boolean="AND", phrase=True)
        finally:
            urllib.request.urlopen = self._urlopen
        self.assertEqual(result["returned"], 2)
        self.assertEqual([r["title"] for r in result["records"]], ["明史研究"])

    def test_phrase_needs_text_and_summaries(self):
        with self.assertRaises(ValueError):
            TimdexAPI(min_interval=0).search(subjects="China", phrase=True)
        with self.assertRaises(ValueError):
            TimdexAPI(min_interval=0).search("x", raw=True, phrase=True)

    def setUp(self):
        self._urlopen = urllib.request.urlopen


class NetworkRetryTest(unittest.TestCase):
    """Dropped connections and timeouts are retried (same fix as issue #2)."""

    def setUp(self):
        import urllib.request
        from scripts import timdex_api as module
        self.module, self.urllib_request = module, urllib.request
        self._urlopen, self._sleep = urllib.request.urlopen, module.time.sleep
        module.time.sleep = lambda seconds: None

    def tearDown(self):
        self.urllib_request.urlopen = self._urlopen
        self.module.time.sleep = self._sleep

    def _serve(self, outcomes):
        import io
        calls = []

        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def fake(req, timeout=None):
            outcome = outcomes[min(len(calls), len(outcomes) - 1)]
            calls.append(1)
            if isinstance(outcome, BaseException):
                raise outcome
            return Response(outcome.encode())
        self.urllib_request.urlopen = fake
        return calls

    def test_retries_then_succeeds(self):
        calls = self._serve([ConnectionResetError(54, "reset"), TimeoutError("timed out"), '{"data": {"ping": "pong"}}'])
        TimdexAPI(min_interval=0).query("{ ping }")
        self.assertEqual(len(calls), 3)

    def test_gives_up(self):
        calls = self._serve([TimeoutError("timed out")])
        with self.assertRaises(TimeoutError):
            TimdexAPI(min_interval=0).query("{ ping }")
        self.assertEqual(len(calls), self.module.MAX_ATTEMPTS)


class CliTest(unittest.TestCase):
    """Issue #24: the CLI --limit default matches the Python default (20)."""

    def setUp(self):
        self._search = TimdexAPI.search
        self.calls = []

        def fake_search(api, searchterm=None, **kwargs):
            self.calls.append(kwargs)
            return {"total": 0, "start": 0, "returned": 0, "records": []}

        TimdexAPI.search = fake_search

    def tearDown(self):
        TimdexAPI.search = self._search

    def run_main(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = timdex_api.main(list(argv))
        return code, out.getvalue()

    def test_limit_default_is_20(self):
        import inspect
        self.assertEqual(inspect.signature(self._search).parameters["limit"].default, 20)
        self.run_main("search", "明史")
        self.assertEqual(self.calls[-1]["limit"], 20)
        self.run_main("search", "明史", "--limit", "5")
        self.assertEqual(self.calls[-1]["limit"], 5)

    def test_filter_only_search_is_a_clean_error(self):
        TimdexAPI.search = self._search  # the real method raises ValueError before any request
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
            timdex_api.main(["search", "--source", "MIT Alma"])
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("Give search words", err.getvalue())


if __name__ == "__main__":
    unittest.main()
