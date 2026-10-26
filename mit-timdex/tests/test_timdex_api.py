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


if __name__ == "__main__":
    unittest.main()
