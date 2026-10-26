import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.harvard_api import HarvardLibraryAPI, mods_text


class ModsTextTest(unittest.TestCase):
    """Issue #6: MODS values can be str, dict (#text), number, or list."""

    def test_shapes(self):
        self.assertEqual(mods_text(" Sŏul "), "Sŏul")
        self.assertEqual(mods_text({"@type": "text", "#text": "Beijing"}), "Beijing")
        self.assertEqual(mods_text(["8 juan"]), "8 juan")
        self.assertEqual(mods_text([1]), "1")
        self.assertEqual(mods_text(["A", {"#text": "B"}, "A", ""]), "A; B")
        self.assertEqual(mods_text(None), "")
        self.assertEqual(mods_text({}), "")
        self.assertIs(HarvardLibraryAPI.text, mods_text)


class ExtractTest(unittest.TestCase):
    def setUp(self):
        self.api = HarvardLibraryAPI(min_interval=0)

    def test_title_with_list_subtitle(self):
        record = {"titleInfo": [{"nonSort": {"#text": "The "}, "title": "Wen miao tong kao", "subTitle": ["8 juan"]}]}
        self.assertEqual(self.api.get_title(record), "The Wen miao tong kao : 8 juan")

    def test_publisher_list(self):
        record = {"originInfo": {"publisher": ["Jiangxi ren min chu ban she", "Jiangxi sheng xin hua shu dian fa xing"]}}
        self.assertEqual(self.api.get_publisher(record),
                         "Jiangxi ren min chu ban she; Jiangxi sheng xin hua shu dian fa xing")

    def test_summarize_odd_shapes(self):
        record = {
            "titleInfo": {"title": ["A", "B"]},
            "originInfo": [{"publisher": {"#text": "Pub"}, "dateIssued": "1872"}],
            "physicalDescription": {"extent": [{"#text": "2 v."}, "26 cm"]},
        }
        rec = self.api.summarize(record)
        self.assertEqual((rec["title"], rec["publisher"], rec["date"], rec["physical_description"]),
                         ("A; B", "Pub", "1872", "2 v.; 26 cm"))

    def test_empty_record(self):
        rec = self.api.summarize({})
        self.assertEqual((rec["title"], rec["publisher"], rec["physical_description"]), ("", "", ""))


if __name__ == "__main__":
    unittest.main()
