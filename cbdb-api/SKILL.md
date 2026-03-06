---
name: cbdb-api
description: Query the China Biographical Database (CBDB) API to retrieve comprehensive biographical data about historical Chinese figures. Use this skill when searching for information about Chinese historical figures, scholars, officials, or literary figures from the 7th century BCE through the 19th century CE. Applicable for queries about biographical details, social relationships, official positions, or when users mention specific Chinese names or CBDB person IDs.
version: 1.1.0
license: MIT
creator: AI
author: Kwok-leong Tang
contributors:
  - Claude (AI Assistant)
  - Z.ai (AI Platform)
---

# CBDB API

Query the China Biographical Database (~500K historical Chinese figures, 7th c. BCE–19th c. CE).

## Critical: Things Claude Won't Know Without This Skill

**API endpoint:**
```
https://cbdb.fas.harvard.edu/cbdbapi/person.php
```

**Response structure is deeply nested:**
```
response["Package"]["PersonAuthority"]["PersonInfo"]["Person"]
```
The Person object contains: `BasicInfo`, `AltNameInfo`, `AddrInfo`, `EntryInfo`, `PostingInfo`, `SocialAssocInfo`, `KinshipInfo`.

**Encoding:** Pass Chinese characters as UTF-8 directly — do not URL-encode into hex.

## Python Script

Use `scripts/cbdb_api.py` for programmatic access (zero dependencies):

```python
from scripts.cbdb_api import CBDBAPI
api = CBDBAPI()

# By name (Chinese or Pinyin)
person = api.query_by_name("蘇軾")
person = api.query_by_name("Wang Anshi")

# By ID (most precise)
person = api.query_by_id(1762)

# Extract structured data
basic = api.get_basic_info(person)      # name, dates, dynasty
postings = api.get_postings(person)     # official positions
assocs = api.get_social_associations(person)  # social network
kinship = api.get_kinship(person)       # family relations
alt_names = api.get_alt_names(person)   # courtesy name, pen name, etc.

# Formatted summary
print(api.summarize(person))
```

The script handles rate limiting, retries, and the nested JSON navigation automatically.

## Quick Reference

**Query by Chinese name:**
```
https://cbdb.fas.harvard.edu/cbdbapi/person.php?name=蘇軾&o=json
```

**Query by Pinyin:** (URL-encode spaces only)
```
https://cbdb.fas.harvard.edu/cbdbapi/person.php?name=Wang%20Anshi&o=json
```

**Query by ID:** (most precise)
```
https://cbdb.fas.harvard.edu/cbdbapi/person.php?id=1762&o=json
```

**Priority:** ID > Chinese characters > Pinyin (Pinyin may return multiple matches).

## Handling Results

**Multiple results from Pinyin queries:** Check dynasty, dates, or other context to identify the correct person. If ambiguous, present options to the user.

**Error response:**
```json
{"error": {"code": 404, "message": "Person not found."}}
```
Try alternative name forms (Chinese vs Pinyin), check spelling, or try courtesy names (字, 號).

**BasicInfo fields:** `PersonId`, `EngName`, `ChName`, `IndexYear`, `Gender`, `YearBirth`, `YearDeath`, `Dynasty`, `Notes`

## Related Skills

- **chgis-tgaz**: Look up birthplaces or associated locations from CBDB's `AddrInfo` in the CHGIS Temporal Gazetteer
- **wikidata-search**: Cross-reference CBDB figures with Wikidata for external identifiers (VIAF, LoC, etc.)

## Resources

- `references/api_reference.md` — Complete endpoint specs, all parameters, response structure details
- `scripts/cbdb_api.py` — Python client with rate limiting and structured data extraction
