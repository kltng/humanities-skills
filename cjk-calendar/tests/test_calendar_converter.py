"""Offline tests for calendar_converter.py, using a tiny fixture database.

The real calendar.db is not in git, so these tests build a small SQLite file
with the same schema and a few real rows copied from it.
"""

import io
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import calendar_converter as cc  # noqa: E402


SCHEMA = """
CREATE TABLE dynasty (id INTEGER PRIMARY KEY, type TEXT NOT NULL);
CREATE TABLE dynasty_name (dynasty_id INTEGER, name TEXT, ranking INTEGER DEFAULT 0,
                           language_id INTEGER DEFAULT 0);
CREATE TABLE emperor (id INTEGER PRIMARY KEY, dynasty_id INTEGER);
CREATE TABLE emperor_name (emperor_id INTEGER, name TEXT, ranking INTEGER DEFAULT 0,
                           language_id INTEGER DEFAULT 0);
CREATE TABLE era (id INTEGER PRIMARY KEY, emperor_id INTEGER);
CREATE TABLE era_name (era_id INTEGER, name TEXT, ranking INTEGER DEFAULT 0,
                       language_id INTEGER DEFAULT 0);
CREATE TABLE month (id INTEGER PRIMARY KEY, year INTEGER, month INTEGER, month_name TEXT,
                    leap_month INTEGER DEFAULT 0, era_id INTEGER, first_jdn INTEGER,
                    last_jdn INTEGER, ganzhi TEXT DEFAULT '', start_from INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'S', eclipse INTEGER DEFAULT 0);
CREATE VIEW era_summary AS
    SELECT e.id AS era_id, en.name AS era_name, emp.id AS emperor_id,
           empn.name AS emperor_name, d.id AS dynasty_id, dn.name AS dynasty_name,
           d.type AS country, MIN(m.first_jdn) AS start_jdn, MAX(m.last_jdn) AS end_jdn
    FROM era e
    JOIN era_name en ON en.era_id = e.id AND en.ranking = 0
    JOIN emperor emp ON emp.id = e.emperor_id
    LEFT JOIN emperor_name empn ON empn.emperor_id = emp.id AND empn.ranking = 0
    JOIN dynasty d ON d.id = emp.dynasty_id
    LEFT JOIN dynasty_name dn ON dn.dynasty_id = d.id AND dn.ranking = 0
    LEFT JOIN month m ON m.era_id = e.id
    GROUP BY e.id;
"""

# era_id, era name, dynasty, emperor, country
ERAS = [
    (647, "萬曆", "明", "神宗", "chinese"),
    (650, "崇禎", "明", "思宗", "chinese"),
    (664, "道光", "清", "宣宗", "chinese"),
    (1191, "天保", "江戸時代", "仁孝天皇", "japanese"),
]

# era_id, year, month, month_name, leap, first_jdn, last_jdn, ganzhi, start_from, status
MONTHS = [
    (647, 10, 1, "正", 0, 2298907, 2298936, "壬午", 1, "S"),
    (650, 17, 3, "三", 0, 2321616, 2321634, "甲申", 1, "S"),
    (650, 17, 3, "三", 0, 2321635, 2321644, "甲申", 20, "P"),
    (650, 205, 10, "十", 0, 2390510, 2390539, "壬辰", 1, "P"),
    (664, 12, 9, "閏九", 1, 2390481, 2390509, "壬辰", 1, "S"),
    (664, 12, 10, "十", 0, 2390510, 2390539, "壬辰", 1, "S"),
    (1191, 3, 10, "十", 0, 2390481, 2390509, "壬辰", 1, "S"),
    (1191, 3, 11, "十一", 0, 2390510, 2390539, "壬辰", 1, "S"),
]


def build_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    for i, (era_id, name, dynasty, emperor, country) in enumerate(ERAS, start=1):
        conn.execute("INSERT INTO dynasty VALUES (?, ?)", (i, country))
        conn.execute("INSERT INTO dynasty_name (dynasty_id, name) VALUES (?, ?)", (i, dynasty))
        conn.execute("INSERT INTO emperor VALUES (?, ?)", (i, i))
        conn.execute("INSERT INTO emperor_name (emperor_id, name) VALUES (?, ?)", (i, emperor))
        conn.execute("INSERT INTO era VALUES (?, ?)", (era_id, i))
        conn.execute("INSERT INTO era_name (era_id, name) VALUES (?, ?)", (era_id, name))
    conn.executemany(
        "INSERT INTO month (era_id, year, month, month_name, leap_month, first_jdn, last_jdn,"
        " ganzhi, start_from, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", MONTHS)
    conn.commit()
    conn.close()


class FixtureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = Path(cls.tmp.name) / "calendar.db"
        build_db(cls.db)
        cls.conn = cc.get_connection(cls.db)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        cls.tmp.cleanup()

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        code = 0
        with mock.patch.object(sys, "argv", ["calendar_converter.py", *args]), \
                redirect_stdout(out), redirect_stderr(err):
            try:
                cc.main()
            except SystemExit as e:
                code = e.code
        return code, out.getvalue(), err.getvalue()


class MonthGanzhiTest(FixtureTest):
    """Issue #20: month 干支 must come from the calendar the user entered."""

    def test_japanese_month_ganzhi(self):
        parsed = cc.parse_cjk_date("天保三年十一月初一")
        [(jdn, era)] = cc.convert_cjk_to_jdn(self.conn, parsed)
        conv = cc.convert_jdn(self.conn, jdn, era_id=era.era_id)
        self.assertEqual((conv.ganzhi.year, conv.ganzhi.month), ("壬辰", "壬子"))
        # Without era_id the first (Chinese) row is used: 道光十二年十月 = 辛亥
        self.assertEqual(cc.convert_jdn(self.conn, jdn).ganzhi.month, "辛亥")

    def test_japanese_month_over_chinese_leap_month(self):
        parsed = cc.parse_cjk_date("天保三年十月初一")
        [(jdn, era)] = cc.convert_cjk_to_jdn(self.conn, parsed)
        self.assertEqual(cc.convert_jdn(self.conn, jdn, era_id=era.era_id).ganzhi.month, "辛亥")
        self.assertEqual(cc.convert_jdn(self.conn, jdn).ganzhi.month, "")  # Chinese 閏九月

    def test_country_filter_on_jdn(self):
        conv = cc.convert_jdn(self.conn, 2390510, country="japanese")
        self.assertEqual([d.era_name for d in conv.cjk_dates], ["天保"])
        self.assertEqual(conv.ganzhi.month, "壬子")


class SimplifiedEraTest(FixtureTest):
    def test_variants(self):
        self.assertIn("萬曆", cc.traditional_variants("万历"))
        self.assertIn("萬歷", cc.traditional_variants("万历"))
        self.assertEqual(cc.traditional_variants("萬曆"), [])

    def test_simplified_convert(self):
        parsed = cc.parse_cjk_date("万历10年1月1日")
        [(jdn, era)] = cc.convert_cjk_to_jdn(self.conn, parsed)
        self.assertEqual(era.era_name, "萬曆")
        self.assertEqual(cc.convert_jdn(self.conn, jdn).gregorian, "1582-02-03")

    def test_cli_note(self):
        code, out, err = self.run_cli("convert", "万历10年1月1日", "--db", str(self.db))
        self.assertEqual(code, 0)
        self.assertIn("萬曆", err)
        self.assertEqual(json.loads(out)[0]["gregorian"], "1582-02-03")


class ContinuedUseTest(FixtureTest):
    def test_chongzhen_after_fall(self):
        last = cc.convert_cjk_to_jdn(self.conn, cc.parse_cjk_date("崇禎十七年三月十九日"))
        after = cc.convert_cjk_to_jdn(self.conn, cc.parse_cjk_date("崇禎十七年三月二十日"))
        self.assertEqual(cc.convert_jdn(self.conn, last[0][0]).gregorian, "1644-04-25")
        self.assertFalse(last[0][1].continued_use)
        self.assertTrue(after[0][1].continued_use)

    def test_cli_note_for_late_chongzhen(self):
        code, out, _ = self.run_cli("convert", "崇禎205年10月1日", "--db", str(self.db))
        self.assertEqual(code, 0)
        self.assertIn("Joseon", json.loads(out)[0]["note"])


class CliTest(FixtureTest):
    def test_country_filter(self):
        code, out, _ = self.run_cli("convert", "天保三年十一月", "--country", "japanese",
                                    "--db", str(self.db))
        self.assertEqual(code, 0)
        [item] = json.loads(out)
        self.assertEqual(item["input_era"]["country"], "japanese")
        self.assertEqual(item["ganzhi"]["month"], "壬子")

    def test_country_filter_no_match(self):
        code, _, err = self.run_cli("convert", "天保三年", "--country", "korean",
                                    "--db", str(self.db))
        self.assertEqual(code, 1)
        self.assertIn("without --country", err)

    def test_unknown_option_is_error(self):
        code, _, err = self.run_cli("convert", "天保三年", "--bogus", "x", "--db", str(self.db))
        self.assertEqual(code, 2)
        self.assertIn("--bogus", err)

    def test_extra_argument_is_error(self):
        code, _, _ = self.run_cli("convert", "天保三年", "extra", "--db", str(self.db))
        self.assertEqual(code, 2)

    def test_unknown_country_is_error(self):
        with self.assertRaises(ValueError):
            cc.parse_cli(["convert", "天保三年", "--country", "mars"])

    def test_parse_cli(self):
        self.assertEqual(
            cc.parse_cli(["gregorian", "-100", "3", "1", "--country=Chinese", "--db", "x.db"]),
            ("gregorian", ["-100", "3", "1"], {"--country": "chinese", "--db": "x.db"}))

    def test_missing_db(self):
        code, _, err = self.run_cli("jdn", "2390510", "--db", str(self.db) + ".missing")
        self.assertEqual(code, 1)
        self.assertIn("Database not found", err)

    def test_eras_simplified(self):
        code, out, _ = self.run_cli("eras", "--name", "万历", "--db", str(self.db))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)[0]["era_name"], "萬曆")


if __name__ == "__main__":
    unittest.main()
