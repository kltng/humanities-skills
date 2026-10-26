"""Offline tests: a tiny fixture database, no real tgaz.db needed."""

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "query_tgaz.py"

sys.path.insert(0, str(SKILL_DIR / "scripts"))

import query_tgaz

SCHEMA = """
CREATE TABLE ftype (id INTEGER PRIMARY KEY, name_vn TEXT, name_tr TEXT, name_en TEXT);
CREATE TABLE placename (id INTEGER PRIMARY KEY, sys_id TEXT, beg_yr INTEGER, end_yr INTEGER);
CREATE TABLE spelling (id INTEGER PRIMARY KEY, placename_id INTEGER, script_id INTEGER,
                       written_form TEXT, trsys_id TEXT);
CREATE TABLE part_of (id INTEGER PRIMARY KEY, child_id INTEGER, parent_id INTEGER,
                      begin_year INTEGER, end_year INTEGER);
CREATE TABLE mv_pn_srch (id INTEGER PRIMARY KEY, sys_id TEXT, data_src TEXT, name TEXT,
    transcription TEXT, beg_yr INTEGER, end_yr INTEGER, obj_type TEXT, x_coord TEXT,
    y_coord TEXT, ftype_vn TEXT, ftype_tr TEXT, parent_id INTEGER, parent_sys_id TEXT,
    parent_vn TEXT, parent_tr TEXT);
CREATE VIRTUAL TABLE search_fts USING fts5(sys_id UNINDEXED, name, transcription,
    ftype_vn, ftype_tr, parent_vn, parent_tr, data_src UNINDEXED, beg_yr UNINDEXED,
    end_yr UNINDEXED);
"""

# id, sys_id, name, transcription, beg, end, obj_type, x, y, ftype_vn, ftype_tr, parent
PLACES = [
    (1, "hvd_1", "苏州", "Su Zhou", 758, 1112, "POINT", "120.61862", "31.31271", "州", "zhou", "hvd_5"),
    (2, "hvd_2", "苏州", "Su Zhou", 939, 1112, "POLYGON", "0.00000", "31.312710", "州", "zhou", None),
    (3, "hvd_3", "苏州府", "Suzhou Fu", 1367, 1911, "POINT", "120.61862", "31.31271", "府", "fu", "hvd_5"),
    (4, "hvd_4", "长安县", "Changan Xian", 703, 1911, "POINT", "108.93", "34.26", "县", "xian", None),
    (5, "hvd_5", "江南行省", "Jiangnan Xingsheng", 1300, 1400, "POINT", "118.8", "32.0", "行省", "xingsheng", None),
    (6, "hvd_6", "浙江布政使司", "Zhejiang Buzhengshisi", 1376, 1644, "POINT", "120.1", "30.2", "布政使司", "buzhengshisi", None),
]
SPELLINGS = [
    (1, "蘇州", 1), (1, "苏州", 2), (2, "蘇州", 1), (3, "蘇州府", 1), (3, "苏州府", 2),
    (4, "長安縣", 1),
]
# child, parent, begin, end: hvd_3's earliest parent is hvd_5; from 1376 it is hvd_6.
PART_OF = [(3, 5, 1367, 1375), (3, 6, 1376, 1644)]


def build_fixture(path):
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO ftype VALUES (1, '县', 'xian', 'county')")
    names = {p[1]: p for p in PLACES}
    for (pid, sid, name, tr, beg, end, obj, x, y, fvn, ftr, parent) in PLACES:
        conn.execute("INSERT INTO placename VALUES (?, ?, ?, ?)", (pid, sid, beg, end))
        pvn = names[parent][2] if parent else None
        ptr = names[parent][3] if parent else None
        conn.execute(
            "INSERT INTO mv_pn_srch VALUES (?, ?, 'CHGIS', ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)",
            (pid, sid, name, tr, beg, end, obj, x, y, fvn, ftr, parent, pvn, ptr))
        conn.execute("INSERT INTO search_fts VALUES (?, ?, ?, ?, ?, ?, ?, 'CHGIS', ?, ?)",
                     (sid, name, tr, fvn, ftr, pvn, ptr, beg, end))
    for i, (pid, form, script) in enumerate(SPELLINGS, 1):
        conn.execute("INSERT INTO spelling VALUES (?, ?, ?, ?, 'na')", (i, pid, script, form))
    for i, (c, p, b, e) in enumerate(PART_OF, 1):
        conn.execute("INSERT INTO part_of VALUES (?, ?, ?, ?, ?)", (i, c, p, b, e))
    conn.commit()
    conn.close()


class FixtureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = Path(cls.tmp.name) / "tgaz.db"
        build_fixture(cls.db)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.conn = query_tgaz.get_conn(self.db)

    def tearDown(self):
        self.conn.close()

    def ids(self, rows):
        return [r["sys_id"] for r in rows]

    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), "--db", str(self.db), *args],
                              text=True, capture_output=True)

    def test_traditional_characters_use_spelling_table(self):
        self.assertEqual(self.ids(query_tgaz.search_name(self.conn, "蘇州")),
                         ["hvd_1", "hvd_2", "hvd_3"])
        self.assertEqual(self.ids(query_tgaz.search_name(self.conn, "長安")), ["hvd_4"])

    def test_simplified_still_works(self):
        self.assertEqual(self.ids(query_tgaz.search_name(self.conn, "苏州府")), ["hvd_3"])

    def test_romanization_ignores_spaces_and_apostrophes(self):
        rows = query_tgaz.search_name(self.conn, "suzhou", year=1100)
        self.assertEqual(self.ids(rows), ["hvd_1", "hvd_2"])
        self.assertEqual(self.ids(query_tgaz.search_name(self.conn, "Chang'an")), ["hvd_4"])

    def test_bad_coords_flag_and_filter(self):
        rows = query_tgaz.search_name(self.conn, "苏州", year=1000)
        flags = {r["sys_id"]: r["bad_coords"] for r in rows}
        self.assertEqual(flags, {"hvd_1": 0, "hvd_2": 1})
        rows = query_tgaz.search_name(self.conn, "苏州", year=1000, good_coords=True)
        self.assertEqual(self.ids(rows), ["hvd_1"])

    def test_parent_is_the_one_in_the_year_asked(self):
        rows = query_tgaz.search_name(self.conn, "苏州府", year=1600)
        self.assertEqual(rows[0]["parent_sys_id"], "hvd_6")
        self.assertEqual(rows[0]["parent_vn"], "浙江布政使司")
        # Without a year, the stored (earliest) parent is kept.
        rows = query_tgaz.search_name(self.conn, "苏州府")
        self.assertEqual(rows[0]["parent_vn"], "江南行省")

    def test_children_come_from_part_of(self):
        self.assertEqual(self.ids(query_tgaz.search_parent(self.conn, "hvd_6", 1600)), ["hvd_3"])
        self.assertEqual(self.ids(query_tgaz.search_parent(self.conn, "hvd_5", 1600)), [])
        self.assertEqual(self.ids(query_tgaz.search_parent(self.conn, "hvd_5")), ["hvd_3"])

    def test_fts_keeps_year_and_feature_type(self):
        # Matches hvd_5 by its own name, and hvd_1 and hvd_3 by their parent name.
        self.assertEqual(len(query_tgaz.search_fts(self.conn, "Jiangnan")), 3)
        self.assertEqual(self.ids(query_tgaz.search_fts(self.conn, "Jiangnan", year=1500)), ["hvd_3"])
        self.assertEqual(query_tgaz.search_fts(self.conn, "Jiangnan", year=1500, feature_type="zhou"), [])

    def test_cli_fallback_keeps_filters_and_says_so(self):
        # "zhou Su" is no name prefix, so the CLI falls back to full-text search.
        cp = self.cli("zhou Su", "--format", "json")
        self.assertIn("full-text search", cp.stderr)
        self.assertEqual(len(json.loads(cp.stdout)), 2)
        cp = self.cli("zhou Su", "--year", "1000", "--good-coords", "--format", "json")
        self.assertEqual(cp.returncode, 0, cp.stderr)
        self.assertEqual([r["sys_id"] for r in json.loads(cp.stdout)], ["hvd_1"])
        cp = self.cli("zhou Su", "--year", "1500", "--format", "json")
        self.assertIn("No results", cp.stdout)


class DbFileCheckTest(unittest.TestCase):
    def run_with(self, content):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tgaz.db"
            path.write_bytes(content)
            return subprocess.run([sys.executable, str(SCRIPT), "--db", str(path), "北京"],
                                  text=True, capture_output=True)

    def test_lfs_pointer_gives_clear_message(self):
        pointer = (b"version https://git-lfs.github.com/spec/v1\n"
                   b"oid sha256:f01afa80f65a470cfa6ebd557408e17b6dd5b9f45a9271a39c53d9735bf4ffc4\n"
                   b"size 238755840\n")
        cp = self.run_with(pointer)
        self.assertNotEqual(cp.returncode, 0)
        self.assertIn("Git LFS pointer", cp.stderr)
        self.assertIn("git lfs pull", cp.stderr)

    def test_other_non_database_file(self):
        cp = self.run_with(b"hello")
        self.assertNotEqual(cp.returncode, 0)
        self.assertIn("not a SQLite database", cp.stderr)


if __name__ == "__main__":
    unittest.main()
