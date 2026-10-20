import json
import sqlite3
import subprocess
import sys
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "cbdb_query.py"
sys.path.insert(0, str(SKILL_DIR / "scripts"))

import cbdb_query

DB_PATH = cbdb_query.DB_PATH


class RunSQLTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("CREATE TABLE sample (id INTEGER, name TEXT)")
        self.conn.execute("INSERT INTO sample VALUES (1, '蘇軾')")

    def tearDown(self):
        self.conn.close()

    def test_run_sql_allows_select(self):
        self.assertEqual(
            cbdb_query.run_sql(self.conn, "SELECT name FROM sample WHERE id = 1"),
            [{"name": "蘇軾"}],
        )

    def test_run_sql_blocks_writes(self):
        self.assertEqual(
            cbdb_query.run_sql(self.conn, "DELETE FROM sample"),
            [{"error": "Only SELECT queries are allowed"}],
        )

    def test_run_sql_returns_json_error_for_bad_select(self):
        result = cbdb_query.run_sql(self.conn, "SELECT * FROM missing_table")
        self.assertEqual(len(result), 1)
        self.assertIn("no such table", result[0]["error"])


@unittest.skipUnless(DB_PATH.exists(), "CBDB SQLite database is not installed")
class InstalledDatabaseTest(unittest.TestCase):
    def run_cli_json(self, *args):
        cp = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            text=True,
            capture_output=True,
            check=True,
        )
        return json.loads(cp.stdout)

    def test_person_id_lookup_returns_su_shi_profile(self):
        profile = self.run_cli_json("person", "--id", "3767")
        self.assertEqual(profile["basic_info"]["name_chn"], "蘇軾")
        self.assertEqual(profile["basic_info"]["dynasty_chn"], "宋")
        self.assertGreaterEqual(len(profile["kinship"]), 20)
        self.assertGreaterEqual(len(profile["offices"]), 30)

    def test_pinyin_lookup_returns_candidate_list_when_ambiguous(self):
        results = self.run_cli_json("person", "Su Shi")
        self.assertGreater(len(results), 1)
        self.assertIn(3767, {row["person_id"] for row in results})

    def test_bad_raw_sql_is_json_not_traceback(self):
        result = self.run_cli_json("sql", "SELECT * FROM ZZZ_BIOG_MAIN")
        self.assertEqual(len(result), 1)
        self.assertIn("no such table", result[0]["error"])


if __name__ == "__main__":
    unittest.main()
