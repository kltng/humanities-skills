---
name: cbdb-local
description: Query the China Biographical Database (CBDB) locally via SQLite for biographical data on 656K+ historical Chinese figures from the 7th century BCE through the 19th century CE. Use when searching for Chinese historical figures, scholars, officials, or literary figures — their biographical details, family/kinship networks, official postings, social associations, examination records, or addresses. Runs entirely locally after initial database download (~556 MB). Faster and more flexible than the API version.
version: 1.0.0
license: MIT
author: Kwok-leong Tang
contributors:
  - name: Claude
    type: AI Assistant
---

# CBDB Local (SQLite)

Query the China Biographical Database locally — 656K+ historical Chinese figures, 7th c. BCE to 19th c. CE. No network calls after setup.

## When to Use

- **Use cbdb-local** (this skill) for: offline access, complex queries, batch analysis, full kinship/social network traversal, raw SQL queries
- **Use cbdb-api** for: quick lookups when database isn't downloaded, or when disk space is limited

## Setup

Download and extract the SQLite database (~69 MB compressed, ~556 MB uncompressed):

```bash
python3 scripts/cbdb_query.py setup
```

**Requires 7z** for extraction:
- macOS: `brew install 7zip`
- Windows: `winget install 7zip.7zip` or download from https://www.7-zip.org/
- Linux: `sudo apt install p7zip-full`

Setup is one-time. The script downloads from GitHub, extracts, creates search indexes, and cleans up the archive.

## Quick Start

### Search by Name

```bash
# Chinese name (exact match, then alt names, then fuzzy)
python3 scripts/cbdb_query.py person "蘇軾"

# Pinyin name
python3 scripts/cbdb_query.py person "Su Shi"

# By person ID (returns full profile)
python3 scripts/cbdb_query.py person --id 3767
```

Single match returns a **full profile** (bio + alt names + kinship + offices + associations + addresses + entries + status + texts + institutions + posting addresses). Multiple matches return a list of candidates.

### Specific Data

```bash
python3 scripts/cbdb_query.py kinship 3767       # Family tree
python3 scripts/cbdb_query.py offices 3767        # Official postings
python3 scripts/cbdb_query.py associations 3767   # Social network
python3 scripts/cbdb_query.py addresses 3767      # Places/addresses
python3 scripts/cbdb_query.py entries 3767        # Exam/entry records
python3 scripts/cbdb_query.py altnames 3767       # Alternative names
python3 scripts/cbdb_query.py status 3767         # Social status
python3 scripts/cbdb_query.py texts 3767          # Writings/texts
python3 scripts/cbdb_query.py institutions 3767   # Academies, temples, etc.
python3 scripts/cbdb_query.py postaddr 3767       # Places of official service
```

### Raw SQL

```bash
python3 scripts/cbdb_query.py sql "SELECT c_personid, c_name_chn, c_birthyear FROM BIOG_MAIN WHERE c_dy = 15 AND c_birthyear > 1000 LIMIT 10"
```

Only SELECT queries are allowed. For complex queries, use `ZZZ_` denormalized tables (e.g., `ZZZ_ENTRY_DATA`, `ZZZ_KIN_BIOG_ADDR`) which pre-join names and descriptions — much simpler than multi-table joins. See `references/database_schema.md` for the full list.

## Output Format

All commands output JSON. Example for `person "蘇軾"`:

```json
{
  "basic_info": {
    "person_id": 3767,
    "name_chn": "蘇軾",
    "name_pinyin": "Su Shi",
    "dynasty_chn": "宋",
    "birth_year": 1036,
    "death_year": 1101
  },
  "alt_names": [
    { "name_chn": "子瞻", "type_chn": "字", "type": "Courtesy name" },
    { "name_chn": "東坡居士", "type_chn": "室名、別號", "type": "Studio name, Style name" }
  ],
  "kinship": [
    { "name_chn": "蘇洵", "relation_chn": "父", "relation": "F" },
    { "name_chn": "蘇轍", "relation_chn": "弟", "relation": "B-" }
  ],
  "offices": [...],
  "associations": [...],
  "addresses": [...],
  "entries": [...],
  "status": [...],
  "texts": [
    { "title_chn": "東坡集", "role_chn": "撰著者", "role": "Author" }
  ],
  "institutions": [...],
  "posted_addresses": [...]
}
```

## Kinship Tree Visualization

Generate family tree diagrams from CBDB kinship data.

### Tree Commands

```bash
# Graphviz DOT format (recommended for quality)
python3 scripts/cbdb_query.py tree 3767 -d 2 -f dot -o su_shi.dot

# Render DOT to image (requires: brew install graphviz)
dot -Tsvg su_shi.dot -o su_shi.svg
dot -Tpng su_shi.dot -o su_shi.png

# Mermaid format (paste into GitHub, Obsidian, etc.)
python3 scripts/cbdb_query.py tree 3767 -d 2 -f mermaid -o su_shi.md

# Direct SVG (requires graphviz, falls back to DOT if missing)
python3 scripts/cbdb_query.py tree 3767 -d 2 -f svg -o su_shi.svg
```

### Visual Conventions

- **Gold** node = ego (the queried person)
- **Blue** nodes = male, **Pink** nodes = female
- **Solid arrows** = parent → child
- **Dashed lines** = marriage / affinal relations
- **Dotted lines** = siblings
- Nodes show name and birth–death years when known
- Generations are laid out top-to-bottom (ancestors above, descendants below)

### Options

| Flag | Description | Default |
|---|---|---|
| `--depth` / `-d` | BFS expansion depth from ego | `2` |
| `--format` / `-f` | `dot`, `mermaid`, or `svg` | `dot` |
| `--output` / `-o` | Output file path | Auto-named |

Depth 1 = ego's direct kin only. Depth 2 = kin of kin (recommended). Depth 3+ can produce very large trees.

## Network Export (for Gephi / Graph Analysis)

Export CBDB relationships as network graphs in GEXF (Gephi native), CSV (nodes + edges), or JSON.

### Export Commands

```bash
# Kinship network from a person, expanding outward
python3 scripts/cbdb_query.py export-kinship 3767 -d 2 -o su_shi_kin.gexf

# Social association network
python3 scripts/cbdb_query.py export-associations 3767 -d 1 -o su_shi_assoc.gexf

# Combined kinship + associations
python3 scripts/cbdb_query.py export-network 3767 -d 1 -o su_shi_full.gexf

# Co-office network: people who held the same office
python3 scripts/cbdb_query.py export-office "翰林學士" --dynasty 15 -o hanlin.gexf

# Person-place bipartite network
python3 scripts/cbdb_query.py export-place "眉山" -o meishan.gexf
```

### Options

| Flag | Description | Default |
|---|---|---|
| `--format` / `-f` | `gexf`, `csv`, or `json` | `gexf` |
| `--depth` / `-d` | Expansion depth (1 = direct, 2 = friends-of-friends) | `1` |
| `--output` / `-o` | Output file path | Auto-named |
| `--dynasty` | Filter by dynasty code (e.g., 15 = Song) | All |
| `--year-from` | Filter postings from this year | None |
| `--year-to` | Filter postings up to this year | None |
| `--addr-type` | Filter place network by address type (1 = 籍貫) | All |

### Network Types

| Command | Nodes | Edges | Use Case |
|---|---|---|---|
| `export-kinship` | Persons | Kin relations (labeled F, M, S, B, W, etc.) | Family tree / clan analysis |
| `export-associations` | Persons | Social ties (friend, teacher, political ally) | Social network analysis |
| `export-network` | Persons | Both kin + social | Combined prosopography |
| `export-office` | Persons | Co-officeholding | Political elite networks |
| `export-place` | Persons + Places | Affiliations | Spatial analysis, migration |

### Multiple Seeds

All person-based exports accept multiple person IDs:
```bash
python3 scripts/cbdb_query.py export-kinship 3767 1762 -d 1 -o su_wang.gexf
```

### Node Attributes (available in Gephi)

`name_chn`, `name_pinyin`, `gender`, `dynasty_chn`, `dynasty`, `birth_year`, `death_year`, `index_year`. Place nodes add `longitude`, `latitude`, `node_type`.

### Edge Attributes

`type` (kinship/association/co-office/person-place), `relation_chn`, `relation`.

### Tips

- **Start with depth=1** — depth=2 can produce very large networks (thousands of nodes)
- **CSV format** produces two files: `*_nodes.csv` and `*_edges.csv`, directly importable into Gephi via "Import Spreadsheet"
- **GEXF** is recommended — preserves all attributes and is Gephi's native format
- **Office codes are dynasty-specific** — use `--dynasty` to narrow results, or omit for cross-dynasty comparison

## Important Caveats

- **Index year is artificial**: Derived estimate of birth year, not a real date. Many people have 0 (unknown) and are excluded by year filters.
- **Song dynasty = one code (15)**: Does not distinguish Northern from Southern Song.
- **Office codes are dynasty-specific**: A Song office code won't match in a Ming query. Search by Chinese office name for cross-dynasty comparison.
- **Association dates are usually empty**: Filter by index year of individuals instead.
- **Extended kinship searches can be huge**: Start with conservative distance parameters.

## Using in Python

```python
import sys
sys.path.insert(0, "scripts")
from cbdb_query import (
    get_connection, search_person, get_full_profile,
    get_kinship, get_offices, get_associations,
    get_texts, get_institutions, get_posted_addresses, run_sql,
    build_kinship_network, build_association_network,
    build_combined_network, build_office_network,
    build_place_network, export_network,
)

conn = get_connection()

# Search
results = search_person(conn, "王安石")
print(f"Found {len(results)} results")

# Full profile
profile = get_full_profile(conn, 3767)  # Su Shi
for kin in profile["kinship"]:
    print(f"{kin['relation_chn']}: {kin['name_chn']}")

# Raw SQL for advanced queries
rows = run_sql(conn, """
    SELECT b.c_name_chn, COUNT(k.c_kin_id) as kin_count
    FROM BIOG_MAIN b
    JOIN KIN_DATA k ON k.c_personid = b.c_personid
    WHERE b.c_dy = 15
    GROUP BY b.c_personid
    ORDER BY kin_count DESC
    LIMIT 10
""")

# Export network for Gephi
network = build_kinship_network(conn, [3767], depth=2)
export_network(network, "su_shi_kin.gexf", "gexf")
```

## Database Coverage

| Table | Records | Description |
|---|---|---|
| BIOG_MAIN | 656,436 | Core biographical records |
| POSTING_DATA | 601,663 | Career posting records |
| POSTED_TO_OFFICE_DATA | 601,002 | Office assignments with titles |
| KIN_DATA | 553,330 | Kinship/family relationships |
| BIOG_ADDR_DATA | 455,705 | Person-place associations |
| ENTRY_DATA | 263,267 | Exam/entry records |
| ALTNAME_DATA | 206,132 | Alternative names (zi, hao, etc.) |
| ASSOC_DATA | 186,876 | Social associations |
| STATUS_DATA | 69,344 | Social status records |
| BIOG_TEXT_DATA | ~50,000 | Person-text relations |
| BIOG_INST_DATA | ~10,000 | Person-institution relations |
| OFFICE_CODES | 34,052 | Office title lookup |
| ADDR_CODES | 30,099 | Place name lookup (with coordinates) |
| DYNASTIES | 85 | Dynasty lookup |

## Key Person IDs for Testing

| Person | ID | Dynasty |
|---|---|---|
| 蘇軾 Su Shi | 3767 | 宋 |
| 王安石 Wang Anshi | 1762 | 宋 |
| 歐陽修 Ouyang Xiu | 4766 | 宋 |
| 司馬光 Sima Guang | 3692 | 宋 |
| 李白 Li Bai | 21646 | 唐 |
| 杜甫 Du Fu | 21831 | 唐 |

## Comparison with cbdb-api

| Feature | cbdb-local | cbdb-api |
|---|---|---|
| Setup | Download ~556 MB | None |
| Speed | Instant (local SQLite) | Network latency + rate limits |
| Offline | Yes | No |
| Raw SQL | Yes | No |
| Batch queries | Fast | Rate-limited |
| Data freshness | Download date | Always current |

## Resources

- `scripts/cbdb_query.py` — Standalone query tool (Python 3.9+, zero dependencies)
- `references/database_schema.md` — Full SQLite schema and query guide
- Source: [cbdb-project/cbdb_sqlite](https://github.com/cbdb-project/cbdb_sqlite)
- CBDB Project: https://projects.iq.harvard.edu/cbdb
