import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.cbdb_api import CBDBAPI


CURRENT_SCHEMA_PERSON = {
    "BasicInfo": {
        "PersonId": "3767",
        "EngName": "Su Shi",
        "ChName": "蘇軾",
        "Dynasty": "宋",
        "YearBirth": "1036",
        "YearDeath": "1101",
    },
    "PersonAliases": {
        "Alias": [
            {"AliasType": "字", "AliasName": "子瞻"},
            {"AliasType": "室名、別號", "AliasName": "東坡居士"},
        ],
    },
    "PersonEntryInfo": {
        "Entry": {"EntryType": "進士類", "RuShiYear": "1057"},
    },
    "PersonKinshipInfo": {
        "Kinship": {"KinPersonName": "蘇洵", "KinRelName": "父"},
    },
    "PersonPostings": {
        "Posting": [
            {"OfficeName": "朝奉郎", "FirstYear": "1085"},
            {"OfficeName": "翰林侍讀學士", "FirstYear": "1087"},
        ],
    },
    "PersonSocialAssociation": {
        "Association": [
            {"AssocPersonName": "歐陽修", "AssocName": "黨魁為Y"},
            {"AssocPersonName": "李常", "AssocName": "友"},
        ],
    },
}


class CBDBAPITest(unittest.TestCase):
    def setUp(self):
        self.api = CBDBAPI()

    def test_extracts_current_cbdb_schema(self):
        self.assertEqual(len(self.api.get_postings(CURRENT_SCHEMA_PERSON)), 2)
        self.assertEqual(len(self.api.get_social_associations(CURRENT_SCHEMA_PERSON)), 2)
        self.assertEqual(len(self.api.get_kinship(CURRENT_SCHEMA_PERSON)), 1)
        self.assertEqual(len(self.api.get_alt_names(CURRENT_SCHEMA_PERSON)), 2)
        self.assertEqual(len(self.api.get_entries(CURRENT_SCHEMA_PERSON)), 1)

    def test_empty_section_is_an_empty_string(self):
        # CBDB sends "" (not {}) for a section with no records.
        person = {"BasicInfo": {"ChName": "某"}, "PersonPostings": "", "PersonKinshipInfo": ""}
        self.assertEqual(self.api.get_postings(person), [])
        self.assertEqual(self.api.get_kinship(person), [])
        self.assertEqual(self.api.get_addresses(person), [])

    def test_person_may_be_a_list(self):
        wrap = lambda p: {"Package": {"PersonAuthority": {"PersonInfo": {"Person": p}}}}
        self.assertEqual(len(self.api._extract_persons(wrap(CURRENT_SCHEMA_PERSON))), 1)
        self.assertEqual(
            len(self.api._extract_persons(wrap([CURRENT_SCHEMA_PERSON, CURRENT_SCHEMA_PERSON]))), 2
        )
        self.assertEqual(self.api._extract_persons({"error": {"code": 404}}), [])

    def test_unknown_year_zero_is_not_shown(self):
        person = {"BasicInfo": {"ChName": "某"},
                  "PersonPostings": {"Posting": {"OfficeName": "知縣", "FirstYear": "0"}}}
        summary = self.api.summarize(person)
        self.assertIn("- 知縣", summary)
        self.assertNotIn("(0)", summary)

    def test_summary_includes_current_schema_sections(self):
        summary = self.api.summarize(CURRENT_SCHEMA_PERSON)

        self.assertIn("# 蘇軾 (Su Shi) — CBDB ID 3767", summary)
        self.assertIn("- 字: 子瞻", summary)
        self.assertIn("## Official Positions (2 records)", summary)
        self.assertIn("- 朝奉郎 (1085)", summary)
        self.assertIn("## Social Associations (2 records)", summary)
        self.assertIn("- 歐陽修 (黨魁為Y)", summary)


if __name__ == "__main__":
    unittest.main()
