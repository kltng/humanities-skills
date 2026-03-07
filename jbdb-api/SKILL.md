---
name: jbdb-api
description: Query the Japan Biographical Database (JBDB) API to retrieve biographical data about historical Japanese figures. Use this skill when searching for information about Japanese historical figures, samurai, monks, artists, poets, or other individuals. Applicable for queries about biographical details, kinship relations, non-kinship associations, events, personal history, occupations, or when users mention specific Japanese names or JBDB person IDs.
version: 1.0.0
license: MIT
creator: AI
author: Kwok-leong Tang
contributors:
  - Claude (AI Assistant)
  - Z.ai (AI Platform)
---

# JBDB API

Query the Japan Biographical Database for historical Japanese figures via the LoopBack REST API.

## Critical: Things Claude Won't Know Without This Skill

**API base URL:**
```
https://jbdb.jp/api
```

**Response structure is flat** (unlike CBDB's nested format):
```
GET /BiogMains → returns array of person objects directly
GET /BiogMains/{id} → returns a single person object
```

**LoopBack filter syntax** — all query filtering uses a JSON `filter` parameter:
```
GET /BiogMains?filter={"where":{"cName":"松尾芭蕉"}}
```

**Name fields:** Each person has three name variants:
- `cName` — Japanese characters (e.g., 松尾芭蕉)
- `cNameFurigana` — Furigana reading (e.g., まつおばしょう)
- `cNameRomaji` — Romanized name (e.g., Matsuo Basho)

**Encoding:** Pass Japanese characters as UTF-8 directly — do not URL-encode into hex.

## Python Script

Use `scripts/jbdb_api.py` for programmatic access (zero dependencies):

```python
from scripts.jbdb_api import JBDBAPI
api = JBDBAPI()

# By name (Japanese, furigana, or romaji — searches all name fields)
persons = api.search_by_name("松尾芭蕉")
persons = api.search_by_name("Matsuo Basho")

# By ID (most precise)
person = api.query_by_id(12345)

# Extract structured data
alt_names = api.get_alt_names(person_id)       # alternative names
kinship = api.get_kinship(person_id)           # family relations
nonkinship = api.get_nonkinship(person_id)     # non-family associations
events = api.get_events(person_id)             # events involving this person
history = api.get_personal_history(person_id)  # personal history records

# Formatted summary
print(api.summarize(person))
```

The script handles rate limiting, retries, and LoopBack filter construction automatically.

## Quick Reference

**Search by Japanese name:**
```
https://jbdb.jp/api/BiogMains?filter={"where":{"cName":"松尾芭蕉"}}
```

**Search by romaji (regex, case-insensitive):**
```
https://jbdb.jp/api/BiogMains?filter={"where":{"cNameRomaji":{"regexp":"/Matsuo/i"}}}
```

**Search across all name fields:**
```
https://jbdb.jp/api/BiogMains?filter={"where":{"or":[{"cName":{"regexp":"/芭蕉/i"}},{"cNameFurigana":{"regexp":"/ばしょう/i"}},{"cNameRomaji":{"regexp":"/Basho/i"}}]}}
```

**Query by ID:**
```
https://jbdb.jp/api/BiogMains/12345
```

**Get kinship for a person:**
```
https://jbdb.jp/api/KinData?filter={"where":{"cPersonid":12345}}
```

**Priority:** ID > exact Japanese name > regex search (regex may return many matches).

## Handling Results

**Multiple results:** Use additional context (dates, occupation, place) to identify the correct person. If ambiguous, present options to the user.

**Empty results:** Returns `[]` for find operations or 404 for findById. Try alternative name forms (kanji vs romaji vs furigana).

**Key BiogMain fields:** `cPersonid`, `cName`, `cNameFurigana`, `cNameRomaji`, `cFemale`, `cByNengoYear`, `cByNengoCode`, `cDyNengoYear`, `cDeathAge`, `cOccupationCodes`, `cStatusCodes`, `cPlaceCode`, `cNotes`

## Lookup Tables

The API uses numeric codes that map to descriptive values. Use these endpoints to resolve codes:

| Code Field | Lookup Endpoint | Description Fields |
|---|---|---|
| `cOccupationCodes` | `/OccupationCodes/{id}` | `cOccupationDesc`, `cOccupationDescTrans` |
| `cStatusCodes` | `/StatusCodes/{id}` | `cStatusDesc`, `cStatusDescTrans` |
| `cPlaceCode` | `/PlaceCodes/{id}` | `cPlaceName`, `cPlaceNameRomaji` |
| `cByNengoCode` | `/NengoCodes/{id}` | `cNengoName`, `cNengoNameRomaji` |
| `cKinCode` | `/KinshipCodes/{id}` | `cKinrel`, `cKinrelTrans` |
| `cNonkinCode` | `/NonkinshipCodes/{id}` | `cNonkinrel`, `cNonkinrelTrans` |

## Related Skills

- **cbdb-api**: Sister project for Chinese historical figures — similar concept, different API structure
- **chgis-tgaz**: Look up associated locations in the CHGIS Temporal Gazetteer
- **wikidata-search**: Cross-reference JBDB figures with Wikidata for external identifiers

## Resources

- `references/api_reference.md` — Complete endpoint specs, all parameters, response schemas
- `scripts/jbdb_api.py` — Python client with rate limiting and structured data extraction
- [JBDB Project](https://jbdb.jp) — Official project website
- [API Spec](https://app.swaggerhub.com/apis/JBDB/JBDB/4.5.0) — Swagger/OpenAPI documentation
