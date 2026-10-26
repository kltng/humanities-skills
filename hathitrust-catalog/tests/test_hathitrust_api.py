import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.hathitrust_api import HathiTrustAPI


def resp(*items):
    return {"records": {"1": {"titles": ["x"]}}, "items": list(items)}


def item(code, us_string="", url="https://babel.hathitrust.org/cgi/pt?id=x"):
    return {"rightsCode": code, "usRightsString": us_string, "itemURL": url}


class FullViewTest(unittest.TestCase):
    """Issue #11: pdus / "Full view" were reported as not readable."""

    def test_pdus_live_shape_is_full_view_in_us(self):
        # Shape seen live for OCLC 34674216 on 2026-10-26.
        r = resp(item("pdus", "Full view", "https://babel.hathitrust.org/cgi/pt?id=hvd.32044067793331"))
        self.assertTrue(HathiTrustAPI.has_full_view(r))
        self.assertEqual(HathiTrustAPI.get_full_view_url(r),
                         "https://babel.hathitrust.org/cgi/pt?id=hvd.32044067793331")

    def test_pdus_not_open_outside_us(self):
        self.assertFalse(HathiTrustAPI.has_full_view(resp(item("pdus", "Full view")), us=False))

    def test_icus_open_outside_us_only(self):
        r = resp(item("icus", "Limited (search-only)"))
        self.assertFalse(HathiTrustAPI.has_full_view(r))
        self.assertTrue(HathiTrustAPI.has_full_view(r, us=False))

    def test_open_codes(self):
        for code in ["pd", "PD", "ic-world", "und-world", "cc-by-4.0", "cc-zero", "cc-by-nc-nd-3.0"]:
            with self.subTest(code=code):
                self.assertTrue(HathiTrustAPI.is_full_view(item(code)))
                self.assertTrue(HathiTrustAPI.is_full_view(item(code), us=False))

    def test_closed_codes(self):
        for code in ["ic", "op", "orph", "orphcand", "und", "umall", "nobody", "pd-pvt", "supp"]:
            with self.subTest(code=code):
                self.assertFalse(HathiTrustAPI.is_full_view(item(code)))
                self.assertFalse(HathiTrustAPI.is_full_view(item(code), us=False))

    def test_rights_code_wins_over_string(self):
        self.assertFalse(HathiTrustAPI.is_full_view(item("ic", "Full view")))

    def test_string_fallback_case_insensitive(self):
        for s in ["Full view", "Full View", "full view"]:
            self.assertTrue(HathiTrustAPI.is_full_view({"usRightsString": s}))
        self.assertFalse(HathiTrustAPI.is_full_view({"usRightsString": "Limited (search-only)"}))

    def test_first_full_view_url_skips_closed(self):
        r = resp(item("ic", url="a"), item("pd", url="b"))
        self.assertEqual(HathiTrustAPI.get_full_view_url(r), "b")
        self.assertIsNone(HathiTrustAPI.get_full_view_url(resp(item("ic"))))

    def test_summarize(self):
        s = HathiTrustAPI(min_interval=0).summarize(resp(item("pdus", "Full view", url="u")))
        self.assertTrue(s["has_full_view"])
        self.assertEqual(s["full_view_url"], "u")


MARC = (
    '<?xml version="1.0" encoding="UTF-8"?><collection xmlns="http://www.loc.gov/MARC21/slim"><record>'
    '<datafield tag="880" ind1=" " ind2="0"><subfield code="6">830-53/</subfield>'
    '<subfield code="a">武英殿聚珍板全書 ;</subfield></datafield>'
    '<datafield tag="880" ind1="1" ind2="0"><subfield code="6">245-01/</subfield>'
    '<subfield code="a">欽定四庫全書總目 :</subfield><subfield code="b">二〇〇卷, 卷首四卷.</subfield>'
    '</datafield></record></collection>'
)


class OriginalTitleTest(unittest.TestCase):
    def test_reads_880_linked_to_245(self):
        r = {"records": {"1": {"titles": ["Qin ding Si ku quan shu zong mu"], "marc-xml": MARC}}, "items": []}
        self.assertEqual(HathiTrustAPI.get_original_title(r), "欽定四庫全書總目 : 二〇〇卷, 卷首四卷")

    def test_brief_response_gives_empty(self):
        self.assertEqual(HathiTrustAPI.get_original_title(resp()), "")


if __name__ == "__main__":
    unittest.main()
