import io
import json
import sys
import unittest
import urllib.parse
import urllib.request
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import wikidata_api
from scripts.wikidata_api import MaxlagError, WikidataAPI


class FakeResponse(io.BytesIO):
    def __init__(self, data, headers=None):
        super().__init__(json.dumps(data).encode())
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


MAXLAG = {"error": {"code": "maxlag", "info": "Waiting for wdqs1016: 11.6 seconds lagged."}}


def params_of(req):
    return urllib.parse.parse_qs(urllib.parse.urlparse(req.full_url).query)


class FakeNetTest(unittest.TestCase):
    def setUp(self):
        self._urlopen = urllib.request.urlopen
        self.calls = []
        self.handler = None

        def fake(req, timeout=None):
            self.calls.append(req)
            return self.handler(req)
        urllib.request.urlopen = fake
        self._sleep = mock.patch.object(wikidata_api.time, "sleep")
        self.sleeps = self._sleep.start()

    def tearDown(self):
        urllib.request.urlopen = self._urlopen
        self._sleep.stop()


class MaxlagTest(FakeNetTest):
    """Issue #16: read calls must not fail just because Wikidata is lagged."""

    def lagged_unless_no_maxlag(self, req):
        if "maxlag" in params_of(req):
            return FakeResponse(MAXLAG, {"Retry-After": "5"})
        return FakeResponse({"search": [{"id": "Q9397"}]})

    def test_retries_then_falls_back_without_maxlag(self):
        self.handler = self.lagged_unless_no_maxlag
        wd = WikidataAPI(min_request_interval=0)
        result = wd.search("Zhu Xi")
        self.assertEqual(result, [{"id": "Q9397"}])
        with_lag = [c for c in self.calls if "maxlag" in params_of(c)]
        self.assertEqual(len(with_lag), 3)  # first try + 2 retries
        self.assertNotIn("maxlag", params_of(self.calls[-1]))
        self.assertEqual(len(self.calls), 4)
        # Waits grow but stay capped.
        waits = [c.args[0] for c in self.sleeps.call_args_list]
        self.assertEqual(waits, [5.0, 10.0])

    def test_no_fallback_raises(self):
        self.handler = self.lagged_unless_no_maxlag
        wd = WikidataAPI(min_request_interval=0, maxlag_fallback=False)
        with self.assertRaises(MaxlagError):
            wd.search("Zhu Xi")

    def test_maxlag_none_sends_no_maxlag(self):
        self.handler = self.lagged_unless_no_maxlag
        WikidataAPI(min_request_interval=0, maxlag=None).search("Zhu Xi")
        self.assertEqual(len(self.calls), 1)
        self.assertNotIn("maxlag", params_of(self.calls[0]))

    def test_recovers_when_lag_clears(self):
        answers = [FakeResponse(MAXLAG, {"Retry-After": "1"}), FakeResponse({"search": []})]
        self.handler = lambda req: answers.pop(0)
        WikidataAPI(min_request_interval=0).search("x")
        self.assertEqual(len(self.calls), 2)
        self.assertIn("maxlag", params_of(self.calls[1]))


class PropertyLabelTest(FakeNetTest):
    """Issue #16: labels for all properties, in batches of 50."""

    def test_labels_fetched_in_batches(self):
        pids = [f"P{i}" for i in range(1, 121)]

        def handler(req):
            ids = params_of(req)["ids"][0].split("|")
            self.assertLessEqual(len(ids), 50)
            return FakeResponse({"entities": {
                pid: {"labels": {"en": {"value": f"label {pid}"}}} for pid in ids}})
        self.handler = handler
        labels = WikidataAPI(min_request_interval=0)._property_labels(pids)
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(len(labels), 120)
        self.assertEqual(labels["P120"], "label P120")


class UserAgentTest(FakeNetTest):
    def test_env_user_agent(self):
        self.handler = lambda req: FakeResponse({"search": []})
        with mock.patch.dict("os.environ", {"WIKIDATA_USER_AGENT": "MyProject/1.0 (me@uni.edu)"}):
            WikidataAPI(min_request_interval=0, maxlag=None).search("x")
        self.assertEqual(self.calls[0].get_header("User-agent"), "MyProject/1.0 (me@uni.edu)")

    def test_explicit_user_agent_wins(self):
        self.handler = lambda req: FakeResponse({"search": []})
        with mock.patch.dict("os.environ", {"WIKIDATA_USER_AGENT": "Env/1.0"}):
            WikidataAPI(user_agent="Mine/2.0 (x)", min_request_interval=0, maxlag=None).search("x")
        self.assertEqual(self.calls[0].get_header("User-agent"), "Mine/2.0 (x)")


if __name__ == "__main__":
    unittest.main()
