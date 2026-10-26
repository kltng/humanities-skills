import io
import json
import sys
import unittest
import urllib.parse
import urllib.request
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.europeana_api import EuropeanaAPI


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


OK = json.dumps({"success": True, "totalResults": 54, "items": [{"id": "/1/a"}]})


class FilterQuotingTest(unittest.TestCase):
    """Issue #22: filter values are quoted, so multi-word values work."""

    def setUp(self):
        self._urlopen = urllib.request.urlopen
        self.calls = []

        def fake(req, timeout=None):
            self.calls.append(req)
            return FakeResponse(OK.encode())
        urllib.request.urlopen = fake

    def tearDown(self):
        urllib.request.urlopen = self._urlopen

    def qf(self):
        query = urllib.parse.urlparse(self.calls[-1].full_url).query
        return urllib.parse.parse_qs(query).get("qf", [])

    def test_search_quotes_multiword_country(self):
        items = EuropeanaAPI(api_key="k", min_interval=0).search("China", country="United Kingdom")
        self.assertEqual(items, [{"id": "/1/a"}])
        self.assertEqual(self.qf(), ['COUNTRY:"United Kingdom"'])

    def test_search_with_count_quotes_all_filters(self):
        items, total = EuropeanaAPI(api_key="k", min_interval=0).search_with_count(
            "China", type="image", country="United Kingdom", language="en",
            provider="The European Library", data_provider="British Library",
        )
        self.assertEqual(total, 54)
        self.assertEqual(self.qf(), [
            'TYPE:"IMAGE"',
            'COUNTRY:"United Kingdom"',
            'LANGUAGE:"en"',
            'PROVIDER:"The European Library"',
            'DATA_PROVIDER:"British Library"',
        ])

    def test_already_quoted_value_not_double_quoted(self):
        EuropeanaAPI(api_key="k", min_interval=0).search("x", country='"United Kingdom"')
        self.assertEqual(self.qf(), ['COUNTRY:"United Kingdom"'])

    def test_inner_quote_escaped(self):
        EuropeanaAPI(api_key="k", min_interval=0).search("x", data_provider='Museum "Het Huis"')
        self.assertEqual(self.qf(), ['DATA_PROVIDER:"Museum \\"Het Huis\\""'])

    def test_cjk_query_sent_as_utf8(self):
        EuropeanaAPI(api_key="k", min_interval=0).search("天工開物")
        query = urllib.parse.urlparse(self.calls[-1].full_url).query
        self.assertEqual(urllib.parse.parse_qs(query)["query"], ["天工開物"])

    def test_bad_type(self):
        with self.assertRaises(ValueError):
            EuropeanaAPI(api_key="k", min_interval=0).search("x", type="scroll")
        with self.assertRaises(ValueError):
            EuropeanaAPI(api_key="k", min_interval=0).search_with_count("x", type="scroll")


if __name__ == "__main__":
    unittest.main()
