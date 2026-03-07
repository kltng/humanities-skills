"""
CJK Calendar Converter — standalone local tool.

Converts between Chinese/Japanese/Korean/Vietnamese lunisolar calendars
and Gregorian/Julian calendars using Julian Day Number (JDN) as a universal pivot.

Requires: Python 3.10+, SQLite database (calendar.db).
Zero external dependencies — stdlib only.

Usage:
    python3 calendar_converter.py setup                       # Download database
    python3 calendar_converter.py convert "崇禎三年四月初三"    # CJK → Gregorian
    python3 calendar_converter.py jdn 2299161                 # JDN → all calendars
    python3 calendar_converter.py gregorian 1644 3 19         # Gregorian → JDN + CJK
    python3 calendar_converter.py eras --name 康熙             # Search era metadata
    python3 calendar_converter.py eras --dynasty 明 --country chinese
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import urllib.request
import urllib.error
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Database location & download
# ---------------------------------------------------------------------------

DB_DIR = Path(__file__).resolve().parent
DB_PATH = DB_DIR / "calendar.db"

# GitHub raw URL for the database file
DB_DOWNLOAD_URL = (
    "https://github.com/kltng/calendar_converter/raw/main/data/calendar.db"
)


def download_db(dest: Path | None = None) -> Path:
    """Download calendar.db from GitHub if not already present."""
    dest = dest or DB_PATH
    if dest.exists():
        print(f"Database already exists: {dest}")
        return dest

    print(f"Downloading calendar.db (~14 MB) ...")
    req = urllib.request.Request(
        DB_DOWNLOAD_URL,
        headers={"User-Agent": "cjk-calendar-skill/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
        print(f"Downloaded to {dest}")
    except urllib.error.URLError as e:
        print(f"Download failed: {e}", file=sys.stderr)
        print("Manual download: visit the GitHub repo and copy data/calendar.db", file=sys.stderr)
        sys.exit(1)
    return dest


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Get a SQLite connection with row factory."""
    path = db_path or DB_PATH
    if not path.exists():
        print(f"Database not found: {path}", file=sys.stderr)
        print("Run: python3 calendar_converter.py setup", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Data classes (replacing Pydantic models)
# ---------------------------------------------------------------------------

@dataclass
class EraInfo:
    era_name: str
    era_id: int
    emperor_name: str | None = None
    dynasty_name: str | None = None
    country: str = ""
    year_in_era: int = 0
    month: int = 0
    month_name: str = ""
    is_leap_month: bool = False
    day: int = 0


@dataclass
class GanzhiInfo:
    year: str = ""
    month: str = ""
    day: str = ""


@dataclass
class DateConversion:
    jdn: int = 0
    gregorian: str = ""
    julian: str | None = None
    ganzhi: GanzhiInfo = field(default_factory=GanzhiInfo)
    cjk_dates: list[EraInfo] = field(default_factory=list)


@dataclass
class EraMetadata:
    era_id: int = 0
    era_name: str = ""
    emperor_name: str | None = None
    dynasty_name: str | None = None
    country: str = ""
    start_jdn: int | None = None
    end_jdn: int | None = None
    start_gregorian: str | None = None
    end_gregorian: str | None = None


@dataclass
class ParsedDate:
    era: str = ""
    year: int | None = None
    month: int | None = None
    day: int | None = None
    is_leap_month: bool = False
    country_hint: str | None = None
    ganzhi_year: str | None = None
    ganzhi_month: str | None = None
    ganzhi_day: str | None = None


# ---------------------------------------------------------------------------
# Parser — CJK date string → ParsedDate
# ---------------------------------------------------------------------------

_DIGITS = {
    "〇": 0, "零": 0,
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9,
    "十": 10, "廿": 20, "卅": 30,
    "元": 1, "正": 1,
}

_STEMS = "甲乙丙丁戊己庚辛壬癸"
_BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
_GANZHI_CHAR = f"[{_STEMS}][{_BRANCHES}]"

_JP_ERA_SHORT = {
    "M": "明治", "T": "大正", "S": "昭和", "H": "平成", "R": "令和",
}


def _parse_chinese_number(s: str) -> int | None:
    """Parse a Chinese numeral string to int."""
    if not s:
        return None
    if len(s) == 1 and s in _DIGITS:
        return _DIGITS[s]
    if s.startswith("初"):
        rest = s[1:]
        if rest and rest in _DIGITS:
            return _DIGITS[rest]
        return None
    if s == "十":
        return 10
    if len(s) == 2 and s[0] == "十":
        ones = _DIGITS.get(s[1])
        if ones is not None:
            return 10 + ones
    if len(s) == 2 and s[1] == "十":
        tens = _DIGITS.get(s[0])
        if tens is not None:
            return tens * 10
    if len(s) == 3 and s[1] == "十":
        tens = _DIGITS.get(s[0])
        ones = _DIGITS.get(s[2])
        if tens is not None and ones is not None:
            return tens * 10 + ones
    if len(s) == 2 and s[0] in ("廿", "卅"):
        base = _DIGITS[s[0]]
        ones = _DIGITS.get(s[1], 0)
        return base + ones
    if "十" in s:
        parts = s.split("十")
        if len(parts) == 2:
            tens = _DIGITS.get(parts[0], 0) if parts[0] else 1
            ones = _DIGITS.get(parts[1], 0) if parts[1] else 0
            return tens * 10 + ones
    return None


_CJK_PATTERN = re.compile(
    r"^"
    r"(?P<era>[^\d\s年]{1,10}?)"
    r"(?P<year>[元一二三四五六七八九十百廿卅\d]+)年"
    r"(?:"
    r"(?P<leap>閏)?"
    r"(?P<month>[正一二三四五六七八九十廿]+)月"
    r"(?:"
    r"(?P<day>[初一二三四五六七八九十廿卅]+)"
    r"日?"
    r")?"
    r")?"
    r"$"
)

_GZ_YEAR_PATTERN = re.compile(
    r"^"
    r"(?P<era>.+?)"
    rf"(?P<gz_year>{_GANZHI_CHAR})年"
    r"(?:"
    r"(?P<leap>閏)?"
    r"(?:"
    rf"(?P<gz_month>{_GANZHI_CHAR})"
    r"|"
    r"(?P<num_month>[正一二三四五六七八九十廿]+)"
    r")月"
    r"(?:"
    rf"(?P<gz_day>{_GANZHI_CHAR})"
    r"|"
    r"(?P<num_day>[初一二三四五六七八九十廿卅]+)"
    r")?"
    r"日?"
    r")?"
    r"$"
)

_JP_SHORT_PATTERN = re.compile(
    r"^(?P<era>[MTSHRLW])(?P<year>\d{1,4})"
    r"(?:\.(?P<month>\d{1,2})"
    r"(?:\.(?P<day>\d{1,2}))?"
    r")?$"
)


def parse_cjk_date(text: str) -> ParsedDate | None:
    """Parse a CJK date string into structured components."""
    text = text.strip()
    if not text:
        return None

    m = _JP_SHORT_PATTERN.match(text)
    if m:
        era_char = m.group("era")
        era = _JP_ERA_SHORT.get(era_char)
        if era is None:
            return None
        year = int(m.group("year"))
        month = int(m.group("month")) if m.group("month") else None
        day = int(m.group("day")) if m.group("day") else None
        return ParsedDate(era=era, year=year, month=month, day=day, country_hint="japanese")

    m = _GZ_YEAR_PATTERN.match(text)
    if m:
        era = m.group("era")
        gz_year = m.group("gz_year")
        is_leap = m.group("leap") is not None
        gz_month = m.group("gz_month")
        num_month_str = m.group("num_month")
        gz_day = m.group("gz_day")
        num_day_str = m.group("num_day")
        month: int | None = None
        if num_month_str:
            month = _parse_chinese_number(num_month_str)
        day: int | None = None
        if num_day_str:
            day = _parse_chinese_number(num_day_str)
        return ParsedDate(
            era=era, year=None, month=month, day=day,
            is_leap_month=is_leap, ganzhi_year=gz_year,
            ganzhi_month=gz_month, ganzhi_day=gz_day,
        )

    m = _CJK_PATTERN.match(text)
    if m:
        era = m.group("era")
        year_str = m.group("year")
        is_leap = m.group("leap") is not None
        month_str = m.group("month")
        day_str = m.group("day")
        if year_str == "元":
            year = 1
        elif year_str.isascii() and year_str.isdigit():
            year = int(year_str)
        else:
            year = _parse_chinese_number(year_str)
            if year is None:
                return None
        month: int | None = None
        if month_str:
            month = _parse_chinese_number(month_str)
        day: int | None = None
        if day_str:
            day = _parse_chinese_number(day_str)
        return ParsedDate(era=era, year=year, month=month, day=day, is_leap_month=is_leap)

    return None


# ---------------------------------------------------------------------------
# Converter — JDN ↔ Gregorian/Julian + ganzhi
# ---------------------------------------------------------------------------

HEAVENLY_STEMS = "甲乙丙丁戊己庚辛壬癸"
EARTHLY_BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


def _ganzhi_from_index(idx: int) -> str:
    idx = idx % 60
    return HEAVENLY_STEMS[idx % 10] + EARTHLY_BRANCHES[idx % 12]


def jdn_to_ganzhi_day(jdn: int) -> str:
    """Compute the sexagenary day designation for a given JDN."""
    return _ganzhi_from_index((jdn + 49) % 60)


def month_ganzhi(year_ganzhi: str, lunar_month: int) -> str:
    """Compute the sexagenary month from year ganzhi and lunar month number."""
    if not year_ganzhi or len(year_ganzhi) < 1:
        return ""
    year_stem_idx = HEAVENLY_STEMS.find(year_ganzhi[0])
    if year_stem_idx < 0:
        return ""
    base_stems = [2, 4, 6, 8, 0]
    month1_stem = base_stems[year_stem_idx % 5]
    month_stem = (month1_stem + (lunar_month - 1)) % 10
    month_branch = (lunar_month + 1) % 12
    return HEAVENLY_STEMS[month_stem] + EARTHLY_BRANCHES[month_branch]


def jdn_to_gregorian(jdn: int) -> tuple[int, int, int]:
    """Convert JDN to proleptic Gregorian calendar date (year, month, day)."""
    a = jdn + 32044
    b = (4 * a + 3) // 146097
    c = a - (146097 * b) // 4
    d = (4 * c + 3) // 1461
    e = c - (1461 * d) // 4
    m = (5 * e + 2) // 153
    day = e - (153 * m + 2) // 5 + 1
    month = m + 3 - 12 * (m // 10)
    year = 100 * b + d - 4800 + m // 10
    return (year, month, day)


def gregorian_to_jdn(year: int, month: int, day: int) -> int:
    """Convert Gregorian date to JDN."""
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    return day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045


def jdn_to_julian(jdn: int) -> tuple[int, int, int]:
    """Convert JDN to Julian calendar date (year, month, day)."""
    c = jdn + 32082
    d = (4 * c + 3) // 1461
    e = c - (1461 * d) // 4
    m = (5 * e + 2) // 153
    day = e - (153 * m + 2) // 5 + 1
    month = m + 3 - 12 * (m // 10)
    year = d - 4800 + m // 10
    return (year, month, day)


def format_date(year: int, month: int, day: int) -> str:
    """Format a date as ISO 8601 string with astronomical year numbering."""
    if year < 0:
        return f"-{abs(year):04d}-{month:02d}-{day:02d}"
    return f"{year:04d}-{month:02d}-{day:02d}"


# ---------------------------------------------------------------------------
# Database queries
# ---------------------------------------------------------------------------

def find_eras_by_name(conn: sqlite3.Connection, era_name: str, country: str | None = None) -> list[sqlite3.Row]:
    sql = "SELECT es.* FROM era_summary es WHERE es.era_name = ?"
    params: list[str] = [era_name]
    if country:
        sql += " AND es.country = ?"
        params.append(country)
    sql += " ORDER BY es.start_jdn"
    return conn.execute(sql, params).fetchall()


def find_month(conn: sqlite3.Connection, era_id: int, year_in_era: int,
               month: int | None = None, is_leap_month: bool = False) -> list[sqlite3.Row]:
    sql = "SELECT * FROM month WHERE era_id = ? AND year = ?"
    params: list = [era_id, year_in_era]
    if month is not None:
        sql += " AND month = ? AND leap_month = ?"
        params.append(month)
        params.append(1 if is_leap_month else 0)
    sql += " ORDER BY first_jdn"
    return conn.execute(sql, params).fetchall()


def find_years_by_ganzhi(conn: sqlite3.Connection, era_id: int, ganzhi: str) -> list[sqlite3.Row]:
    sql = "SELECT DISTINCT year, ganzhi FROM month WHERE era_id = ? AND ganzhi = ? ORDER BY year"
    return conn.execute(sql, (era_id, ganzhi)).fetchall()


def find_date_by_jdn(conn: sqlite3.Connection, jdn: int) -> list[sqlite3.Row]:
    sql = """
        SELECT m.*, es.era_name, es.emperor_name, es.dynasty_name, es.country
        FROM month m
        JOIN era_summary es ON es.era_id = m.era_id
        WHERE m.first_jdn <= ? AND m.last_jdn >= ?
        ORDER BY es.country, m.first_jdn
    """
    return conn.execute(sql, (jdn, jdn)).fetchall()


def get_all_eras(conn: sqlite3.Connection, country: str | None = None,
                 dynasty_name: str | None = None) -> list[sqlite3.Row]:
    sql = "SELECT * FROM era_summary WHERE 1=1"
    params: list[str] = []
    if country:
        sql += " AND country = ?"
        params.append(country)
    if dynasty_name:
        sql += " AND dynasty_name = ?"
        params.append(dynasty_name)
    sql += " ORDER BY start_jdn"
    return conn.execute(sql, params).fetchall()


# ---------------------------------------------------------------------------
# High-level conversion functions
# ---------------------------------------------------------------------------

def _resolve_ganzhi_month(year_ganzhi: str, target_gz_month: str) -> int | None:
    for m in range(1, 13):
        if month_ganzhi(year_ganzhi, m) == target_gz_month:
            return m
    return None


def _resolve_ganzhi_day(first_jdn: int, last_jdn: int, start_from: int, target_gz_day: str) -> int | None:
    for jdn in range(first_jdn, last_jdn + 1):
        if jdn_to_ganzhi_day(jdn) == target_gz_day:
            return jdn - first_jdn + start_from
    return None


def convert_cjk_to_jdn(conn: sqlite3.Connection, parsed: ParsedDate) -> list[tuple[int, EraInfo]]:
    """Convert a parsed CJK date to JDN(s). Multiple results when era name is ambiguous."""
    eras = find_eras_by_name(conn, parsed.era, parsed.country_hint)
    if not eras:
        return []

    results: list[tuple[int, EraInfo]] = []

    for era_row in eras:
        era_id = era_row["era_id"]

        if parsed.ganzhi_year and parsed.year is None:
            year_rows = find_years_by_ganzhi(conn, era_id, parsed.ganzhi_year)
            years = [r["year"] for r in year_rows]
        elif parsed.year is not None:
            years = [parsed.year]
        else:
            continue

        for year in years:
            month_val = parsed.month
            is_leap = parsed.is_leap_month
            if parsed.ganzhi_month and month_val is None:
                year_gz = parsed.ganzhi_year
                if not year_gz:
                    continue
                month_val = _resolve_ganzhi_month(year_gz, parsed.ganzhi_month)
                if month_val is None:
                    continue
                is_leap = False

            months = find_month(conn, era_id, year, month_val, is_leap)

            for month_row in months:
                day = parsed.day
                if parsed.ganzhi_day and day is None:
                    day = _resolve_ganzhi_day(
                        month_row["first_jdn"], month_row["last_jdn"],
                        month_row["start_from"], parsed.ganzhi_day,
                    )
                    if day is None:
                        continue

                if day is not None:
                    day_offset = day - month_row["start_from"]
                    jdn = month_row["first_jdn"] + day_offset
                    if jdn > month_row["last_jdn"]:
                        continue
                else:
                    jdn = month_row["first_jdn"]

                day_in_month = day if day is not None else month_row["start_from"]

                era_info = EraInfo(
                    era_name=era_row["era_name"],
                    era_id=era_id,
                    emperor_name=era_row["emperor_name"],
                    dynasty_name=era_row["dynasty_name"],
                    country=era_row["country"],
                    year_in_era=year,
                    month=month_row["month"],
                    month_name=month_row["month_name"],
                    is_leap_month=bool(month_row["leap_month"]),
                    day=day_in_month,
                )
                results.append((jdn, era_info))

    return results


def convert_jdn(conn: sqlite3.Connection, jdn: int) -> DateConversion:
    """Convert a JDN to all calendar representations."""
    g_year, g_month, g_day = jdn_to_gregorian(jdn)
    gregorian = format_date(g_year, g_month, g_day)

    julian_str: str | None = None
    if jdn < 2299161:  # Gregorian reform: Oct 15, 1582
        j_year, j_month, j_day = jdn_to_julian(jdn)
        julian_str = format_date(j_year, j_month, j_day)

    ganzhi_day = jdn_to_ganzhi_day(jdn)
    ganzhi_year = ""
    ganzhi_month_str = ""

    month_rows = find_date_by_jdn(conn, jdn)
    cjk_dates: list[EraInfo] = []

    for row in month_rows:
        day_in_month = jdn - row["first_jdn"] + row["start_from"]
        cjk_dates.append(EraInfo(
            era_name=row["era_name"],
            era_id=row["era_id"],
            emperor_name=row["emperor_name"],
            dynasty_name=row["dynasty_name"],
            country=row["country"],
            year_in_era=row["year"],
            month=row["month"],
            month_name=row["month_name"],
            is_leap_month=bool(row["leap_month"]),
            day=day_in_month,
        ))
        if not ganzhi_year and row["ganzhi"]:
            ganzhi_year = row["ganzhi"]
            if not row["leap_month"]:
                ganzhi_month_str = month_ganzhi(ganzhi_year, row["month"])

    return DateConversion(
        jdn=jdn,
        gregorian=gregorian,
        julian=julian_str,
        ganzhi=GanzhiInfo(year=ganzhi_year, month=ganzhi_month_str, day=ganzhi_day),
        cjk_dates=cjk_dates,
    )


def get_era_metadata(conn: sqlite3.Connection, era_name: str | None = None,
                     dynasty_name: str | None = None, country: str | None = None) -> list[EraMetadata]:
    """Get metadata for eras matching search criteria."""
    if era_name:
        rows = find_eras_by_name(conn, era_name, country)
    else:
        rows = get_all_eras(conn, country, dynasty_name)

    results = []
    for row in rows:
        start_greg = None
        end_greg = None
        if row["start_jdn"]:
            y, m, d = jdn_to_gregorian(row["start_jdn"])
            start_greg = format_date(y, m, d)
        if row["end_jdn"]:
            y, m, d = jdn_to_gregorian(row["end_jdn"])
            end_greg = format_date(y, m, d)
        results.append(EraMetadata(
            era_id=row["era_id"],
            era_name=row["era_name"],
            emperor_name=row["emperor_name"],
            dynasty_name=row["dynasty_name"],
            country=row["country"],
            start_jdn=row["start_jdn"],
            end_jdn=row["end_jdn"],
            start_gregorian=start_greg,
            end_gregorian=end_greg,
        ))
    return results


# ---------------------------------------------------------------------------
# JSON output helpers
# ---------------------------------------------------------------------------

def _to_dict(obj) -> dict:
    """Recursively convert dataclass to dict."""
    if hasattr(obj, "__dataclass_fields__"):
        d = {}
        for k, v in asdict(obj).items():
            d[k] = v
        return d
    return obj


def _print_json(data):
    """Pretty-print JSON output."""
    if isinstance(data, list):
        print(json.dumps([_to_dict(d) for d in data], ensure_ascii=False, indent=2))
    else:
        print(json.dumps(_to_dict(data), ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _usage():
    print(__doc__.strip())
    sys.exit(1)


def main():
    if len(sys.argv) < 2:
        _usage()

    cmd = sys.argv[1]

    if cmd == "setup":
        download_db()
        return

    conn = get_connection()

    if cmd == "convert":
        if len(sys.argv) < 3:
            print("Usage: calendar_converter.py convert <CJK date string>", file=sys.stderr)
            sys.exit(1)
        text = sys.argv[2]
        parsed = parse_cjk_date(text)
        if parsed is None:
            print(f"Could not parse: {text}", file=sys.stderr)
            sys.exit(1)
        results = convert_cjk_to_jdn(conn, parsed)
        if not results:
            print(f"No matching dates found for: {text}", file=sys.stderr)
            sys.exit(1)
        output = []
        for jdn, era_info in results:
            conversion = convert_jdn(conn, jdn)
            output.append({
                "input_era": _to_dict(era_info),
                "jdn": jdn,
                "gregorian": conversion.gregorian,
                "julian": conversion.julian,
                "ganzhi": _to_dict(conversion.ganzhi),
                "all_cjk_dates": [_to_dict(c) for c in conversion.cjk_dates],
            })
        print(json.dumps(output, ensure_ascii=False, indent=2))

    elif cmd == "jdn":
        if len(sys.argv) < 3:
            print("Usage: calendar_converter.py jdn <JDN>", file=sys.stderr)
            sys.exit(1)
        jdn = int(sys.argv[2])
        result = convert_jdn(conn, jdn)
        _print_json(result)

    elif cmd == "gregorian":
        if len(sys.argv) < 5:
            print("Usage: calendar_converter.py gregorian <year> <month> <day>", file=sys.stderr)
            sys.exit(1)
        year, month, day = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
        jdn = gregorian_to_jdn(year, month, day)
        result = convert_jdn(conn, jdn)
        _print_json(result)

    elif cmd == "eras":
        era_name = None
        dynasty = None
        country = None
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == "--name" and i + 1 < len(sys.argv):
                era_name = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--dynasty" and i + 1 < len(sys.argv):
                dynasty = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--country" and i + 1 < len(sys.argv):
                country = sys.argv[i + 1]
                i += 2
            else:
                print(f"Unknown option: {sys.argv[i]}", file=sys.stderr)
                sys.exit(1)
        results = get_era_metadata(conn, era_name, dynasty, country)
        _print_json(results)

    else:
        _usage()

    conn.close()


if __name__ == "__main__":
    main()
