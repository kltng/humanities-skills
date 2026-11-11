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
    # rows for the database corrections (issues #28 and #32)
    (695, "始建", "西漢", "成帝", "chinese"),        # wrong in the database: it is 建始
    (710, "（後元）", "西漢", "武帝", "chinese"),
    (720, "建元", "西漢", "武帝", "chinese"),
    (724, "（無年號）", "西漢", "文帝", "chinese"),
    (1490, "（王年）", "大朝鮮國", "光海君", "korean"),
    (1491, "（王年）", "大朝鮮國", "仁祖", "korean"),
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
    (695, 3, 1, "正", 0, 1710510, 1710539, "辛卯", 1, "S"),
    (710, 1, 1, "正", 0, 1689307, 1689336, "癸巳", 1, "S"),
    (720, 6, 6, "六", 0, 1672298, 1672327, "丙午", 1, "S"),
    (724, 7, 10, "十", 0, 1658183, 1658211, "戊辰", 1, "S"),
    # 光海君 was deposed in 15年三月; the database keeps him to the end of the year
    (1490, 15, 3, "三", 0, 2313938, 2313950, "癸亥", 1, "S"),
    (1490, 15, 3, "三", 0, 2313951, 2313966, "癸亥", 14, "P"),
    (1490, 15, 4, "四", 0, 2313967, 2313996, "癸亥", 1, "P"),
    (1491, 1, 1, "正", 0, 2314263, 2314291, "甲子", 1, "S"),
    (1491, 21, 3, "三", 0, 2321616, 2321644, "甲申", 1, "S"),
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



class DatabaseCorrectionTest(FixtureTest):
    """Issues #28 and #32: errors in calendar.db that the converter corrects."""

    def convert(self, text, country=None):
        return cc.convert_cjk_to_jdn(self.conn, cc.parse_cjk_date(text), country)

    def test_jianshi_is_found_under_its_right_name(self):
        results = self.convert("建始三年正月")
        self.assertEqual([(j, e.era_name, e.emperor_name) for j, e in results],
                         [(1710510, "建始", "成帝")])
        self.assertEqual(self.convert("始建三年正月"), [])

    def test_bracketed_era_name_is_found_without_brackets(self):
        results = self.convert("後元元年正月")
        self.assertEqual([(j, e.emperor_name) for j, e in results], [(1689307, "武帝")])

    def test_numeric_year_with_ganzhi_day(self):
        parsed = cc.parse_cjk_date("建元六年六月丁酉")
        self.assertEqual((parsed.year, parsed.month, parsed.day, parsed.ganzhi_day),
                         (6, 6, None, "丁酉"))
        (jdn, era), = self.convert("建元六年六月丁酉")
        self.assertEqual((era.day, cc.jdn_to_ganzhi_day(jdn)), (7, "丁酉"))
        # a 干支 day that does not fall in the month gives no result
        self.assertEqual(self.convert("建元六年六月辛卯")[0][1].day, 1)
        self.assertEqual(cc.parse_cjk_date("建元六年六月初七日").day, 7)

    def test_reign_name_finds_years_without_an_era_name(self):
        (jdn, era), = self.convert("文帝七年十月")
        self.assertEqual((jdn, era.era_name, era.year_in_era), (1658183, "（無年號）", 7))

    def test_injo_years_count_from_the_accession_year(self):
        # 1644-04-25 is 仁祖 22년 3월 19일 in the Sillok (the database says 21)
        korean = cc.convert_jdn(self.conn, cc.gregorian_to_jdn(1644, 4, 25), country="korean").cjk_dates
        self.assertEqual([(e.emperor_name, e.year_in_era, e.month, e.day) for e in korean],
                         [("仁祖", 22, 3, 19)])
        (jdn, _), = self.convert("仁祖二十二年三月十九日", "korean")
        self.assertEqual(cc.jdn_to_gregorian(jdn), (1644, 4, 25))

    def test_accession_year_is_split_on_the_accession_day(self):
        def korean(y, m, d):
            dates = cc.convert_jdn(self.conn, cc.gregorian_to_jdn(y, m, d), country="korean").cjk_dates
            return [(e.emperor_name, e.year_in_era, e.month, e.day) for e in dates]

        self.assertEqual(korean(1623, 4, 11), [("光海君", 15, 3, 12)])
        self.assertEqual(korean(1623, 4, 12), [("仁祖", 1, 3, 13)])
        self.assertEqual(korean(1623, 5, 1), [("仁祖", 1, 4, 3)])
        self.assertEqual(self.convert("光海君十五年三月十三日"), [])

    def test_era_list_shows_the_corrected_start(self):
        injo, = cc.get_era_metadata(self.conn, era_name="仁祖")
        self.assertEqual(injo.start_gregorian, "1623-04-12")


class NoCorrectionNeededTest(unittest.TestCase):
    """A database that is already right must be left as it is."""

    def test_fixed_database_is_not_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "calendar.db"
            build_db(db)
            conn = sqlite3.connect(db)
            conn.execute("UPDATE era_name SET name = '建始' WHERE era_id = 695")
            # the new king already starts in the accession year
            conn.execute("UPDATE month SET era_id = 1491, year = 1, status = 'S' "
                         "WHERE era_id = 1490 AND status = 'P'")
            conn.execute("UPDATE month SET year = year + 1 WHERE era_id = 1491 AND first_jdn > 2314000")
            conn.commit()
            conn.close()
            conn = cc.get_connection(db)
            try:
                dates = cc.convert_jdn(conn, cc.gregorian_to_jdn(1644, 4, 25), country="korean").cjk_dates
                self.assertEqual([(e.emperor_name, e.year_in_era) for e in dates], [("仁祖", 22)])
                self.assertEqual(len(cc.find_eras_by_name(conn, "建始")), 1)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
