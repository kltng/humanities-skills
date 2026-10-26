import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.lux_api import LuxAPI, summarize


SAMPLE_OBJECT = {
    "id": "https://lux.collections.yale.edu/data/object/d8030f43-3681-405a-9f5f-af1c35217d58",
    "type": "HumanMadeObject",
    "_label": "明史選輯",
    "identified_by": [
        {"type": "Name", "content": "明史選輯"},
        {"type": "Name", "content": "Ming shi xuan ji"},
        {"type": "Identifier", "content": "Fv3470 4332 307"},
    ],
    "classified_as": [{"type": "Type", "_label": "Books"}],
    "member_of": [{"type": "Set", "_label": "Offsite Storage, Yale University Library"}],
    "referred_to_by": [
        {"type": "LinguisticObject", "content": "4 v. in 1. 19 cm.",
         "classified_as": [{"_label": "Physical Statement"}]},
        {"type": "LinguisticObject", "content": "  "},
    ],
    "produced_by": {
        "timespan": {"begin_of_the_begin": "1700-01-01T00:00:00Z", "end_of_the_end": "1799-12-31T23:59:59Z"},
        "carried_out_by": [{"_label": "Zhonghua shu ju"}],
    },
    "equivalent": [{"id": "https://linked-art.library.yale.edu/node/cab18ca0"}],
    "subject_of": [{
        "digitally_carried_by": [{
            "access_point": [{"id": "https://search.library.yale.edu/catalog/9929486513408651"}],
        }],
    }],
}


class LuxSummarizeTest(unittest.TestCase):
    def setUp(self):
        self.rec = summarize(SAMPLE_OBJECT)

    def test_names_and_identifiers_are_split(self):
        self.assertEqual(self.rec["label"], "明史選輯")
        self.assertEqual(self.rec["names"], ["明史選輯", "Ming shi xuan ji"])
        self.assertEqual(self.rec["identifiers"], ["Fv3470 4332 307"])

    def test_notes_dates_makers_links(self):
        self.assertEqual(self.rec["notes"], ["Physical Statement: 4 v. in 1. 19 cm."])
        self.assertEqual(self.rec["dates"], {"produced_by": "1700-01-01 – 1799-12-31"})
        self.assertEqual(self.rec["makers"], ["Zhonghua shu ju"])
        self.assertEqual(self.rec["member_of"], ["Offsite Storage, Yale University Library"])
        self.assertEqual(self.rec["links"], ["https://search.library.yale.edu/catalog/9929486513408651"])

    def test_empty_document(self):
        rec = summarize({})
        self.assertEqual(rec["names"], [])
        self.assertEqual(rec["dates"], {})


class LuxQueryTest(unittest.TestCase):
    def test_build_query(self):
        self.assertEqual(LuxAPI.build_query("明史"), {"text": "明史"})
        self.assertEqual(LuxAPI.build_query("Wen", field="name"), {"name": "Wen"})
        raw = {"AND": [{"text": "Ming"}]}
        self.assertIs(LuxAPI.build_query("ignored", query=raw), raw)
        with self.assertRaises(ValueError):
            LuxAPI.build_query()

    def test_bad_scope(self):
        with self.assertRaises(ValueError):
            LuxAPI().search("x", scope="nonsense")


class NetworkRetryTest(unittest.TestCase):
    """Dropped connections and timeouts are retried (same fix as issue #2)."""

    def setUp(self):
        import urllib.request
        from scripts import lux_api as module
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
        calls = self._serve([ConnectionResetError(54, "reset"), TimeoutError("timed out"), '{"id": "x"}'])
        LuxAPI(min_interval=0).get("person/x", raw=True)
        self.assertEqual(len(calls), 3)

    def test_gives_up(self):
        calls = self._serve([TimeoutError("timed out")])
        with self.assertRaises(TimeoutError):
            LuxAPI(min_interval=0).get("person/x", raw=True)
        self.assertEqual(len(calls), self.module.MAX_ATTEMPTS)


if __name__ == "__main__":
    unittest.main()
