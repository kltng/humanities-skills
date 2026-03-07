---
name: cjk-calendar
description: Convert between Chinese, Japanese, Korean, and Vietnamese lunisolar calendar dates and Gregorian/Julian dates. Use when the user needs to look up historical East Asian dates, convert era names (年號) like 康熙, 天保, 崇禎 to Western dates, compute sexagenary cycle (干支) day/month/year, or work with Julian Day Numbers. Supports ~220 BCE to 1945 CE with 1,637 eras and 131,808 lunar month records. Runs entirely locally with a SQLite database.
version: 1.0.0
license: MIT
author: Kwok-leong Tang
contributors:
  - name: Claude
    type: AI Assistant
---

# CJK Calendar Converter

Convert between East Asian lunisolar calendars (Chinese, Japanese, Korean, Vietnamese) and Gregorian/Julian dates. All conversions run locally against a SQLite database — no network calls after setup.

## When to Use

- Converting a CJK era date to Gregorian (e.g., 崇禎三年四月初三 → 1630-05-14)
- Converting a Gregorian date to concurrent CJK era dates
- Looking up era metadata (date ranges, dynasties, emperors)
- Computing sexagenary cycle (干支) for a given date
- Working with Julian Day Numbers (JDN)
- Japanese era shorthand (M45.7.30, H26.6.8)

## Setup

Download the SQLite database (~14 MB) on first use:

```bash
python3 scripts/calendar_converter.py setup
```

This downloads `calendar.db` into the `scripts/` directory. Only needed once.

## Quick Start

### CJK Date → Gregorian

```bash
python3 scripts/calendar_converter.py convert "崇禎三年四月初三"
python3 scripts/calendar_converter.py convert "康熙六十一年十二月二十九日"
python3 scripts/calendar_converter.py convert "天保三年閏十一月十五日"
python3 scripts/calendar_converter.py convert "M1.1.1"
```

### Gregorian → CJK Dates

```bash
python3 scripts/calendar_converter.py gregorian 1644 3 19
```

### JDN → All Calendars

```bash
python3 scripts/calendar_converter.py jdn 2299161
```

### Search Eras

```bash
python3 scripts/calendar_converter.py eras --name 康熙
python3 scripts/calendar_converter.py eras --dynasty 明 --country chinese
python3 scripts/calendar_converter.py eras --country japanese
```

## Supported Input Formats

| Format | Example | Notes |
|---|---|---|
| Chinese numerals | 崇禎三年四月初三 | Standard CJK date |
| Leap month | 天保三年閏九月十五日 | 閏 prefix marks leap |
| 元年 (year 1) | 康熙元年正月初一 | 元 = 1, 正 = month 1 |
| 廿/卅 shorthand | 光緒廿八年三月卅日 | 廿 = 20, 卅 = 30 |
| Arabic numerals | 康熙61年12月29日 | Mixed format |
| Japanese shorthand | M1.1.1 | M/T/S/H/R for eras (lunisolar years only) |
| Ganzhi year | 嘉慶甲午年三月初五 | Sexagenary year cycle |
| Full ganzhi | 嘉慶甲午年丁亥月丙子日 | Year + month + day ganzhi |

## Output Format

All commands output JSON. Example for `convert`:

```json
[
  {
    "input_era": {
      "era_name": "崇禎",
      "era_id": 371,
      "emperor_name": "思宗",
      "dynasty_name": "明",
      "country": "chinese",
      "year_in_era": 3,
      "month": 4,
      "month_name": "四月",
      "is_leap_month": false,
      "day": 3
    },
    "jdn": 2316520,
    "gregorian": "1630-05-14",
    "julian": "1630-05-04",
    "ganzhi": { "year": "庚午", "month": "辛巳", "day": "丙子" },
    "all_cjk_dates": [
      { "era_name": "崇禎", "country": "chinese", "year_in_era": 3, ... },
      { "era_name": "寛永", "country": "japanese", "year_in_era": 7, ... }
    ]
  }
]
```

## Key Concepts

### Julian Day Number (JDN)

JDN is the universal pivot for all conversions. It's an integer day count from noon GMT, January 1, 4713 BCE (Julian calendar). Every lunisolar month record in the database stores its `first_jdn` and `last_jdn`.

### Sexagenary Cycle (干支)

The 60-unit cycle combines 10 Heavenly Stems (天干: 甲乙丙丁戊己庚辛壬癸) with 12 Earthly Branches (地支: 子丑寅卯辰巳午未申酉戌亥). Used for years, months, and days.

- **Day ganzhi**: `(JDN + 49) mod 60` gives the cycle index
- **Month ganzhi**: Derived from the year's Heavenly Stem via the Five Tigers formula (五虎遁)
- **Year ganzhi**: Stored in the database for each lunar month record

### Ambiguous Era Names

The same era name can appear in different dynasties or countries (e.g., 建武 was used by both Han and Japanese emperors). When results are ambiguous, the converter returns all matches. Use `--country` to filter.

## Coverage

| Region | Coverage | Era Count |
|---|---|---|
| Chinese | ~220 BCE – 1912 CE | ~900 eras |
| Japanese | 645 CE – 1945 CE | ~250 eras |
| Korean | Various periods | ~200 eras |
| Vietnamese | Various periods | ~200 eras |

Total: 1,637 eras, 131,808 lunar month records.

**Note**: Japanese dates after Meiji 5 (1872) are not in the database because Japan adopted the Gregorian calendar in 1873. Japanese shorthand (M/T/S/H/R) only works for lunisolar-era dates.

## Using in Python

Import the script directly for programmatic use:

```python
import sys
sys.path.insert(0, "scripts")
from calendar_converter import (
    get_connection, parse_cjk_date, convert_cjk_to_jdn,
    convert_jdn, gregorian_to_jdn, get_era_metadata,
)

conn = get_connection()

# CJK → Gregorian
parsed = parse_cjk_date("康熙六十一年十二月二十九日")
results = convert_cjk_to_jdn(conn, parsed)
for jdn, era_info in results:
    conversion = convert_jdn(conn, jdn)
    print(f"{era_info.era_name} → {conversion.gregorian}")

# Gregorian → CJK
jdn = gregorian_to_jdn(1644, 3, 19)
conversion = convert_jdn(conn, jdn)
for cjk in conversion.cjk_dates:
    print(f"{cjk.era_name}{cjk.year_in_era}年{cjk.month_name}{cjk.day}日 ({cjk.country})")
```

## Database Schema

See `references/database_schema.md` for the full schema and query guide.

## Resources

- `scripts/calendar_converter.py` — Standalone converter (Python 3.10+, zero dependencies)
- `references/database_schema.md` — SQLite schema and query patterns
- Source data: [DILA Authority Database](http://authority.dila.edu.tw/time/)
