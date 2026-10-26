import io
import json
import sys
import unittest
import urllib.parse
import urllib.request
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.ldt_api import LDTAPI, LDTError, summarize

MADS = "http://www.loc.gov/mads/rdf/v1#"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class SummarizeTest(unittest.TestCase):
    def test_person(self):
        rec = summarize(
            "https://ld.ncl.edu.tw/authority/114743",
            [
                {"p": RDF_TYPE, "o": MADS + "Authority"},
                {"p": RDF_TYPE, "o": MADS + "PersonalName"},
                {"p": MADS + "authoritativeLabel", "o": "王守仁, 1472-1528"},
                {"p": "http://id.loc.gov/vocabulary/identifiers/lccn", "o": ""},
                {"p": "http://id.loc.gov/vocabulary/identifiers/local", "o": "(CYT)AC000207896"},
                {"p": "http://id.loc.gov/ontologies/bflc/marcKey", "o": "1001 $a王守仁,$d1472-1528"},
            ],
            [{"v": "王陽明, 1472-1528"}, {"v": "Wang, Yangming, 1472-1528"}, {"v": "王陽明, 1472-1528"}],
            [{"source": "明人傳記資料索引. 民54:", "note": "面28-29.", "status": "found"}],
            [],
        )
        self.assertEqual(rec["label"], "王守仁, 1472-1528")
        self.assertEqual(rec["kind"], "PersonalName")
        self.assertEqual(rec["variants"], ["王陽明, 1472-1528", "Wang, Yangming, 1472-1528"])
        self.assertEqual(rec["sources"][0]["note"], "面28-29.")
        self.assertEqual(rec["local_id"], ["(CYT)AC000207896"])
        self.assertEqual(rec["lccn"], [])

    def test_classification_and_blank_related(self):
        rec = summarize(
            "https://ld.ncl.edu.tw/classification/384863",
            [
                {"p": RDF_TYPE, "o": "http://www.w3.org/2004/02/skos/core#Concept"},
                {"p": "http://www.w3.org/2004/02/skos/core#prefLabel", "o": "王守仁"},
                {"p": "http://www.w3.org/2004/02/skos/core#notation", "o": "T中國作家時代區分表--6.6"},
            ],
            [], [],
            [{"r": "b0", "label": "傷風", "rel": MADS + "hasReciprocalAuthority"}],
        )
        self.assertEqual(rec["kind"], "Classification")
        self.assertEqual(rec["label"], "王守仁")
        self.assertEqual(rec["notation"], "T中國作家時代區分表--6.6")
        self.assertEqual(rec["related"], [{"relation": "hasReciprocalAuthority", "uri": "", "label": "傷風"}])


class RequestTest(unittest.TestCase):
    def setUp(self):
        self._urlopen = urllib.request.urlopen
        self.sent = []
        self.reply = {}

        def fake(req, timeout=None):
            self.sent.append(urllib.parse.parse_qs(req.data.decode()))
            return FakeResponse(json.dumps(self.reply).encode())

        urllib.request.urlopen = fake

    def tearDown(self):
        urllib.request.urlopen = self._urlopen

    def test_literal_escaping(self):
        self.assertEqual(LDTAPI.literal('a"b\\c'), '"a\\"b\\\\c"')

    def test_exact_lookup_matches_tagged_literals(self):
        self.reply = {"results": {"bindings": [
            {"s": {"value": "https://ld.ncl.edu.tw/subject/89443"}, "label": {"value": "孔廟"},
             "type": {"value": MADS + "Authority"}},
            {"s": {"value": "https://ld.ncl.edu.tw/subject/89443"}, "label": {"value": "孔廟"},
             "type": {"value": MADS + "Topic"}},
        ]}}
        result = LDTAPI(min_interval=0).lookup("孔廟")
        self.assertEqual(result, [{"uri": "https://ld.ncl.edu.tw/subject/89443", "label": "孔廟", "kind": "Topic"}])
        query = self.sent[0]["query"][0]
        self.assertIn('"孔廟"@en', query)
        self.assertIn("PREFIX madsrdf:", query)

    def test_reconcile_dedupes_and_expands_ids(self):
        hit = {"id": "/authority/80435", "name": "張祥浩, 1945-", "score": 10.1, "match": False,
               "type": [{"name": "Personal Name", "id": "authority"}]}
        self.reply = {"q0": {"result": [hit, hit]}}
        result = LDTAPI(min_interval=0).reconcile("王守仁", type="authority")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["uri"], "https://ld.ncl.edu.tw/authority/80435")
        self.assertEqual(json.loads(self.sent[0]["queries"][0])["q0"]["type"], "authority")

    def test_bad_input(self):
        api = LDTAPI(min_interval=0)
        with self.assertRaises(ValueError):
            api.lookup("x", mode="fuzzy")
        with self.assertRaises(ValueError):
            api.reconcile("x", type="person")

    def test_unreadable_answer(self):
        urllib.request.urlopen = lambda req, timeout=None: FakeResponse(b"<html>error</html>")
        with self.assertRaises(LDTError):
            LDTAPI(min_interval=0).sparql("SELECT * WHERE { ?s ?p ?o } LIMIT 1")


if __name__ == "__main__":
    unittest.main()
