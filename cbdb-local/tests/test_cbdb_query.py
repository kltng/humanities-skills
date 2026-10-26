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


def _fixture_db() -> sqlite3.Connection:
    """Tiny in-memory CBDB with only the columns the query code uses."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE DYNASTIES (c_dy INTEGER, c_dynasty_chn TEXT, c_dynasty TEXT);
        CREATE TABLE BIOG_MAIN (c_personid INTEGER, c_name_chn TEXT, c_name TEXT,
            c_dy INTEGER, c_birthyear INTEGER, c_deathyear INTEGER, c_surname_chn TEXT,
            c_mingzi_chn TEXT, c_female INTEGER, c_index_year INTEGER, c_notes TEXT);
        CREATE TABLE ALTNAME_DATA (c_personid INTEGER, c_alt_name_chn TEXT, c_alt_name TEXT,
            c_alt_name_type_code INTEGER, c_sequence INTEGER);
        CREATE TABLE OFFICE_CODES (c_office_id INTEGER, c_office_chn TEXT,
            c_office_pinyin TEXT, c_office_trans TEXT);
        CREATE TABLE POSTED_TO_OFFICE_DATA (c_personid INTEGER, c_office_id INTEGER,
            c_firstyear INTEGER, c_lastyear INTEGER, c_dy INTEGER, c_notes TEXT, c_sequence INTEGER);
        CREATE TABLE ASSOC_CODES (c_assoc_code INTEGER, c_assoc_desc_chn TEXT, c_assoc_desc TEXT);
        CREATE TABLE ASSOC_DATA (c_personid INTEGER, c_assoc_id INTEGER, c_assoc_code INTEGER,
            c_assoc_first_year INTEGER, c_assoc_last_year INTEGER);

        INSERT INTO DYNASTIES VALUES (19, '明', 'Ming');
        INSERT INTO BIOG_MAIN VALUES
            (30374, '王守仁', 'Wang Shouren', 19, 1472, 1529, '王', '守仁', 0, 1532, NULL),
            (72362, '毛燧傳', 'Mao Suichuan', 19, NULL, NULL, '毛', '燧傳', 0, 1600, NULL),
            (1, '甲', 'Jia', 19, NULL, NULL, '甲', NULL, 0, 1500, NULL),
            (2, '乙', 'Yi', 19, NULL, NULL, '乙', NULL, 0, 1500, NULL),
            (3, '丙', 'Bing', 19, NULL, NULL, '丙', NULL, 0, 1500, NULL);
        INSERT INTO ALTNAME_DATA VALUES
            (72362, '陽明', 'Yangming', 4, 1),
            (30374, '陽明先生', NULL, 5, 1),
            (30374, '陽明子', NULL, 5, 2),
            (30374, '伯安', 'Boan', 4, 1);
        INSERT INTO OFFICE_CODES VALUES (10, '主事', NULL, NULL);
        INSERT INTO POSTED_TO_OFFICE_DATA VALUES
            (30374, 10, NULL, NULL, 19, 'undated', 1),
            (30374, 10, 0, 0, 19, 'zero', 2),
            (30374, 10, 1510, 1511, 19, 'later', 3),
            (30374, 10, 1499, 1500, 19, 'first', 4);
        INSERT INTO ASSOC_CODES VALUES (1, '友', 'friend');
        INSERT INTO ASSOC_DATA VALUES
            (30374, 1, 1, -1, -1),
            (30374, 2, 1, 1520, 1520),
            (30374, 3, 1, 1505, 1506);
    """)
    return conn


class SearchPersonTest(unittest.TestCase):
    """Issue #17: loose alt-name matches must not hide other candidates."""

    def setUp(self):
        self.conn = _fixture_db()

    def tearDown(self):
        self.conn.close()

    def test_alt_name_returns_all_candidates(self):
        results = cbdb_query.search_person(self.conn, "陽明")
        self.assertEqual([r["person_id"] for r in results], [72362, 30374])
        self.assertEqual(results[0]["match_type"], "alt_name")
        self.assertEqual(results[1]["match_type"], "alt_name_partial")
        self.assertEqual(results[1]["matched_name"], "陽明先生")

    def test_surname_plus_alt_name(self):
        results = cbdb_query.search_person(self.conn, "王陽明")
        self.assertEqual([r["person_id"] for r in results], [30374])
        self.assertEqual(results[0]["match_type"], "surname_plus_alt_name")

    def test_wrong_surname_does_not_match(self):
        self.assertEqual(cbdb_query.search_person(self.conn, "李陽明"), [])

    def test_exact_name_is_exact(self):
        results = cbdb_query.search_person(self.conn, "王守仁")
        self.assertEqual(results[0]["match_type"], "name")
        self.assertIn(results[0]["match_type"], cbdb_query.EXACT_MATCH_TYPES)


class OrderingAndTruncationTest(unittest.TestCase):
    def setUp(self):
        self.conn = _fixture_db()

    def tearDown(self):
        self.conn.close()

    def test_undated_offices_sort_last(self):
        notes = [o["notes"] for o in cbdb_query.get_offices(self.conn, 30374)]
        self.assertEqual(notes[:2], ["first", "later"])
        self.assertEqual(set(notes[2:]), {"undated", "zero"})

    def test_associations_dated_first_and_undated_is_none(self):
        rows = cbdb_query.get_associations(self.conn, 30374)
        self.assertEqual([r["assoc_person_id"] for r in rows], [3, 2, 1])
        self.assertIsNone(rows[-1]["first_year"])

    def test_associations_limit_and_count(self):
        self.assertEqual(len(cbdb_query.get_associations(self.conn, 30374, limit=2)), 2)
        self.assertEqual(len(cbdb_query.get_associations(self.conn, 30374, limit=None)), 3)
        self.assertEqual(cbdb_query.count_associations(self.conn, 30374), 3)


class DbOptionTest(unittest.TestCase):
    def test_pop_db_option(self):
        argv = ["cbdb_query.py", "--db", "/x/cbdb.db", "person", "蘇軾"]
        self.assertEqual(cbdb_query._pop_db_option(argv), Path("/x/cbdb.db"))
        self.assertEqual(argv, ["cbdb_query.py", "person", "蘇軾"])
        argv = ["cbdb_query.py", "person", "蘇軾", "--db=/y.db"]
        self.assertEqual(cbdb_query._pop_db_option(argv), Path("/y.db"))
        self.assertEqual(argv, ["cbdb_query.py", "person", "蘇軾"])
        self.assertIsNone(cbdb_query._pop_db_option(["cbdb_query.py", "check"]))

    def test_meta_path_sits_next_to_db(self):
        self.assertEqual(cbdb_query._meta_path_for(Path("/d/my.db")),
                         Path("/d/my.db.release.json"))

    def test_missing_db_via_option_reports_path(self):
        cp = subprocess.run(
            [sys.executable, str(SCRIPT), "--db", "/nonexistent/cbdb.db", "person", "蘇軾"],
            text=True, capture_output=True,
        )
        self.assertEqual(cp.returncode, 1)
        self.assertIn("/nonexistent/cbdb.db", cp.stderr)


class TreeRenderTest(unittest.TestCase):
    """Issue #17: grandchildren must not be drawn as direct children."""

    TREE = {
        "ego_id": "1",
        "nodes": [
            {"id": "1", "name_chn": "甲", "generation": 0, "is_ego": True},
            {"id": "2", "name_chn": "乙", "generation": 1},
            {"id": "3", "name_chn": "丙", "generation": 2},
        ],
        "edges": [
            {"source": "1", "target": "2", "relation_chn": "子", "relation": "S",
             "edge_type": "parent-child", "generation_gap": 1},
            {"source": "1", "target": "3", "relation_chn": "孫", "relation": "SS",
             "edge_type": "parent-child", "generation_gap": 2},
        ],
    }

    def test_mermaid_long_link_for_grandchild(self):
        out = cbdb_query.render_tree_mermaid(self.TREE)
        self.assertIn('p1 -->|"子"| p2', out)
        self.assertIn('p1 -..->|"孫"| p3', out)

    def test_dot_minlen_for_grandchild(self):
        out = cbdb_query.render_tree_dot(self.TREE)
        self.assertIn('"1" -> "3" [label="孫", minlen=2, style=dashed];', out)
        self.assertIn('"1" -> "2" [label="子"];', out)


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

    def test_yangming_lists_candidates_not_one_profile(self):
        results = self.run_cli_json("person", "陽明")
        self.assertIsInstance(results, list)
        ids = [row["person_id"] for row in results]
        self.assertIn(30374, ids)
        self.assertIn(72362, ids)

    def test_surname_plus_alt_name_finds_wang_shouren(self):
        profile = self.run_cli_json("person", "王陽明")
        self.assertEqual(profile["basic_info"]["person_id"], 30374)
        self.assertEqual(profile["match"]["match_type"], "surname_plus_alt_name")

    def test_profile_reports_association_truncation(self):
        profile = self.run_cli_json("person", "--id", "30374")
        self.assertGreater(profile["associations_total"], len(profile["associations"]))
        self.assertIn("truncated", profile)
        self.assertIsNotNone(profile["associations"][0]["first_year"])

    def test_bad_raw_sql_is_json_not_traceback(self):
        result = self.run_cli_json("sql", "SELECT * FROM ZZZ_BIOG_MAIN")
        self.assertEqual(len(result), 1)
        self.assertIn("no such table", result[0]["error"])


if __name__ == "__main__":
    unittest.main()
