---
name: chgis-tgaz
description: Query the China Historical GIS (CHGIS) Temporal Gazetteer (TGAZ) API to search for historical Chinese placenames from 222 BCE to 1911 CE. Use this skill when searching for information about historical Chinese places, administrative units, or geographic locations during the dynastic period. Applicable for queries about historical place names, administrative hierarchies, or when users mention specific Chinese locations with historical context.
version: 1.1.0
license: MIT
creator: AI
author: Kwok-leong Tang
contributors:
  - Claude (AI Assistant)
  - Z.ai (AI Platform)
---

# CHGIS TGAZ

Query the China Historical GIS Temporal Gazetteer for historical placenames and administrative units (222 BCE–1911 CE).

## Critical: Things Claude Won't Know Without This Skill

**The correct domain is `chgis.hudci.org`** — the old `maps.cga.harvard.edu` is defunct. Do not use it.

**ID lookups use a URL path format, NOT query params:**
```
✅  https://chgis.hudci.org/tgaz/placename/json/hvd_32180
❌  https://chgis.hudci.org/tgaz/placename?id=hvd_32180&fmt=json
```
The `?fmt=json` parameter only works for the faceted search endpoint.

**TGAZ IDs use the `hvd_` prefix:** CHGIS ID 32180 → TGAZ ID `hvd_32180`.

**The `ipar` (parent) search parameter is unreliable.** For hierarchical queries (e.g., "find all counties in Zhejiang"), use the canonical record drill-down approach instead: look up the parent record by ID and read its subordinate units.

**Romanization quirks:** Some names use older romanizations, not modern pinyin. For example, Ningbo is stored as "Ningpo". If a search returns no results, try alternative romanizations.

**Search uses prefix matching:** `n=beijing` matches 北京路, 北京行省, 北井县, etc. Short terms return more results.

## Python Script

Use `scripts/tgaz_api.py` for programmatic access (zero dependencies):

```python
from scripts.tgaz_api import TGAZAPI
api = TGAZAPI()

# Faceted search
results = api.search("suzhou", year=1820)
results = api.search("北京", feature_type="fu")

# ID lookup (correct URL format handled automatically)
record = api.get_by_id("hvd_32180")

# Extract structured data
name = api.get_name(record)                    # Chinese name
transcription = api.get_transcription(record)  # Romanized
begin, end = api.get_temporal_span(record)     # Year range
modern = api.get_modern_location(record)       # Present-day equivalent
ftype = api.get_feature_type(record)           # Administrative type
subs = api.get_subordinates(record)            # Child units (reliable!)

# Formatted summary
print(api.summarize(record))
```

## Quick Reference

**Faceted search:**
```
https://chgis.hudci.org/tgaz/placename?n=suzhou&yr=1820&fmt=json
```

Parameters:
- `n` — placename (Chinese or Romanized, required)
- `yr` — historical year (-222 to 1911)
- `ftyp` — administrative type: `xian` (县), `fu` (府), `zhou` (州), `sheng` (省), `dao` (道), `lu` (路), `jun` (郡)
- `ipar` — parent unit (⚠️ unreliable — prefer canonical record drill-down)
- `fmt` — output format (`json` recommended; default is XML)

**ID lookup** (format in URL path):
- `/placename/json/{id}` — JSON
- `/placename/xml/{id}` — XML
- `/placename/rdf/{id}` — RDF

## Hierarchical Queries (Recommended Approach)

Since `ipar` is unreliable, use this pattern for "find all X in Y" queries:

1. Search for the parent region to get its TGAZ ID
2. Look up the parent's canonical record via `/placename/json/{id}`
3. Read the `historical_context.has parts` field for subordinate units
4. Filter subordinates by year range and feature type

```python
api = TGAZAPI()
# Find Zhejiang
results = api.search("zhejiang", year=1850, feature_type="sheng")
zhejiang_id = results[0]["sys_id"]  # e.g., hvd_30015

# Get canonical record with subordinates
record = api.get_by_id(zhejiang_id)
subordinates = api.get_subordinates(record)

# Filter to active units in 1850
for sub in subordinates:
    # Check temporal range overlaps with 1850
    ...
```

## Encoding

- Pass Chinese characters as UTF-8 directly: `"n": "北京"` ✅
- Do not URL-encode Chinese into hex ❌
- URL-encode spaces and special characters normally

## Related Skills

- **cbdb-api**: Cross-reference CBDB address data with TGAZ placenames to map historical figures to locations
- **wikidata-search**: Find Wikidata entries for historical places identified in TGAZ

## Resources

- `references/api_reference.md` — Complete endpoint specs, all parameters, response field details
- `scripts/tgaz_api.py` — Python client with correct URL handling and hierarchical query support
