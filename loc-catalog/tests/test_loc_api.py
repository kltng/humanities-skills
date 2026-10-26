import io
import json
import sys
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import loc_api
from scripts.loc_api import LocAPI


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


OK = json.dumps({"results": [], "pagination": {"of": 46}})


class SearchTest(unittest.TestCase):
    def setUp(self):
        self._urlopen = urllib.request.urlopen
        self.calls = []

        def fake(req, timeout=None):
            self.calls.append((req, timeout))
            return FakeResponse(OK.encode())
        urllib.request.urlopen = fake

    def tearDown(self):
        urllib.request.urlopen = self._urlopen

    def test_params_and_timeout(self):
        LocAPI(min_interval=0, timeout=90).search('"wen miao"', format="books", include_all=True, limit=50)
        req, timeout = self.calls[0]
        self.assertEqual(timeout, 90)
        parsed = urllib.parse.urlparse(req.full_url)
        self.assertEqual(parsed.path, "/books/")
        params = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(params["q"], ['"wen miao"'])
        self.assertEqual(params["all"], ["true"])
        self.assertEqual(params["c"], ["50"])

    def test_bad_format(self):
        with self.assertRaises(ValueError):
            LocAPI(min_interval=0).search("x", format="scrolls")


class NetworkRetryTest(unittest.TestCase):
    """Issue #5: read timeouts are retried."""

    def setUp(self):
        self._urlopen, self._sleep = urllib.request.urlopen, loc_api.time.sleep
        loc_api.time.sleep = lambda seconds: None

    def tearDown(self):
        urllib.request.urlopen = self._urlopen
        loc_api.time.sleep = self._sleep

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
        error_503 = urllib.error.HTTPError("https://www.loc.gov", 503, "busy", {}, io.BytesIO(b""))
        calls = self._serve([TimeoutError("The read operation timed out"), error_503,
                             ConnectionResetError(54, "reset"), OK])
        self.assertEqual(LocAPI(min_interval=0).get_total(q="x"), 46)
        self.assertEqual(len(calls), 4)

    def test_gives_up(self):
        calls = self._serve([TimeoutError("The read operation timed out")])
        with self.assertRaises(TimeoutError):
            LocAPI(min_interval=0).search("文廟")
        self.assertEqual(len(calls), loc_api.MAX_ATTEMPTS)


if __name__ == "__main__":
    unittest.main()
