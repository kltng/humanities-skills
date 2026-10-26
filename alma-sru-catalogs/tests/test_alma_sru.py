import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import alma_sru
from scripts.alma_sru import (
    LIBRARIES,
    NS,
    AlmaSRU,
    SRUError,
    parse_marc,
    resolve_libraries,
    search_many,
    summarize,
)

RECORD_URL = LIBRARIES["umich"]["record_url"]


SAMPLE_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <version>1.2</version>
  <numberOfRecords>1</numberOfRecords>
  <records><record><recordSchema>marcxml</recordSchema><recordPacking>xml</recordPacking>
  <recordData>
    <record xmlns="http://www.loc.gov/MARC21/slim">
      <leader>00000cam a2200000 a 4500</leader>
      <controlfield tag="001">990023071550106381</controlfield>
      <controlfield tag="008">780101s1882    cc            000 0 chi d</controlfield>
      <datafield tag="035" ind1=" " ind2=" "><subfield code="a">(OCoLC)ocm12345678</subfield></datafield>
      <datafield tag="035" ind1=" " ind2=" "><subfield code="a">(MiU)002307155</subfield></datafield>
      <datafield tag="050" ind1=" " ind2="4"><subfield code="a">Z3102</subfield><subfield code="b">.P15</subfield></datafield>
      <datafield tag="245" ind1="0" ind2="0">
        <subfield code="6">880-01</subfield>
        <subfield code="a">Ba shi jing ji zhi /</subfield>
      </datafield>
      <datafield tag="260" ind1=" " ind2=" ">
        <subfield code="6">880-02</subfield>
        <subfield code="a">[Suzhou] :</subfield>
        <subfield code="b">[Zhen xian yin shu she],</subfield>
        <subfield code="c">Guangxu 8 nian [1882]</subfield>
      </datafield>
      <datafield tag="650" ind1=" " ind2="0">
        <subfield code="a">Chinese literature</subfield>
        <subfield code="v">Bibliography.</subfield>
      </datafield>
      <datafield tag="880" ind1="0" ind2="0">
        <subfield code="6">245-01/$1</subfield>
        <subfield code="a">八史經籍志 /</subfield>
      </datafield>
      <datafield tag="880" ind1=" " ind2=" ">
        <subfield code="6">260-02/$1</subfield>
        <subfield code="a">[蘇州] :</subfield>
        <subfield code="b">[振新印書社],</subfield>
        <subfield code="c">光緖8年 [1882]</subfield>
      </datafield>
      <datafield tag="AVA" ind1=" " ind2=" ">
        <subfield code="b">BUHR</subfield>
        <subfield code="c">Main</subfield>
        <subfield code="d">Z 3102 .P15</subfield>
        <subfield code="e">available</subfield>
        <subfield code="f">2</subfield>
        <subfield code="g">0</subfield>
        <subfield code="q">Buhr Shelving Facility</subfield>
        <subfield code="t">(v.1-16 1883)</subfield>
      </datafield>
      <datafield tag="AVE" ind1=" " ind2=" ">
        <subfield code="e">Available</subfield>
        <subfield code="m">Zhonghua jing dian gu ji ku.</subfield>
        <subfield code="t">Zhonghua ancient books database</subfield>
        <subfield code="u">https://example.org/openurl?rft.mms_id=990023071550106381</subfield>
      </datafield>
    </record>
  </recordData><recordPosition>1</recordPosition></record></records>
</searchRetrieveResponse>
"""

DIAGNOSTIC_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <version>1.2</version>
  <numberOfRecords>0</numberOfRecords>
  <diagnostics>
    <diagnostic xmlns="http://www.loc.gov/zing/srw/diagnostic/">
      <uri>info:srw/diagnostic/1/10</uri>
      <details>alma.nonsense</details>
      <message>Query syntax error</message>
    </diagnostic>
  </diagnostics>
</searchRetrieveResponse>
"""


def sample_record():
    root = ET.fromstring(SAMPLE_RESPONSE)
    return parse_marc(root.find(".//marc:record", NS))


class BuildCqlTest(unittest.TestCase):
    def test_fields_are_quoted_and_joined(self):
        query = AlmaSRU.build_cql(title="明史", language="chi")
        self.assertEqual(query, 'alma.title="明史" and alma.language="chi"')

    def test_quotes_are_escaped(self):
        query = AlmaSRU.build_cql(title='say "hi"')
        self.assertEqual(query, 'alma.title="say \\"hi\\""')

    def test_truncation_left_unquoted(self):
        self.assertEqual(AlmaSRU.build_cql(call_number="DS753*"), "alma.lc_class_number=DS753*")

    def test_raw_cql_and_sort(self):
        query = AlmaSRU.build_cql(cql="alma.main_pub_date<1700", title="明史", sort="date_asc")
        self.assertEqual(
            query,
            '(alma.main_pub_date<1700) and alma.title="明史" sortBy alma.main_pub_date/sort.ascending',
        )

    def test_empty_values_are_skipped(self):
        self.assertEqual(AlmaSRU.build_cql(title="x", author=None, isbn=""), 'alma.title="x"')

    def test_bad_input_raises(self):
        with self.assertRaises(ValueError):
            AlmaSRU.build_cql()
        with self.assertRaises(ValueError):
            AlmaSRU.build_cql(nonsense="x")
        with self.assertRaises(ValueError):
            AlmaSRU.build_cql(title="x", sort="random")


class SummarizeTest(unittest.TestCase):
    def setUp(self):
        self.rec = summarize(sample_record(), RECORD_URL)

    def test_vernacular_paired_with_romanized(self):
        self.assertEqual(self.rec["title"], "八史經籍志 (Ba shi jing ji zhi)")
        self.assertEqual(self.rec["titles"], [{"romanized": "Ba shi jing ji zhi", "vernacular": "八史經籍志"}])
        self.assertEqual(
            self.rec["publication"],
            "[蘇州] : [振新印書社], 光緖8年 [1882] ([Suzhou] : [Zhen xian yin shu she], Guangxu 8 nian [1882])",
        )

    def test_fixed_fields_and_identifiers(self):
        self.assertEqual(self.rec["mms_id"], "990023071550106381")
        self.assertEqual(self.rec["year"], "1882")
        self.assertEqual(self.rec["language"], "chi")
        self.assertEqual(self.rec["oclc"], ["12345678"])
        self.assertEqual(self.rec["lc_call_number"], "Z3102 .P15")
        self.assertEqual(self.rec["subjects"], ["Chinese literature -- Bibliography"])
        self.assertEqual(self.rec["url"], RECORD_URL.format(mms_id="990023071550106381"))

    def test_holdings(self):
        physical = self.rec["holdings"]["physical"]
        self.assertEqual(len(physical), 1)
        self.assertEqual(physical[0]["library"], "Buhr Shelving Facility")
        self.assertEqual(physical[0]["call_number"], "Z 3102 .P15")
        self.assertEqual(physical[0]["availability"], "available")
        self.assertEqual(physical[0]["summary"], "(v.1-16 1883)")
        electronic = self.rec["holdings"]["electronic"]
        self.assertEqual(electronic[0]["interface"], "Zhonghua ancient books database")
        self.assertEqual(electronic[0]["url"], "https://example.org/openurl?rft.mms_id=990023071550106381")


class DiagnosticsTest(unittest.TestCase):
    def test_diagnostic_raises(self):
        with self.assertRaises(SRUError) as ctx:
            AlmaSRU._raise_diagnostics(ET.fromstring(DIAGNOSTIC_RESPONSE))
        self.assertIn("Query syntax error", str(ctx.exception))

    def test_normal_response_passes(self):
        AlmaSRU._raise_diagnostics(ET.fromstring(SAMPLE_RESPONSE))


class LibrariesTest(unittest.TestCase):
    def test_every_library_is_complete(self):
        for key, lib in LIBRARIES.items():
            self.assertTrue(lib["sru"].startswith("https://") and "/view/sru/" in lib["sru"], key)
            self.assertIn("{mms_id}", lib["record_url"], key)
            self.assertTrue(lib["name"], key)

    def test_resolve_libraries(self):
        self.assertEqual(resolve_libraries("oxford, Cambridge"), ["oxford", "cambridge"])
        self.assertEqual(resolve_libraries("all"), list(LIBRARIES))
        with self.assertRaises(ValueError):
            resolve_libraries("oxford,hogwarts")
        with self.assertRaises(ValueError):
            AlmaSRU("hogwarts")

    def test_summary_without_record_url(self):
        self.assertEqual(summarize(sample_record())["url"], "")

    def test_search_many_isolates_failures(self):
        def fake_search(self, **kwargs):
            if self.library == "oxford":
                raise SRUError("SRU diagnostic: boom")
            return {"library": self.library, "total": 1, "records": [{"mms_id": "1"}]}

        original = AlmaSRU.search
        AlmaSRU.search = fake_search
        try:
            results = search_many(["oxford", "yale"], title="x")
        finally:
            AlmaSRU.search = original
        self.assertIn("boom", results["oxford"]["error"])
        self.assertEqual(results["oxford"]["records"], [])
        self.assertEqual(results["yale"]["total"], 1)

    def test_rate_limit_is_per_host(self):
        a, b = AlmaSRU("oxford"), AlmaSRU("yale")
        self.assertNotEqual(a._host, b._host)
        alma_sru.AlmaSRU._last_request.clear()
        a._rate_limit()
        self.assertIn(a._host, AlmaSRU._last_request)
        self.assertNotIn(b._host, AlmaSRU._last_request)


class PhraseTest(unittest.TestCase):
    """Issue #1: SRU `=` is not a phrase search; `phrase=True` filters titles."""

    @staticmethod
    def rec(romanized, vernacular=""):
        title = {"romanized": romanized}
        if vernacular:
            title["vernacular"] = vernacular
        return {"titles": [title]}

    def test_romanized_needs_adjacent_syllables(self):
        from scripts.alma_sru import title_matches
        self.assertTrue(title_matches(self.rec("Shi dian kao"), "shi dian"))
        self.assertTrue(title_matches(self.rec("Wen miao si dian kao : [50 juan]"), "Wen miao"))
        self.assertFalse(title_matches(self.rec("Shenyang shi dian hua"), "shi hua"))
        self.assertFalse(title_matches(self.rec("Shidian"), "shi dian"))
        self.assertFalse(title_matches(self.rec("Bai shi dianzi"), "shi dian"))

    def test_cjk_substring_and_accents(self):
        from scripts.alma_sru import title_matches
        self.assertTrue(title_matches(self.rec("Wen miao si dian kao", "文廟祀典考 :"), "文廟"))
        self.assertFalse(title_matches(self.rec("Wen miao", "文 學 廟"), "文廟祀"))
        self.assertTrue(title_matches(self.rec("Nihon no Kōshibyō"), "koshibyo"))
        self.assertFalse(title_matches({"titles": []}, "x"))
        self.assertFalse(title_matches(self.rec("anything"), "  "))

    def test_phrase_needs_title_and_summaries(self):
        api = AlmaSRU("umich")
        with self.assertRaises(ValueError):
            api.search(author="x", phrase=True)
        with self.assertRaises(ValueError):
            api.search(title="x", raw=True, phrase=True)


class CatalogingFieldsTest(unittest.TestCase):
    """Subject vocabularies and classification schemes, for comparing cataloging traditions."""

    MARC = {"control": {}, "fields": [
        {"tag": "050", "ind1": " ", "ind2": "4", "subfields": [("a", "DS753"), ("b", ".Z533 2002")]},
        {"tag": "082", "ind1": "0", "ind2": "4", "subfields": [("a", "951.026"), ("2", "23")]},
        {"tag": "084", "ind1": " ", "ind2": " ", "subfields": [("a", "666"), ("b", "8365"), ("2", "ncsclt")]},
        {"tag": "650", "ind1": " ", "ind2": "0", "subfields": [("a", "Temples, Confucian"), ("z", "China.")]},
        {"tag": "650", "ind1": " ", "ind2": "7", "subfields": [("a", "歷史地理"), ("x", "研究"), ("y", "明代"), ("2", "csht")]},
        {"tag": "651", "ind1": " ", "ind2": "4", "subfields": [("a", "China")]},
        {"tag": "655", "ind1": " ", "ind2": "7", "subfields": [("a", "Local histories"), ("2", "fast")]},
    ]}

    def test_subject_headings_keep_vocabulary(self):
        from scripts.alma_sru import subject_headings
        self.assertEqual(subject_headings(self.MARC), [
            {"heading": "Temples, Confucian -- China", "source": "lcsh", "tag": "650"},
            {"heading": "歷史地理 -- 研究 -- 明代", "source": "csht", "tag": "650"},
            {"heading": "China", "source": "unspecified", "tag": "651"},
            {"heading": "Local histories", "source": "fast", "tag": "655"},
        ])

    def test_classifications_keep_scheme(self):
        from scripts.alma_sru import classifications
        self.assertEqual(classifications(self.MARC), [
            {"scheme": "lcc", "number": "DS753 .Z533 2002"},
            {"scheme": "ddc", "number": "951.026"},
            {"scheme": "ncsclt", "number": "666 8365"},
        ])


class RetryTest(unittest.TestCase):
    """Issue #2: dropped connections and timeouts are retried; later-page failures keep fetched records."""

    def setUp(self):
        import urllib.request
        from scripts import alma_sru as module
        self.module = module
        self.urllib_request = urllib.request
        self._urlopen = urllib.request.urlopen
        self._sleep = module.time.sleep
        module.time.sleep = lambda seconds: None
        self.calls = 0

    def tearDown(self):
        self.urllib_request.urlopen = self._urlopen
        self.module.time.sleep = self._sleep

    def _serve(self, outcomes):
        import io

        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def fake(req, timeout=None):
            outcome = outcomes[min(self.calls, len(outcomes) - 1)]
            self.calls += 1
            if isinstance(outcome, BaseException):
                raise outcome
            return Response(outcome.encode())
        self.urllib_request.urlopen = fake

    def page(self, total, n):
        record = SAMPLE_RESPONSE.split("<records>")[1].split("</records>")[0]
        head = SAMPLE_RESPONSE.split("<records>")[0].replace("<numberOfRecords>1<", f"<numberOfRecords>{total}<")
        return head + "<records>" + record * n + "</records></searchRetrieveResponse>"

    def test_network_errors_are_retried(self):
        self._serve([ConnectionResetError(54, "Connection reset by peer"), TimeoutError("timed out"), self.page(1, 1)])
        result = AlmaSRU("sydney", min_interval=0).search(title="x")
        self.assertEqual(self.calls, 3)
        self.assertEqual(result["total"], 1)

    def test_gives_up_after_max_attempts(self):
        self._serve([TimeoutError("timed out")])
        with self.assertRaises(TimeoutError):
            AlmaSRU("sydney", min_interval=0).search(title="x")
        self.assertEqual(self.calls, self.module.MAX_ATTEMPTS)

    def test_later_page_failure_keeps_records(self):
        self._serve([self.page(120, 50)] + [TimeoutError("timed out")] * 10)
        with self.assertRaises(self.module.IncompleteResults) as ctx:
            AlmaSRU("sydney", min_interval=0).search_all(max_results=120, title="x")
        self.assertEqual(len(ctx.exception.records), 50)
        self.assertIn("Stopped at record 51", str(ctx.exception))

    def test_first_page_failure_raises_original_error(self):
        self._serve([ConnectionResetError(54, "reset")])
        with self.assertRaises(ConnectionResetError):
            AlmaSRU("sydney", min_interval=0).search_all(max_results=10, title="x")


if __name__ == "__main__":
    unittest.main()
