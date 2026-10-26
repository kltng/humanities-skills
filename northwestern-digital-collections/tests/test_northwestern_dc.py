import io
import json
import sys
import unittest
import urllib.parse
import urllib.request
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.northwestern_dc import NorthwesternDC, summarize_collection, summarize_work


SAMPLE_WORK = {
    "id": "a84ea83c-bf11-4c4f-89ac-87a951b9ce58",
    "title": "Yungang Cave 20. Detail: two Buddhas seated side-by-side",
    "work_type": "Image",
    "date_created": ["467 to 499", "1999"],
    "creator": [],
    "contributor": [
        {"label": "unknown", "role": "Artist", "label_with_role": "unknown (Artist)"},
        {"label": "Linrothe, Robert N., 1951-", "label_with_role": "Linrothe, Robert N., 1951- (Photographer)"},
    ],
    "subject": [{"label": "China--Shanxi Sheng"}, {"label": "China--Shanxi Sheng"}],
    "genre": [{"label": "architecture (object genre)"}],
    "physical_description_material": ["sandstone"],
    "collection": {"title": "Rob Linrothe Image Collection", "description": "..."},
    "rights_statement": None,
    "visibility": "Public",
    "canonical_link": "https://dc.library.northwestern.edu/items/a84ea83c-bf11-4c4f-89ac-87a951b9ce58",
    "iiif_manifest": "https://api.dc.library.northwestern.edu/api/v2/works/a84ea83c?as=iiif",
}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class SummarizeTest(unittest.TestCase):
    def test_work_summary(self):
        rec = summarize_work(SAMPLE_WORK)
        self.assertEqual(rec["dates"], ["467 to 499", "1999"])
        self.assertEqual(rec["creators"], ["unknown (Artist)", "Linrothe, Robert N., 1951- (Photographer)"])
        self.assertEqual(rec["subjects"], ["China--Shanxi Sheng"])
        self.assertEqual(rec["genres"], ["architecture (object genre)"])
        self.assertEqual(rec["collection"], "Rob Linrothe Image Collection")
        self.assertEqual(rec["rights"], "")
        self.assertTrue(rec["url"].startswith("https://dc.library.northwestern.edu/items/"))

    def test_empty_work(self):
        rec = summarize_work({})
        self.assertEqual(rec["creators"], [])
        self.assertEqual(rec["collection"], "")

    def test_collection_summary_trims_description(self):
        rec = summarize_collection({"id": "c1", "title": "T", "description": "x" * 500})
        self.assertEqual(len(rec["description"]), 300)


class RequestTest(unittest.TestCase):
    def setUp(self):
        self._urlopen = urllib.request.urlopen
        self.calls = []

        def fake(req, timeout=None):
            self.calls.append(req)
            return FakeResponse(json.dumps({"data": [SAMPLE_WORK], "pagination": {"total_hits": 48}}).encode())

        urllib.request.urlopen = fake

    def tearDown(self):
        urllib.request.urlopen = self._urlopen

    def test_get_search_sends_query_and_excludes_embeddings(self):
        result = NorthwesternDC(min_interval=0).search("Yungang", limit=5, sort="date_created:asc")
        self.assertEqual(result["total"], 48)
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.calls[0].full_url).query)
        self.assertEqual(params["query"], ["Yungang"])
        self.assertEqual(params["size"], ["5"])
        self.assertIn("embedding", params["_source_excludes"][0])
        self.assertIsNone(self.calls[0].data)

    def test_dsl_search_posts_body(self):
        NorthwesternDC(min_interval=0).search(dsl={"query": {"match": {"title": "Shanghai"}}})
        self.assertEqual(json.loads(self.calls[0].data), {"query": {"match": {"title": "Shanghai"}}})
        self.assertNotIn("query=", self.calls[0].full_url)

    def test_bad_input(self):
        api = NorthwesternDC(min_interval=0)
        with self.assertRaises(ValueError):
            api.search()
        with self.assertRaises(ValueError):
            api.search("x", model="people")


class NetworkRetryTest(unittest.TestCase):
    """Dropped connections and timeouts are retried (same fix as issue #2)."""

    def setUp(self):
        import urllib.request
        from scripts import northwestern_dc as module
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
        calls = self._serve([ConnectionResetError(54, "reset"), TimeoutError("timed out"), '{"data": [], "pagination": {"total_hits": 0}}'])
        NorthwesternDC(min_interval=0).collections()
        self.assertEqual(len(calls), 3)

    def test_gives_up(self):
        calls = self._serve([TimeoutError("timed out")])
        with self.assertRaises(TimeoutError):
            NorthwesternDC(min_interval=0).collections()
        self.assertEqual(len(calls), self.module.MAX_ATTEMPTS)


if __name__ == "__main__":
    unittest.main()
