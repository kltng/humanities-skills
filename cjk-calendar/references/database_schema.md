# CJK Calendar Database Schema

SQLite database with East Asian lunisolar calendar data from ~220 BCE to 1945 CE.

## Tables

### `dynasty`
Country/tradition grouping (chinese, japanese, korean, vietnamese).

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Dynasty ID |
| `type` | TEXT | `'chinese'`, `'japanese'`, `'korean'`, or `'vietnamese'` |

### `dynasty_name`
Multilingual dynasty names (ranking 0 = primary name).

| Column | Type | Description |
|---|---|---|
| `dynasty_id` | INTEGER FK | References dynasty(id) |
| `name` | TEXT | Dynasty name |
| `ranking` | INTEGER | 0 = primary |
| `language_id` | INTEGER | Language identifier |

### `emperor` / `emperor_name`
Emperor records, linked to dynasty. Same ranking pattern as dynasty_name.

### `era` / `era_name`
Era (年號) records, linked to emperor. Same ranking pattern.

### `month` (core table — 131,808 records)

Each row represents one lunar month within an era.

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Month record ID |
| `year` | INTEGER | Ordinal year within era (1 = 元年) |
| `month` | INTEGER | Month number (1-12) |
| `month_name` | TEXT | Chinese month name (e.g., 四月) |
| `leap_month` | INTEGER | 1 if leap month, 0 otherwise |
| `era_id` | INTEGER FK | References era(id) |
| `first_jdn` | INTEGER | JDN of first day of month |
| `last_jdn` | INTEGER | JDN of last day of month |
| `ganzhi` | TEXT | Sexagenary year designation (e.g., 庚午) |
| `start_from` | INTEGER | Day numbering start (usually 1) |
| `status` | TEXT | `'S'` standard, `'P'` proleptic |
| `eclipse` | INTEGER | Eclipse flag |

### `era_summary` (view)

Pre-joined view combining era, emperor, dynasty names with date ranges.

| Column | Source |
|---|---|
| `era_id` | era.id |
| `era_name` | era_name.name (ranking=0) |
| `emperor_id` | emperor.id |
| `emperor_name` | emperor_name.name (ranking=0) |
| `dynasty_id` | dynasty.id |
| `dynasty_name` | dynasty_name.name (ranking=0) |
| `country` | dynasty.type |
| `start_jdn` | MIN(month.first_jdn) |
| `end_jdn` | MAX(month.last_jdn) |

## Key Indexes

- `idx_month_jdn_range` on `month(first_jdn, last_jdn)` — fast JDN lookups
- `idx_era_name_name` on `era_name(name)` — era name search
- `idx_month_era_id` on `month(era_id)` — era-based month queries

## Common Query Patterns

### Find all eras matching a name

```sql
SELECT * FROM era_summary WHERE era_name = '康熙';
```

### Find lunar months for a specific era-year

```sql
SELECT * FROM month
WHERE era_id = ? AND year = ?
ORDER BY first_jdn;
```

### Find a specific month (with leap month handling)

```sql
SELECT * FROM month
WHERE era_id = ? AND year = ? AND month = ? AND leap_month = ?
ORDER BY first_jdn;
```

### Convert JDN to CJK date (find containing month)

```sql
SELECT m.*, es.era_name, es.emperor_name, es.dynasty_name, es.country
FROM month m
JOIN era_summary es ON es.era_id = m.era_id
WHERE m.first_jdn <= ? AND m.last_jdn >= ?
ORDER BY es.country, m.first_jdn;
```

The day within the month is: `jdn - first_jdn + start_from`

### Find years by ganzhi within an era

```sql
SELECT DISTINCT year, ganzhi FROM month
WHERE era_id = ? AND ganzhi = ?
ORDER BY year;
```

### List eras by dynasty/country

```sql
SELECT * FROM era_summary
WHERE country = 'chinese' AND dynasty_name = '明'
ORDER BY start_jdn;
```

## JDN Reference Points

| Date | JDN | Notes |
|---|---|---|
| 4713 BCE Jan 1 (Julian) | 0 | JDN epoch |
| 1582 Oct 15 (Gregorian) | 2,299,161 | Gregorian reform |
| 1644 Mar 19 (Gregorian) | 2,321,605 | Fall of Ming |
| 1868 Jan 25 (Gregorian) | 2,403,400 | Meiji era start |

## Day Counting

Lunar months typically have 29 or 30 days. The number of days in a month is:
`last_jdn - first_jdn + 1`

Day numbering within a month starts at `start_from` (usually 1). To compute day N:
`jdn = first_jdn + (N - start_from)`
