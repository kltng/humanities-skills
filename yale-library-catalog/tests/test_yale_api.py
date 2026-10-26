import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.yale_api import (
    NS,
    RECORD_URL,
    SRUError,
    YaleCatalogAPI,
    parse_marc,
    summarize,
)


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
        query = YaleCatalogAPI.build_cql(title="明史", language="chi")
        self.assertEqual(query, 'alma.title="明史" and alma.language="chi"')

    def test_quotes_are_escaped(self):
        query = YaleCatalogAPI.build_cql(title='say "hi"')
        self.assertEqual(query, 'alma.title="say \\"hi\\""')

    def test_truncation_left_unquoted(self):
        self.assertEqual(YaleCatalogAPI.build_cql(call_number="DS753*"), "alma.lc_class_number=DS753*")

    def test_raw_cql_and_sort(self):
        query = YaleCatalogAPI.build_cql(cql="alma.main_pub_date<1700", title="明史", sort="date_asc")
        self.assertEqual(
            query,
            '(alma.main_pub_date<1700) and alma.title="明史" sortBy alma.main_pub_date/sort.ascending',
        )

    def test_empty_values_are_skipped(self):
        self.assertEqual(YaleCatalogAPI.build_cql(title="x", author=None, isbn=""), 'alma.title="x"')

    def test_bad_input_raises(self):
        with self.assertRaises(ValueError):
            YaleCatalogAPI.build_cql()
        with self.assertRaises(ValueError):
            YaleCatalogAPI.build_cql(nonsense="x")
        with self.assertRaises(ValueError):
            YaleCatalogAPI.build_cql(title="x", sort="random")


class SummarizeTest(unittest.TestCase):
    def setUp(self):
        self.rec = summarize(sample_record())

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
            YaleCatalogAPI._raise_diagnostics(ET.fromstring(DIAGNOSTIC_RESPONSE))
        self.assertIn("Query syntax error", str(ctx.exception))

    def test_normal_response_passes(self):
        YaleCatalogAPI._raise_diagnostics(ET.fromstring(SAMPLE_RESPONSE))


class PhraseTest(unittest.TestCase):
    """Issue #1: SRU `=` is not a phrase search; `phrase=True` filters titles."""

    @staticmethod
    def rec(romanized, vernacular=""):
        title = {"romanized": romanized}
        if vernacular:
            title["vernacular"] = vernacular
        return {"titles": [title]}

    def test_romanized_needs_adjacent_syllables(self):
        from scripts.yale_api import title_matches
        self.assertTrue(title_matches(self.rec("Shi dian kao"), "shi dian"))
        self.assertTrue(title_matches(self.rec("Wen miao si dian kao : [50 juan]"), "Wen miao"))
        self.assertFalse(title_matches(self.rec("Shenyang shi dian hua"), "shi hua"))
        self.assertFalse(title_matches(self.rec("Shidian"), "shi dian"))
        self.assertFalse(title_matches(self.rec("Bai shi dianzi"), "shi dian"))

    def test_cjk_substring_and_accents(self):
        from scripts.yale_api import title_matches
        self.assertTrue(title_matches(self.rec("Wen miao si dian kao", "文廟祀典考 :"), "文廟"))
        self.assertFalse(title_matches(self.rec("Wen miao", "文 學 廟"), "文廟祀"))
        self.assertTrue(title_matches(self.rec("Nihon no Kōshibyō"), "koshibyo"))
        self.assertFalse(title_matches({"titles": []}, "x"))
        self.assertFalse(title_matches(self.rec("anything"), "  "))

    def test_phrase_needs_title_and_summaries(self):
        api = YaleCatalogAPI()
        with self.assertRaises(ValueError):
            api.search(author="x", phrase=True)
        with self.assertRaises(ValueError):
            api.search(title="x", raw=True, phrase=True)


if __name__ == "__main__":
    unittest.main()
