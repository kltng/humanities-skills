import json
import subprocess
import sys
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "query_tgaz.py"

sys.path.insert(0, str(SKILL_DIR / "scripts"))

import query_tgaz

# The database is not in the repo; use whichever copy query_tgaz would find.
DB_PATH = next((p for p in query_tgaz.db_candidates() if p.exists()), None)
HAS_DB = DB_PATH is not None


@unittest.skipUnless(HAS_DB, "TGAZ SQLite database is not installed")
class TGAZCLITest(unittest.TestCase):
    def run_cli(self, *args, check=True):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            text=True,
            capture_output=True,
            check=check,
        )

    def run_cli_json(self, *args):
        cp = self.run_cli(*args, "--format", "json")
        return json.loads(cp.stdout)

    def test_cli_finds_database_from_other_cwd(self):
        cp = subprocess.run(
            [sys.executable, str(SCRIPT), "北京", "--format", "json", "--limit", "1"],
            cwd=SKILL_DIR.parent,
            text=True,
            capture_output=True,
            check=True,
        )
        rows = json.loads(cp.stdout)
        self.assertEqual(len(rows), 1)
        self.assertIn("北京", rows[0]["name"])

    def test_stats_match_database(self):
        stats = json.loads(self.run_cli("--stats").stdout)
        self.assertEqual(stats["total_placenames"], 82117)
        self.assertEqual(stats["total_spellings"], 245042)
        self.assertEqual(stats["total_relationships"], 83400)

    def test_english_feature_type_resolves_to_county_terms(self):
        rows = self.run_cli_json("--feature-type", "county", "--year", "1820", "--limit", "50")
        self.assertEqual(len(rows), 50)
        self.assertTrue(all(row["ftype_tr"] in {"xian", "gun", "uezd"} for row in rows))

    def test_english_feature_type_with_name(self):
        rows = self.run_cli_json("长安", "--feature-type", "county")
        self.assertGreaterEqual(len(rows), 1)
        self.assertTrue(all(row["ftype_tr"] == "xian" for row in rows))

    def test_native_feature_type_still_works(self):
        for ftype in ("xian", "县"):
            rows = self.run_cli_json("--feature-type", ftype, "--year", "1820", "--limit", "5")
            self.assertEqual(len(rows), 5, ftype)

    def test_fts_falls_back_from_english_feature_word(self):
        rows = self.run_cli_json("--fts", "county Beijing", "--limit", "5")
        self.assertGreaterEqual(len(rows), 1)
        self.assertTrue(all(row["ftype_tr"] == "xian" for row in rows))

    def test_fts_fallback_after_syntax_error(self):
        # The apostrophe forces the quoted-phrase retry; the English word
        # must still be expanded after that.
        rows = self.run_cli_json("--fts", "Chang'an county", "--limit", "5")
        self.assertGreaterEqual(len(rows), 1)

    def test_history_returns_spellings_and_place(self):
        history = json.loads(self.run_cli("--history", "hvd_70621").stdout)
        self.assertEqual(history["place"]["sys_id"], "hvd_70621")
        self.assertGreaterEqual(len(history["spellings"]), 3)

    def test_traditional_characters_find_places(self):
        rows = self.run_cli_json("蘇州", "--good-coords")
        self.assertGreaterEqual(len(rows), 1)
        self.assertTrue(all(row["bad_coords"] == 0 for row in rows))

    def test_romanization_with_space_and_year(self):
        rows = self.run_cli_json("suzhou", "--year", "1100")
        self.assertIn("hvd_32071", [row["sys_id"] for row in rows])
        self.assertTrue(all(row["beg_yr"] <= 1100 <= row["end_yr"] for row in rows))

    def test_parent_in_year_asked(self):
        rows = self.run_cli_json("杭州府", "--year", "1600", "--good-coords")
        self.assertEqual(rows[0]["parent_vn"], "浙江布政使司")

    def test_children_of_ming_zhejiang(self):
        rows = self.run_cli_json("--parent", "hvd_30037", "--year", "1600")
        self.assertEqual(len(rows), 11)

    def test_bad_sql_exits_cleanly(self):
        cp = self.run_cli("--sql", "SELECT * FROM missing_table", check=False)
        self.assertNotEqual(cp.returncode, 0)
        self.assertIn("no such table: missing_table", cp.stderr)


@unittest.skipUnless(HAS_DB, "TGAZ SQLite database is not installed")
class FeatureTypeResolutionTest(unittest.TestCase):
    def setUp(self):
        self.conn = query_tgaz.get_conn(DB_PATH)

    def tearDown(self):
        self.conn.close()

    def test_exact_english_match(self):
        self.assertEqual(
            set(query_tgaz.english_feature_terms(self.conn, "County")),
            {"xian", "gun", "uezd"},
        )

    def test_alias_for_word_not_in_ftype(self):
        self.assertIn("guo", query_tgaz.english_feature_terms(self.conn, "kingdom"))

    def test_non_english_word_is_not_expanded(self):
        self.assertEqual(query_tgaz.english_feature_terms(self.conn, "xian"), [])
        self.assertEqual(query_tgaz.english_feature_terms(self.conn, "Beijing"), [])
        self.assertIsNone(query_tgaz._expand_feature_words(self.conn, "Beijing"))

    def test_expanded_query_uses_explicit_and(self):
        self.assertTrue(
            query_tgaz._expand_feature_words(self.conn, "county Beijing").endswith(") AND Beijing")
        )


if __name__ == "__main__":
    unittest.main()
