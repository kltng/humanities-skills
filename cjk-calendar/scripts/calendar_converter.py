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
    python3 calendar_converter.py gregorian 1644 4 25         # Gregorian → JDN + CJK
    python3 calendar_converter.py eras --name 康熙             # Search era metadata
    python3 calendar_converter.py eras --dynasty 明 --country chinese

Options:
    --country C   convert, jdn, gregorian, eras: keep only one calendar
                  (chinese, japanese, korean, vietnamese)
    --db PATH     any command: use this calendar.db instead of the one in scripts/
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
    # Download to a temporary file and rename at the end, so an interrupted
    # download never leaves a truncated calendar.db that `setup` then skips.
    tmp = dest.with_name(dest.name + ".part")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
        with open(tmp, "rb") as f:
            if f.read(16) != b"SQLite format 3\x00":
                raise OSError("downloaded file is not a SQLite database")
        os.replace(tmp, dest)
        print(f"Downloaded to {dest}")
    except (urllib.error.URLError, OSError) as e:
        tmp.unlink(missing_ok=True)
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
    # Read-only: the converter never writes, and a read-only file (e.g. a
    # shared or installed copy) must still open.
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
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
    # True when the database marks this month as use of the era after its
    # official end (month.status = 'P'), e.g. 崇禎 after 1644-04-25, kept by
    # Ming loyalists and in Joseon Korea.
    continued_use: bool = False


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
    # 元 only stands alone (元年). Otherwise eras ending in 元 (開元, 至元,
    # 永元, 建武中元 ...) would lose that character to the year number.
    r"(?P<year>元|[一二三四五六七八九十百廿卅〇零\d]+)年"
    r"(?:"
    r"(?P<leap>閏)?"
    r"(?P<month>[正一二三四五六七八九十廿]+|\d{1,2})月"
    r"(?:"
    r"(?P<day>[初一二三四五六七八九十廿卅]+|\d{1,2})"
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
        elif year_str.isdecimal():
            year = int(year_str)
        else:
            year = _parse_chinese_number(year_str)
            if year is None:
                return None
        month: int | None = None
        if month_str:
            month = int(month_str) if month_str.isdecimal() else _parse_chinese_number(month_str)
        day: int | None = None
        if day_str:
            day = int(day_str) if day_str.isdecimal() else _parse_chinese_number(day_str)
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
# Simplified → traditional era names
# ---------------------------------------------------------------------------

COUNTRIES = ("chinese", "japanese", "korean", "vietnamese")

# Era names in the database use traditional characters. This maps simplified
# characters to the traditional forms that occur in era names (made with
# OpenCC t2s over every era-name character in calendar.db).
_S2T_ERA = dict(item.split(":") for item in (
    "万:萬 业:業 丰:豐 义:義 乌:烏 乐:樂 云:雲 仪:儀 会:會 兴:興 养:養 册:冊 "
    "凤:鳳 升:昇 协:協 历:曆歷 号:號 后:後 启:啟 吴:吳 国:國 圣:聖 复:復 "
    "宁:寧甯 宝:寶 宽:寬寛 寿:壽 将:將 岁:歲 干:乾 广:廣 庆:慶 应:應 开:開 "
    "总:總 护:護 摄:攝 无:無 显:顯 杨:楊 极:極 汉:漢 济:濟 灵:靈 玺:璽 监:監 "
    "礼:禮 祯:禎 禄:祿 纪:紀 绍:紹 统:統 绥:綏 绪:緒 维:維 聪:聰 胜:勝 节:節 "
    "观:觀 视:視 证:證 调:調 贞:貞 贶:貺 资:資 赐:賜 赞:贊 载:載 辅:輔 运:運 "
    "鉴:鑑 铜:銅 长:長 阳:陽 顺:順 颁:頒 飞:飛 鸟:鳥 鸿:鴻 黄:黃 齐:齊 龙:龍 "
    "龟:龜"
).split())


def traditional_variants(name: str, limit: int = 64) -> list[str]:
    """Traditional spellings of a (possibly simplified) era name, e.g. 万历 → 萬曆, 萬歷."""
    variants = [""]
    for ch in name:
        options = [ch] + list(_S2T_ERA.get(ch, ""))
        variants = [v + o for v in variants for o in options][:limit]
    return [v for v in variants if v != name]


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


def resolve_era_name(conn: sqlite3.Connection, era_name: str,
                     country: str | None = None) -> tuple[list[sqlite3.Row], str]:
    """
    Find eras by name, trying traditional forms if the name is simplified.

    Returns (rows, name_used). name_used differs from era_name when a
    simplified name (万历) was read as a traditional one (萬曆).
    """
    rows = find_eras_by_name(conn, era_name, country)
    if rows:
        return rows, era_name
    for variant in traditional_variants(era_name):
        rows = find_eras_by_name(conn, variant, country)
        if rows:
            return rows, variant
    return [], era_name


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


def find_date_by_jdn(conn: sqlite3.Connection, jdn: int,
                     country: str | None = None) -> list[sqlite3.Row]:
    sql = """
        SELECT m.*, es.era_name, es.emperor_name, es.dynasty_name, es.country
        FROM month m
        JOIN era_summary es ON es.era_id = m.era_id
        WHERE m.first_jdn <= ? AND m.last_jdn >= ?
    """
    params: list = [jdn, jdn]
    if country:
        sql += " AND es.country = ?"
        params.append(country)
    sql += " ORDER BY es.country, m.first_jdn"
    return conn.execute(sql, params).fetchall()


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


def convert_cjk_to_jdn(conn: sqlite3.Connection, parsed: ParsedDate,
                       country: str | None = None) -> list[tuple[int, EraInfo]]:
    """
    Convert a parsed CJK date to JDN(s). Multiple results when era name is ambiguous.

    country ("chinese", "japanese", "korean", "vietnamese") keeps only that
    calendar. Simplified era names (万历) are read as traditional (萬曆).
    """
    eras, _ = resolve_era_name(conn, parsed.era, country or parsed.country_hint)
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
                    if day < 1:
                        continue
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
                    continued_use=month_row["status"] == "P",
                )
                results.append((jdn, era_info))

    return results


def convert_jdn(conn: sqlite3.Connection, jdn: int, era_id: int | None = None,
                country: str | None = None) -> DateConversion:
    """
    Convert a JDN to all calendar representations.

    The year and month 干支 come from the row of era_id when given (the
    calendar the user entered), else from the first row (Chinese first).
    Months can differ between calendars: Japanese 天保3年十一月 (month 壬子)
    overlaps Chinese 道光12年十月 (month 辛亥). country keeps only one calendar.
    """
    g_year, g_month, g_day = jdn_to_gregorian(jdn)
    gregorian = format_date(g_year, g_month, g_day)

    julian_str: str | None = None
    if jdn < 2299161:  # Gregorian reform: Oct 15, 1582
        j_year, j_month, j_day = jdn_to_julian(jdn)
        julian_str = format_date(j_year, j_month, j_day)

    ganzhi_day = jdn_to_ganzhi_day(jdn)
    ganzhi_year = ""
    ganzhi_month_str = ""

    month_rows = find_date_by_jdn(conn, jdn, country)
    cjk_dates: list[EraInfo] = []
    ganzhi_row = next((r for r in month_rows if r["era_id"] == era_id and r["ganzhi"]), None)
    if ganzhi_row is None:
        ganzhi_row = next((r for r in month_rows if r["ganzhi"]), None)
    if ganzhi_row is not None:
        ganzhi_year = ganzhi_row["ganzhi"]
        # Leap months have no month 干支 of their own
        if not ganzhi_row["leap_month"]:
            ganzhi_month_str = month_ganzhi(ganzhi_year, ganzhi_row["month"])

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
            continued_use=row["status"] == "P",
        ))

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
        rows, _ = resolve_era_name(conn, era_name, country)
        if dynasty_name:
            rows = [r for r in rows if r["dynasty_name"] == dynasty_name]
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


# Options each command accepts (all take one value)
_COMMAND_OPTIONS = {
    "setup": set(),
    "convert": {"--country"},
    "jdn": {"--country"},
    "gregorian": {"--country"},
    "eras": {"--name", "--dynasty", "--country"},
}
_COMMAND_ARGS = {"setup": 0, "convert": 1, "jdn": 1, "gregorian": 3, "eras": 0}
_COMMAND_USAGE = {
    "setup": "setup [--db PATH]",
    "convert": "convert <CJK date string> [--country C] [--db PATH]",
    "jdn": "jdn <JDN> [--country C] [--db PATH]",
    "gregorian": "gregorian <year> <month> <day> [--country C] [--db PATH]",
    "eras": "eras [--name N] [--dynasty D] [--country C] [--db PATH]",
}


def parse_cli(argv: list[str]) -> tuple[str, list[str], dict[str, str]]:
    """
    Split argv (without the program name) into (command, positionals, options).

    Unknown options, missing option values, a wrong number of positional
    arguments and unknown countries raise ValueError.
    """
    if not argv:
        raise ValueError("no command given")
    cmd, rest = argv[0], argv[1:]
    if cmd not in _COMMAND_OPTIONS:
        raise ValueError(f"unknown command: {cmd}")
    allowed = _COMMAND_OPTIONS[cmd] | {"--db"}
    positionals: list[str] = []
    options: dict[str, str] = {}
    i = 0
    while i < len(rest):
        arg = rest[i]
        if arg.startswith("--"):
            name, eq, value = arg.partition("=")
            if name not in allowed:
                raise ValueError(f"unknown option for {cmd}: {name}")
            if not eq:
                if i + 1 >= len(rest):
                    raise ValueError(f"{name} needs a value")
                value = rest[i + 1]
                i += 1
            options[name] = value
        else:
            positionals.append(arg)
        i += 1
    if len(positionals) != _COMMAND_ARGS[cmd]:
        raise ValueError(f"wrong number of arguments. Usage: calendar_converter.py {_COMMAND_USAGE[cmd]}")
    country = options.get("--country")
    if country is not None:
        country = country.lower()
        if country not in COUNTRIES:
            raise ValueError(f"unknown country: {options['--country']} (use one of: {', '.join(COUNTRIES)})")
        options["--country"] = country
    return cmd, positionals, options


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        _usage()

    try:
        cmd, args, opts = parse_cli(sys.argv[1:])
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Run without arguments for help.", file=sys.stderr)
        sys.exit(2)

    db_path = Path(opts["--db"]).expanduser() if "--db" in opts else None
    country = opts.get("--country")

    if cmd == "setup":
        download_db(db_path)
        return

    conn = get_connection(db_path)

    if cmd == "convert":
        text = args[0]
        parsed = parse_cjk_date(text)
        if parsed is None:
            print(f"Could not parse: {text}", file=sys.stderr)
            sys.exit(1)
        _, era_used = resolve_era_name(conn, parsed.era, country or parsed.country_hint)
        if era_used != parsed.era:
            print(f"Note: read the era name {parsed.era} as {era_used}.",
                  file=sys.stderr)
        results = convert_cjk_to_jdn(conn, parsed, country)
        if not results:
            print(f"No matching dates found for: {text}", file=sys.stderr)
            if not find_eras_by_name(conn, era_used):
                print(f"The era name {parsed.era} is not in the database. Era names use "
                      "traditional characters (萬曆, not 万历); Japanese eras use Japanese "
                      "forms (寛永). Check with: eras --name <name>", file=sys.stderr)
            elif country:
                print(f"Try without --country {country}.", file=sys.stderr)
            sys.exit(1)
        output = []
        for jdn, era_info in results:
            conversion = convert_jdn(conn, jdn, era_id=era_info.era_id)
            item = {
                "input_era": _to_dict(era_info),
                "jdn": jdn,
                "gregorian": conversion.gregorian,
                "julian": conversion.julian,
                "ganzhi": _to_dict(conversion.ganzhi),
                "all_cjk_dates": [_to_dict(c) for c in conversion.cjk_dates],
            }
            if era_info.continued_use:
                note = (f"{era_info.era_name} had officially ended by this date. The database "
                        "keeps counting it for later or continued use of the era.")
                if era_info.era_name == "崇禎":
                    note += " After 1644 崇禎 was used by Ming loyalists and in Joseon Korea."
                item["note"] = note
            output.append(item)
        print(json.dumps(output, ensure_ascii=False, indent=2))

    elif cmd == "jdn":
        try:
            jdn = int(args[0])
        except ValueError:
            print(f"JDN must be an integer: {args[0]}", file=sys.stderr)
            sys.exit(1)
        result = convert_jdn(conn, jdn, country=country)
        _print_json(result)

    elif cmd == "gregorian":
        try:
            year, month, day = int(args[0]), int(args[1]), int(args[2])
        except ValueError:
            print("Year, month and day must be integers (astronomical years: 0 = 1 BCE)",
                  file=sys.stderr)
            sys.exit(1)
        jdn = gregorian_to_jdn(year, month, day)
        if jdn_to_gregorian(jdn) != (year, month, day):
            print(f"Invalid Gregorian date: {year}-{month}-{day}", file=sys.stderr)
            sys.exit(1)
        result = convert_jdn(conn, jdn, country=country)
        _print_json(result)

    elif cmd == "eras":
        results = get_era_metadata(conn, opts.get("--name"), opts.get("--dynasty"), country)
        _print_json(results)

    conn.close()


if __name__ == "__main__":
    main()
