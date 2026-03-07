---
name: tgaz-query
description: >
  Query and explore the TGAZ (Temporal Gazetteer) SQLite database of 82,000+
  historical Chinese placenames spanning 763 BCE to 1911 CE. Use this skill
  whenever the user asks about historical Chinese places, administrative
  geography, dynastic jurisdictions, place name evolution, or wants to query
  tgaz.db. Also trigger when the user mentions CHGIS, TGAZ, historical
  gazetteer, Chinese historical GIS, or asks questions like "what was X called
  in dynasty Y", "what counties existed in year Z", "where was X located",
  or any spatial/temporal query about Chinese historical geography. This skill
  is relevant even for casual questions like "tell me about ancient Chang'an"
  or "Tang dynasty cities near the Yellow River".
---

# TGAZ Historical Gazetteer Query Skill

## Setup: Get the Database

Before running any queries, check that `tgaz.db` and `query_tgaz.py` exist in the current directory. If they don't, clone the repo:

```bash
# Check if files exist
ls tgaz.db query_tgaz.py 2>/dev/null

# If not found, clone the repo (requires git-lfs for the 228 MB database)
git lfs install
git clone https://github.com/kltng/tgaz-sqlite.git /tmp/tgaz-sqlite
cp /tmp/tgaz-sqlite/tgaz.db /tmp/tgaz-sqlite/query_tgaz.py .
```

If the user is already inside the `tgaz-sqlite` repo directory, everything is ready — skip the clone.

---

You have access to `tgaz.db`, a SQLite database containing the full China
Historical GIS (CHGIS) dataset from Harvard & Fudan University. It has
82,117 placenames, 245,042 name spellings, 83,400 jurisdictional relationships,
and 25,655 historical notes covering 763 BCE to 1911 CE.

## Quick Start: Use the CLI

For common lookups, `query_tgaz.py` is fastest. Run it via Bash:

```bash
# Search by name (Chinese or romanized)
python3 query_tgaz.py "北京"
python3 query_tgaz.py "Chang'an"

# Name + temporal filter
python3 query_tgaz.py "长安" --year -200

# Full-text search (searches names, feature types, parent names)
python3 query_tgaz.py --fts "county Beijing"

# Spatial query: bounding box (lon_min,lat_min,lon_max,lat_max)
python3 query_tgaz.py --bbox 108,34,110,36 --year -200

# Feature type + year
python3 query_tgaz.py --feature-type county --year 1820 --limit 20

# Children of a jurisdiction
python3 query_tgaz.py --parent hvd_9659 --year 1820

# All name forms for a place (simplified, traditional, pinyin)
python3 query_tgaz.py --spellings hvd_70621

# Full history: parents, predecessors, present location, notes
python3 query_tgaz.py --history hvd_70621

# Output as JSON (for further processing or LLM context)
python3 query_tgaz.py "长安" --format json

# Database statistics
python3 query_tgaz.py --stats

# Raw SQL
python3 query_tgaz.py --sql "SELECT name, transcription, beg_yr, end_yr FROM mv_pn_srch WHERE ftype_tr = 'fu' AND beg_yr <= 1400 AND end_yr >= 1400 ORDER BY name"
```

## When to Use SQL Directly

Use `--sql` or open `tgaz.db` directly when:
- Aggregating (COUNT, GROUP BY, temporal distributions)
- Joining across multiple tables (e.g., spellings + notes + present location)
- Queries the CLI doesn't support (predecessor chains, multi-hop parent traversal)

## Schema Essentials

### The go-to table: `mv_pn_srch`

This pre-joined table has everything for 90% of queries:

| Column | Description |
|--------|-------------|
| `sys_id` | Unique ID (e.g., `hvd_70621`) |
| `name` | Place name (Chinese) |
| `transcription` | Romanized name |
| `beg_yr` / `end_yr` | Temporal range (negative = BCE) |
| `x_coord` / `y_coord` | Longitude / Latitude (as TEXT, cast to REAL for math) |
| `ftype_vn` | Feature type in Chinese (e.g., 县) |
| `ftype_tr` | Feature type romanized (e.g., xian) |
| `parent_sys_id` | Parent jurisdiction ID |
| `parent_vn` / `parent_tr` | Parent name (Chinese / romanized) |
| `data_src` | Source code (CHGIS, TBRC, HGR) |

### Other key tables

| Table | Use for |
|-------|---------|
| `placename` | Core records with full metadata, FK to ftype/data_src/snote |
| `spelling` | All 245K name forms (simplified, traditional, pinyin, Tibetan) |
| `part_of` | Parent-child jurisdiction links with temporal bounds |
| `prec_by` | Which place preceded which (name changes over time) |
| `present_loc` | Modern-day location mapping |
| `snote` | Historical notes and annotations |
| `ftype` | Feature type lookup (name_en, name_vn, name_tr) |
| `data_src` | Data source lookup (CHGIS, TBRC, HGR) |

### Useful views

| View | What it joins |
|------|--------------|
| `v_search` | `mv_pn_srch` + data source names |
| `v_placename` | `placename` + `data_src` + `ftype` |
| `v_full` | `placename` + `data_src` + `ftype` + `snote` + `present_loc` |
| `v_placename_names` | `placename` + `spelling` + `script` + `trsys` |

### FTS5 indexes

| Index | Searches over |
|-------|--------------|
| `search_fts` | Names, transcriptions, feature types, parent names |
| `spelling_fts` | All 245K written forms |
| `notes_fts` | Historical note topics and full text |

## Data Conventions

- **Years**: Negative integers = BCE. `-202` means 202 BCE. `9999` means "still existing."
- **sys_id format**: `hvd_NNNNN` for CHGIS, `TBRC_GNNNN` for Tibetan data, `HGR_NNNNN` for Russian data.
- **Coordinates**: Stored as TEXT. Use `CAST(x_coord AS REAL)` for math. x = longitude, y = latitude.
- **Feature types**: The `ftype_tr` field has romanized types. Common ones:
  - `xian` (县, county), `fu` (府, prefecture), `jun` (郡, commandery)
  - `sheng` (省, province), `lu` (路, circuit), `dao` (道, circuit/route)
  - `zhou` (州, prefecture), `guo` (国, kingdom/state), `dgon pa` (monastery)

## Common Query Patterns

### "What was this area called in year X?"
```sql
SELECT name, transcription, ftype_tr, beg_yr, end_yr
FROM mv_pn_srch
WHERE CAST(x_coord AS REAL) BETWEEN 116.0 AND 117.0
  AND CAST(y_coord AS REAL) BETWEEN 39.5 AND 40.5
  AND beg_yr <= 1400 AND end_yr >= 1400
ORDER BY ftype_tr;
```

### "Show the administrative hierarchy of place X"
```sql
-- Get the place and all its parents over time
SELECT m.name AS child_name, m.transcription AS child_trans,
       po.begin_year, po.end_year,
       pm.name AS parent_name, pm.transcription AS parent_trans,
       pm.ftype_tr AS parent_type
FROM part_of po
JOIN placename c ON po.child_id = c.id
JOIN placename p ON po.parent_id = p.id
JOIN mv_pn_srch m ON m.sys_id = c.sys_id
JOIN mv_pn_srch pm ON pm.sys_id = p.sys_id
WHERE c.sys_id = 'hvd_70621'
ORDER BY po.begin_year;
```

### "What did this place used to be called?"
```sql
-- Predecessor chain
SELECT prev.sys_id, m.name, m.transcription, m.beg_yr, m.end_yr
FROM prec_by pb
JOIN placename curr ON pb.placename_id = curr.id
JOIN placename prev ON pb.prec_id = prev.id
JOIN mv_pn_srch m ON m.sys_id = prev.sys_id
WHERE curr.sys_id = 'hvd_70626';
```

### "All spellings of a place across scripts"
```sql
SELECT s.written_form, sc.name AS script, sc.lang, tr.name AS trsys
FROM spelling s
JOIN placename p ON s.placename_id = p.id
LEFT JOIN script sc ON s.script_id = sc.id
LEFT JOIN trsys tr ON s.trsys_id = tr.id
WHERE p.sys_id = 'hvd_70621'
ORDER BY sc.lang;
```

### "Counties per dynasty/period"
```sql
SELECT
  CASE
    WHEN beg_yr BETWEEN -221 AND -207 THEN 'Qin'
    WHEN beg_yr BETWEEN -206 AND 8 THEN 'Western Han'
    WHEN beg_yr BETWEEN 25 AND 220 THEN 'Eastern Han'
    WHEN beg_yr BETWEEN 618 AND 907 THEN 'Tang'
    WHEN beg_yr BETWEEN 960 AND 1279 THEN 'Song'
    WHEN beg_yr BETWEEN 1271 AND 1368 THEN 'Yuan'
    WHEN beg_yr BETWEEN 1368 AND 1644 THEN 'Ming'
    WHEN beg_yr BETWEEN 1644 AND 1911 THEN 'Qing'
    ELSE 'Other'
  END AS dynasty,
  COUNT(*) AS county_count
FROM mv_pn_srch
WHERE ftype_tr = 'xian'
GROUP BY dynasty
ORDER BY MIN(beg_yr);
```

## Presenting Results

When answering user questions about historical places:

1. **Lead with the answer** in natural language, then show supporting data.
2. **Include temporal context** — say "during the Tang dynasty (618-907)" not just "in 700 CE."
3. **Note name changes** — if a place had different names in different periods, mention the evolution.
4. **Use both Chinese and romanized names** — e.g., "长安县 (Chang'an Xian)."
5. **Mention modern location** when relevant — use `--history` or `present_loc` table.
6. **For JSON output to feed into other tools**, use `--format json` or `--format jsonl`.
