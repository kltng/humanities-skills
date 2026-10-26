import io
import json
import sys
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import crossref_api
from scripts.crossref_api import (
    CrossrefAPI, CrossrefError, author_matches, clean_abstract, jstor_url,
    normalize_doi, summarize, summarize_reference, title_matches,
)


SAMPLE_WORK = {
    "DOI": "10.2307/2057472",
    "type": "journal-article",
    "title": ["Political, Social, and Cultural Reproduction via Civil Service Examinations in Late Imperial China"],
    "author": [{"given": "Benjamin A.", "family": "Elman", "sequence": "first"}],
    "container-title": ["The Journal of Asian Studies"],
    "publisher": "Duke University Press",
    "issued": {"date-parts": [[1991, 2]]},
    "volume": "50", "issue": "1", "page": "7-28",
    "ISSN": ["0021-9118", "1752-0401", "1752-0401"],
    "abstract": "<jats:title>Abstract</jats:title><jats:p>Most previous scholarship &amp; more.</jats:p>",
    "is-referenced-by-count": 92,
    "references-count": 100,
    "resource": {"primary": {"URL": "https://read.dukeupress.edu/x"}},
    "score": 38.2,
}

CJK_WORK = {
    "DOI": "10.53106/160759942024120043003",
    "type": "journal-article",
    "title": ["明代科舉中的罰科及其影響"],
    "author": [{"given": "劉小龍", "family": "劉小龍"}],
    "container-title": ["明代研究"],
    "issued": {"date-parts": [[2024, 12]]},
}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _http_error(code, body=b""):
    return urllib.error.HTTPError("https://api.crossref.org/x", code, "err", {}, io.BytesIO(body))


class SummarizeTest(unittest.TestCase):
    def test_summary_fields(self):
        rec = summarize(SAMPLE_WORK)
        self.assertEqual(rec["authors"], ["Elman, Benjamin A."])
        self.assertEqual(rec["issued"], "1991-02")
        self.assertEqual(rec["year"], "1991")
        self.assertEqual(rec["issn"], ["0021-9118", "1752-0401"])
        self.assertEqual(rec["abstract"], "Most previous scholarship & more.")
        self.assertEqual(rec["cited_by"], 92)
        self.assertEqual(rec["url"], "https://doi.org/10.2307/2057472")
        self.assertEqual(rec["jstor_url"], "https://www.jstor.org/stable/2057472")
        self.assertEqual(rec["landing_page"], "https://read.dukeupress.edu/x")

    def test_cjk_name_given_equal_to_family_is_shown_once(self):
        self.assertEqual(summarize(CJK_WORK)["authors"], ["劉小龍"])

    def test_subtitle_is_joined(self):
        rec = summarize({"title": ["Main"], "subtitle": ["Sub"]})
        self.assertEqual(rec["title"], "Main: Sub")

    def test_empty_work(self):
        rec = summarize({})
        self.assertEqual(rec["title"], "")
        self.assertEqual(rec["issued"], "")
        self.assertEqual(rec["jstor_url"], "")

    def test_reference(self):
        ref = summarize_reference({"DOI": "10.1/x", "volume-title": "Book", "author": "Chang", "year": "2007"})
        self.assertEqual((ref["doi"], ref["title"], ref["author"]), ("10.1/x", "Book", "Chang"))

    def test_helpers(self):
        self.assertEqual(normalize_doi(" https://doi.org/10.2307/2057472 "), "10.2307/2057472")
        self.assertEqual(normalize_doi("doi:10.1/X"), "10.1/X")
        self.assertEqual(jstor_url("10.2307/j.ctt7sd8m.20"), "https://www.jstor.org/stable/j.ctt7sd8m.20")
        self.assertEqual(jstor_url("10.1353/late.1989.0009"), "")
        self.assertEqual(clean_abstract(""), "")


class MatchTest(unittest.TestCase):
    def test_title_phrase(self):
        self.assertTrue(title_matches(summarize(CJK_WORK), "明代科舉"))
        self.assertFalse(title_matches({"title": "科舉‧家族‧女德：明代楊文儷"}, "明代科舉"))
        self.assertTrue(title_matches(summarize(SAMPLE_WORK), "civil service"))
        self.assertFalse(title_matches({"title": "Serviceable civilians"}, "civil service"))

    def test_author(self):
        self.assertTrue(author_matches({"authors": ["Tang, Kwok-leong"]}, "Kwok-leong Tang"))
        self.assertFalse(author_matches({"authors": ["Ng, Leong Kwok"]}, "Kwok-leong Tang"))
        self.assertTrue(author_matches({"editors": ["劉小龍"]}, "劉小龍"))
        self.assertFalse(author_matches({}, "x"))


class BuildFilterTest(unittest.TestCase):
    def test_combines_parts(self):
        f = CrossrefAPI.build_filter({"has-abstract": True, "type": ["book", "monograph"]},
                                     from_year=2000, until_year="2010-06", jstor=True)
        self.assertEqual(f, "has-abstract:true,type:book,type:monograph,from-pub-date:2000,"
                            "until-pub-date:2010-06,prefix:10.2307")
        self.assertEqual(CrossrefAPI.build_filter("type:book", type="monograph"), "type:book,type:monograph")
        self.assertEqual(CrossrefAPI.build_filter(), "")


class RequestTest(unittest.TestCase):
    def setUp(self):
        self._urlopen = urllib.request.urlopen
        self.calls = []

    def tearDown(self):
        urllib.request.urlopen = self._urlopen

    def _reply(self, payload):
        def fake(req, timeout=None):
            self.calls.append(req)
            if isinstance(payload, BaseException):
                raise payload
            body = payload if isinstance(payload, str) else json.dumps(payload)
            return FakeResponse(body.encode())
        urllib.request.urlopen = fake

    def _params(self, i=0):
        return urllib.parse.parse_qs(urllib.parse.urlparse(self.calls[i].full_url).query)

    def test_search_params_and_filters(self):
        self._reply({"status": "ok", "message": {
            "total-results": 2, "items": [SAMPLE_WORK, CJK_WORK],
            "facets": {"type-name": {"values": {"Journal Article": 2}}}}})
        api = CrossrefAPI(mailto="me@example.org", min_interval=0)
        result = api.search("Ming", author="Elman", container="Late Imperial China", type="journal-article",
                            from_year=1980, rows=5, offset=10, facets="type-name:5", author_match=True)
        params = self._params()
        self.assertEqual(params["query.bibliographic"], ["Ming"])
        self.assertEqual(params["query.author"], ["Elman"])
        self.assertEqual(params["query.container-title"], ["Late Imperial China"])
        self.assertEqual(params["filter"], ["type:journal-article,from-pub-date:1980"])
        self.assertEqual(params["mailto"], ["me@example.org"])
        self.assertEqual(params["offset"], ["10"])
        self.assertNotIn("select", params)
        self.assertIn("mailto:me@example.org", self.calls[0].get_header("User-agent"))
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["returned"], 2)
        self.assertEqual([r["doi"] for r in result["items"]], ["10.2307/2057472"])
        self.assertEqual(result["facets"], {"type-name": [("Journal Article", 2)]})

    def test_issn_route_and_cursor(self):
        self._reply({"status": "ok", "message": {"total-results": 0, "items": [], "next-cursor": "abc"}})
        result = CrossrefAPI(mailto="", min_interval=0).search(author="Elman", issn="1086-3257", cursor="*")
        self.assertIn("/journals/1086-3257/works?", self.calls[0].full_url)
        self.assertEqual(self._params()["cursor"], ["*"])
        self.assertNotIn("mailto", self._params())
        self.assertEqual(result["next_cursor"], "abc")

    def test_bad_input(self):
        api = CrossrefAPI(mailto="", min_interval=0)
        with self.assertRaises(ValueError):
            api.search("x", journal="y")
        with self.assertRaises(ValueError):
            api.search("x", sort="published", cursor="*")
        with self.assertRaises(ValueError):
            api.search("x", offset=9995, rows=10)
        with self.assertRaises(ValueError):
            api.search(author="x", phrase=True)
        with self.assertRaises(ValueError):
            api.search("x", author_match=True)
        with self.assertRaises(ValueError):
            api.search("x", sort="nonsense")

    def test_validation_failure_raises_crossref_error(self):
        body = json.dumps({"status": "failed", "message": [{"message": "Filter 'x' specified but there is no such filter"}]})
        self._reply(_http_error(400, body.encode()))
        with self.assertRaisesRegex(CrossrefError, "no such filter"):
            CrossrefAPI(mailto="", min_interval=0).search("x", filters="x:1")

    def test_missing_work_returns_none(self):
        self._reply(_http_error(404, b"Resource not found."))
        self.assertIsNone(CrossrefAPI(mailto="", min_interval=0).get_work("10.9999/nope"))

    def test_doi_is_quoted_in_path(self):
        self._reply({"status": "ok", "message": SAMPLE_WORK})
        CrossrefAPI(mailto="", min_interval=0).get_work("https://doi.org/10.1002/(SICI)1097-4571<1>3.0.CO;2-#")
        self.assertIn("/works/10.1002/%28SICI%291097-4571%3C1%3E3.0.CO%3B2-%23", self.calls[0].full_url)

    def test_cite_sends_style_in_accept(self):
        self._reply("Elman, Benjamin A. 1991. ...")
        text = CrossrefAPI(mailto="", min_interval=0).cite("10.2307/2057472", style="apa")
        self.assertTrue(text.startswith("Elman"))
        self.assertEqual(self.calls[0].get_header("Accept"), "text/x-bibliography; style=apa; locale=en-US")
        self.assertTrue(self.calls[0].full_url.endswith("/works/10.2307/2057472/transform"))
        with self.assertRaises(ValueError):
            CrossrefAPI(mailto="", min_interval=0).cite("10.1/x", fmt="docx")

    def test_agency_falls_back_to_doi_org(self):
        outcomes = [_http_error(404, b"Resource not found."), json.dumps([{"DOI": "10.13471", "RA": "CNKI"}])]

        def fake(req, timeout=None):
            self.calls.append(req)
            outcome = outcomes[len(self.calls) - 1]
            if isinstance(outcome, BaseException):
                raise outcome
            return FakeResponse(outcome.encode())
        urllib.request.urlopen = fake
        self.assertEqual(CrossrefAPI(mailto="", min_interval=0).agency("10.13471/x"), "CNKI")
        self.assertEqual(self.calls[1].full_url, "https://doi.org/ra/10.13471/x")

    def test_references(self):
        self._reply({"status": "ok", "message": dict(SAMPLE_WORK, reference=[{"DOI": "10.1/y", "year": "2016"}])})
        refs = CrossrefAPI(mailto="", min_interval=0).references("10.2307/2057472")
        self.assertEqual(refs[0]["doi"], "10.1/y")


class NetworkRetryTest(unittest.TestCase):
    """Dropped connections, timeouts, and 429/5xx are retried."""

    def setUp(self):
        self._urlopen, self._sleep = urllib.request.urlopen, crossref_api.time.sleep
        crossref_api.time.sleep = lambda seconds: None

    def tearDown(self):
        urllib.request.urlopen = self._urlopen
        crossref_api.time.sleep = self._sleep

    def _serve(self, outcomes):
        calls = []

        def fake(req, timeout=None):
            outcome = outcomes[min(len(calls), len(outcomes) - 1)]
            calls.append(1)
            if isinstance(outcome, BaseException):
                raise outcome
            return FakeResponse(outcome.encode())
        urllib.request.urlopen = fake
        return calls

    def test_retries_then_succeeds(self):
        ok = json.dumps({"status": "ok", "message": {"total-results": 0, "items": []}})
        calls = self._serve([ConnectionResetError(54, "reset"), _http_error(429), TimeoutError("timed out"), ok])
        CrossrefAPI(mailto="", min_interval=0).search("x")
        self.assertEqual(len(calls), 4)

    def test_gives_up(self):
        calls = self._serve([TimeoutError("timed out")])
        with self.assertRaises(TimeoutError):
            CrossrefAPI(mailto="", min_interval=0).search("x")
        self.assertEqual(len(calls), crossref_api.MAX_ATTEMPTS)


if __name__ == "__main__":
    unittest.main()
