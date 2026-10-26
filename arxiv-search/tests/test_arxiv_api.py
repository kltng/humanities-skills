import io
import sys
import unittest
import urllib.parse
import urllib.request
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.arxiv_api import ArxivAPI, normalize_query


FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
<opensearch:totalResults>0</opensearch:totalResults>
<opensearch:startIndex>0</opensearch:startIndex>
<opensearch:itemsPerPage>0</opensearch:itemsPerPage>
</feed>"""


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class QueryEncodingTest(unittest.TestCase):
    """Issue #18: hand-encoded queries were encoded twice and returned 0."""

    def setUp(self):
        self._urlopen = urllib.request.urlopen
        self.urls = []

        def fake(req, timeout=None):
            self.urls.append(req.full_url)
            return FakeResponse(FEED)
        urllib.request.urlopen = fake

    def tearDown(self):
        urllib.request.urlopen = self._urlopen

    def sent_query(self):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.urls[-1]).query)
        return params["search_query"][0]

    def test_plain_query_sent_as_is(self):
        ArxivAPI(min_request_interval=0).search('ti:"classical Chinese" AND cat:cs.CL')
        self.assertEqual(self.sent_query(), 'ti:"classical Chinese" AND cat:cs.CL')
        self.assertNotIn("%2522", self.urls[-1])

    def test_pre_encoded_query_decoded_once(self):
        ArxivAPI(min_request_interval=0).search("ti:%22classical+Chinese%22")
        self.assertEqual(self.sent_query(), 'ti:"classical Chinese"')
        self.assertNotIn("%2522", self.urls[-1])

    def test_normalize_query(self):
        self.assertEqual(normalize_query("au:bengio+AND+%28cat:cs.LG+OR+cat:cs.AI%29"),
                         "au:bengio AND (cat:cs.LG OR cat:cs.AI)")
        self.assertEqual(normalize_query("cat:cs.CL AND submittedDate:%5B202401010000+TO+202412312359%5D"),
                         "cat:cs.CL AND submittedDate:[202401010000 TO 202412312359]")
        # Lowercase escapes work too.
        self.assertEqual(normalize_query("ti:%22a+b%22".lower()), 'ti:"a b"')
        # No escapes: unchanged, a literal "+" survives.
        self.assertEqual(normalize_query("ti:C++"), "ti:C++")
        self.assertEqual(normalize_query('ti:"large language model"'), 'ti:"large language model"')


if __name__ == "__main__":
    unittest.main()
