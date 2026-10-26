import io
import json
import sys
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import openaire_api
from scripts.openaire_api import (
    OpenAIREAPI, OpenAIREError, quote_value, summarize_datasource, summarize_product,
)


SAMPLE_THESIS = {
    "id": "doi_dedup___::5619fd1bdb39d6549898d1c1583fcdea",
    "type": "publication",
    "mainTitle": "The Ming Shi-lu (veritable records of the Ming Dynasty) as a source for Southeast Asian history",
    "authors": [{"fullName": "Wade, Geoff.", "rank": 1}],
    "publicationDate": "2012-04-25",
    "publisher": "The University of Hong Kong Libraries",
    "language": {"code": "und", "label": "Undetermined"},
    "pids": [{"scheme": "doi", "value": "10.5353/th_b3123394"}, {"scheme": "handle", "value": "10722/34793"}],
    "bestAccessRight": {"code": "c_abf2", "label": "OPEN"},
    "isGreen": True,
    "subjects": [{"subject": {"scheme": "FOS", "value": "0601 history and archaeology"}}],
    "descriptions": ["<jats:p>Thesis &amp; more</jats:p>"],
    "indicators": {"citationImpact": {"citationCount": 1.0}},
    "instances": [
        {"type": "Doctoral thesis", "urls": ["https://doi.org/10.5353/th_b3123394"],
         "hostedBy": {"value": "Unknown Repository"}},
        {"type": "Thesis", "urls": ["https://dx.doi.org/10.5353/th_b3123394"],
         "hostedBy": {"value": "Unknown Repository"}},
        {"type": "Doctoral thesis", "urls": ["https://doi.org/https://doi.org/10.5353/th_b3123394"],
         "hostedBy": {"value": "HKU Scholars Hub"}, "accessRight": {"label": "OPEN"}, "license": "CC BY"},
    ],
    "collectedFrom": [{"value": "Crossref"}, {"value": "HKU Scholars Hub"}],
}

SAMPLE_ARTICLE = {
    "id": "doi_________::9a801389035aa2e105eac8dce493d014",
    "mainTitle": "Analysis of the Causes of the North and South List Case",
    "container": {"name": "International Journal of Education and Humanities", "vol": "9", "sp": "234", "ep": "236"},
    "instances": [],
}


class FakeResponse(io.BytesIO):
    headers = {"x-ratelimit-limit": "7199", "x-ratelimit-used": "3", "Content-Type": "application/json"}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _http_error(code, body=b""):
    return urllib.error.HTTPError("https://api.openaire.eu/x", code, "err", {}, io.BytesIO(body))


class SummarizeTest(unittest.TestCase):
    def test_product_summary(self):
        rec = summarize_product(SAMPLE_THESIS)
        self.assertEqual(rec["doi"], "10.5353/th_b3123394")
        self.assertEqual(rec["pids"]["handle"], ["10722/34793"])
        self.assertEqual(rec["instance_types"], ["Doctoral thesis", "Thesis"])
        self.assertEqual(rec["description"], "Thesis & more")
        self.assertEqual(rec["citation_count"], 1)
        self.assertEqual(rec["subjects"], ["0601 history and archaeology"])
        self.assertTrue(rec["is_green"])

    def test_copies_are_merged_and_cleaned(self):
        copies = summarize_product(SAMPLE_THESIS)["copies"]
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0]["url"], "https://doi.org/10.5353/th_b3123394")
        self.assertEqual(copies[0]["access"], "OPEN")
        self.assertEqual(copies[0]["hosted_by"], "HKU Scholars Hub")
        self.assertEqual(summarize_product(SAMPLE_THESIS)["open_urls"], ["https://doi.org/10.5353/th_b3123394"])

    def test_container_and_empty(self):
        rec = summarize_product(SAMPLE_ARTICLE)
        self.assertEqual((rec["container"], rec["volume"], rec["pages"]),
                         ("International Journal of Education and Humanities", "9", "234-236"))
        empty = summarize_product({})
        self.assertEqual(empty["copies"], [])
        self.assertIsNone(empty["citation_count"])

    def test_doi_from_copy_url_when_no_pid(self):
        rec = summarize_product({
            "mainTitle": "旧幕府聖堂釈奠図",
            "pids": [],
            "instances": [
                {"urls": ["http://example.org/item/1"]},
                {"urls": ["http://dx.doi.org/10.11501/1016515"], "accessRight": {"label": "OPEN"}},
            ],
        })
        self.assertEqual(rec["doi"], "10.11501/1016515")
        self.assertEqual(rec["pids"], {})
        self.assertEqual(rec["open_urls"], ["https://doi.org/10.11501/1016515"])

    def test_pid_doi_wins_over_copy_url(self):
        rec = summarize_product({
            "pids": [{"scheme": "doi", "value": "10.1/a"}],
            "instances": [{"urls": ["https://doi.org/10.1/b"]}],
        })
        self.assertEqual(rec["doi"], "10.1/a")

    def test_no_doi_without_doi_url(self):
        rec = summarize_product({"instances": [{"urls": ["https://hdl.handle.net/10722/1"]}]})
        self.assertEqual(rec["doi"], "")

    def test_datasource(self):
        rec = summarize_datasource({"id": "x", "officialName": "HKU Scholars Hub",
                                    "type": {"value": "Institutional Repository"}})
        self.assertEqual((rec["name"], rec["type"]), ("HKU Scholars Hub", "Institutional Repository"))


class BuildParamsTest(unittest.TestCase):
    def test_quote_value(self):
        self.assertEqual(quote_value("Open Access"), '"Open Access"')
        self.assertEqual(quote_value("publication"), "publication")
        self.assertEqual(quote_value('"Kwok-leong Tang"'), '"Kwok-leong Tang"')
        self.assertEqual(quote_value('("publication" OR "dataset")'), '("publication" OR "dataset")')

    def test_friendly_names_and_quoting(self):
        params = OpenAIREAPI.build_params(
            "明代科舉", phrase=True, open_access=True, instance_type="Doctoral thesis",
            author="Kwok-leong Tang", from_date="2000", peer_reviewed=True, sort="citationCount",
            page=2, page_size=500)
        self.assertEqual(params, {
            "search": '"明代科舉"', "instanceType": '"Doctoral thesis"', "authorFullName": '"Kwok-leong Tang"',
            "fromPublicationDate": "2000", "isPeerReviewed": "true", "accessRightLabel": '"Open Access"',
            "sortBy": "citationCount DESC", "page": 2, "pageSize": 100,
        })

    def test_search_keeps_operators(self):
        params = OpenAIREAPI.build_params('"Ming dynasty" AND examination NOT medicine', phrase=True)
        self.assertEqual(params["search"], '"Ming dynasty" AND examination NOT medicine')

    def test_other_entities_pass_names_through(self):
        params = OpenAIREAPI.build_params("Academia Sinica", entity="organizations", countryCode="TW")
        self.assertEqual(params["countryCode"], "TW")
        self.assertEqual(params["search"], "Academia Sinica")

    def test_bad_input(self):
        with self.assertRaises(ValueError):
            OpenAIREAPI.build_params()
        with self.assertRaises(ValueError):
            OpenAIREAPI.build_params(phrase=True, author="x")
        with self.assertRaises(ValueError):
            OpenAIREAPI.build_params("x", entity="journals")
        with self.assertRaises(ValueError):
            OpenAIREAPI.build_params("x", sort="date")
        with self.assertRaises(ValueError):
            OpenAIREAPI.build_params("x", sort="publicationDate", cursor="*")
        with self.assertRaises(ValueError):
            OpenAIREAPI.build_params("x", page=101, page_size=100)


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
            return FakeResponse(json.dumps(payload).encode())
        urllib.request.urlopen = fake

    def test_search_parses_header_and_items(self):
        self._reply({"header": {"numFound": 49, "page": 1, "pageSize": 1}, "results": [SAMPLE_THESIS]})
        api = OpenAIREAPI(token="", min_interval=0)
        result = api.search("Ming dynasty", instance_type="Doctoral thesis", page_size=1)
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.calls[0].full_url).query)
        self.assertTrue(self.calls[0].full_url.startswith("https://api.openaire.eu/graph/v3/research-products?"))
        self.assertEqual(params["instanceType"], ['"Doctoral thesis"'])
        self.assertIsNone(self.calls[0].get_header("Authorization"))
        self.assertEqual(result["total"], 49)
        self.assertEqual(result["items"][0]["doi"], "10.5353/th_b3123394")
        self.assertEqual(api.rate_limit["x-ratelimit-limit"], "7199")

    def test_token_is_sent(self):
        self._reply({"header": {"numFound": 0}, "results": []})
        OpenAIREAPI(token="abc", min_interval=0).search("x")
        self.assertEqual(self.calls[0].get_header("Authorization"), "Bearer abc")

    def test_find_doi_strips_prefix(self):
        self._reply({"header": {"numFound": 1}, "results": [SAMPLE_THESIS]})
        rec = OpenAIREAPI(token="", min_interval=0).find_doi("https://doi.org/10.5353/th_b3123394")
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.calls[0].full_url).query)
        self.assertEqual(params["pid"], ["10.5353/th_b3123394"])
        self.assertEqual(rec["id"], SAMPLE_THESIS["id"])

    def test_get_missing_returns_none(self):
        self._reply(_http_error(404, b'{"message": "not found"}'))
        self.assertIsNone(OpenAIREAPI(token="", min_interval=0).get("doi_dedup___::nope"))
        self.assertIn("/research-products/doi_dedup___::nope", self.calls[0].full_url)

    def test_bad_request_raises_openaire_error(self):
        body = json.dumps({"message": "Invalid value: 'X' in 'accessRightLabel'. Allowed values are: [...]"})
        self._reply(_http_error(400, body.encode()))
        with self.assertRaisesRegex(OpenAIREError, "accessRightLabel"):
            OpenAIREAPI(token="", min_interval=0).search("x", access="X")


class NetworkRetryTest(unittest.TestCase):
    """Dropped connections, timeouts, and 429/5xx are retried."""

    def setUp(self):
        self._urlopen, self._sleep = urllib.request.urlopen, openaire_api.time.sleep
        openaire_api.time.sleep = lambda seconds: None

    def tearDown(self):
        urllib.request.urlopen = self._urlopen
        openaire_api.time.sleep = self._sleep

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
        ok = json.dumps({"header": {"numFound": 0}, "results": []})
        calls = self._serve([ConnectionResetError(54, "reset"), _http_error(503), TimeoutError("timed out"), ok])
        OpenAIREAPI(token="", min_interval=0).search("x")
        self.assertEqual(len(calls), 4)

    def test_gives_up(self):
        calls = self._serve([TimeoutError("timed out")])
        with self.assertRaises(TimeoutError):
            OpenAIREAPI(token="", min_interval=0).search("x")
        self.assertEqual(len(calls), openaire_api.MAX_ATTEMPTS)


if __name__ == "__main__":
    unittest.main()
