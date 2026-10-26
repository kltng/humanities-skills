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


class OriginalScriptTitleTest(unittest.TestCase):
    """Issue #19: show the original-script title next to the romanized one."""

    def setUp(self):
        self.api = HarvardLibraryAPI(min_interval=0)

    def test_cjk_pair(self):
        record = {"titleInfo": [
            {"@altRepGroup": "02", "title": "Tian gong kai wu", "subTitle": "3 juan"},
            {"@altRepGroup": "02", "title": "天工開物", "subTitle": "三卷"},
            {"@type": "alternative", "@altRepGroup": "03", "title": "Kai wu"},
        ]}
        self.assertEqual(self.api.get_title(record), "天工開物 : 三卷 (Tian gong kai wu : 3 juan)")
        self.assertEqual(self.api.get_title(record, original=False), "Tian gong kai wu : 3 juan")
        self.assertEqual(self.api.get_original_title(record), "天工開物 : 三卷")
        rec = self.api.summarize(record)
        self.assertEqual((rec["title_romanized"], rec["title_original"]),
                         ("Tian gong kai wu : 3 juan", "天工開物 : 三卷"))

    def test_original_listed_first_and_alternative_first(self):
        record = {"titleInfo": [
            {"@type": "alternative", "title": "Challenge from civil society"},
            {"@altRepGroup": "01", "title": "시민사회의도전 "},
            {"@altRepGroup": "01", "title": "Simin sahoe ui tojŏn ", "subTitle": "Hanʾguk minjuhwa"},
        ]}
        self.assertEqual(self.api.get_title(record), "시민사회의도전 (Simin sahoe ui tojŏn : Hanʾguk minjuhwa)")

    def test_script_attribute(self):
        record = {"titleInfo": [
            {"@altRepGroup": "01", "@script": "Latn", "title": "Tenkō kaibutsu"},
            {"@altRepGroup": "01", "@script": "Hani", "title": "天工開物"},
        ]}
        self.assertEqual(self.api.get_original_title(record), "天工開物")

    def test_no_original(self):
        for record in ({"titleInfo": {"title": "Hamlet"}},
                       {"titleInfo": [{"title": "Hamlet"}, {"@type": "uniform", "title": "Hamlet."}]},
                       {"titleInfo": [{"@altRepGroup": "01", "title": "明史"}]}):
            self.assertEqual(self.api.get_original_title(record), "")
        self.assertEqual(self.api.get_title({"titleInfo": [{"@altRepGroup": "01", "title": "明史"}]}), "明史")


if __name__ == "__main__":
    unittest.main()
