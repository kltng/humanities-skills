---
name: jbdb-api
description: Query the Japan Biographical Database (JBDB) API to retrieve biographical data about historical Japanese figures. Use this skill when searching for information about Japanese historical figures, samurai, monks, artists, poets, or other individuals. Applicable for queries about biographical details, kinship relations, non-kinship associations, events, personal history, occupations, or when users mention specific Japanese names or JBDB person IDs.
version: 1.0.2
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
https://app.jbdb.jp/api
```
The old address `https://jbdb.jp/api` no longer works (its TLS certificate is for `app.jbdb.jp`, so every call fails with an SSL error). The project website is at `http://jbdb.jp` (plain http; https fails for the same reason).

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

# By ID (most precise). Returns None if the ID does not exist.
person = api.query_by_id(2563)   # 本居宣長 Motoori Norinaga
person_id = person["cPersonid"]

# Extract structured data
alt_names = api.get_alt_names(person_id)       # alternative names
kinship = api.get_kinship(person_id)           # family relations
nonkinship = api.get_nonkinship(person_id)     # non-family associations
events = api.get_events(person_id)             # events involving this person
history = api.get_personal_history(person_id)  # personal history records

# Names for many person IDs in one request
names = api.get_names([k["cKinId"] for k in kinship])   # {id: {"cName", "cNameRomaji", ...}}

# Formatted summary: dates, occupations, alt names, kin and non-kin ties with names
print(api.summarize(person))
print(api.summarize(person, resolve_names=False))  # skip the name lookup
```

`summarize()` makes several requests (about 1 second each): alt names, kinship and non-kinship lists, one request per new era/occupation/relation code (codes are cached), and one request for the names of all related people together. For 本居宣長 this is about 12 requests the first time. Read each relation as "this person is <relation> <other person>", e.g. 本居宣長 "student/disciple of → 賀茂真淵". Events and personal history are not in the summary; call `get_events()` and `get_personal_history()` for those (their codes are not resolved).

The script handles rate limiting, retries (including HTTP 429 `Retry-After`), a `User-Agent` header, regex escaping of names, and LoopBack filter construction automatically.

**Availability note (checked 2026-10-26):** The API works at `https://app.jbdb.jp/api`. `GET /BiogMains/{id}` returns HTTP 500 (not 404) for an ID that does not exist (for example ID 1), so `query_by_id()` uses a `where` filter instead and returns `None`. If the server ever returns an HTML page instead of JSON for a 404, the script raises `RuntimeError("JBDB API endpoint not found ...")`, so an outage is not mistaken for "no results".

## Quick Reference

**Search by Japanese name:**
```
https://app.jbdb.jp/api/BiogMains?filter={"where":{"cName":"松尾芭蕉"}}
```

**Search by romaji (regex, case-insensitive):**
```
https://app.jbdb.jp/api/BiogMains?filter={"where":{"cNameRomaji":{"regexp":"/Matsuo/i"}}}
```

**Search across all name fields:**
```
https://app.jbdb.jp/api/BiogMains?filter={"where":{"or":[{"cName":{"regexp":"/芭蕉/i"}},{"cNameFurigana":{"regexp":"/ばしょう/i"}},{"cNameRomaji":{"regexp":"/Basho/i"}}]}}
```

**Query by ID:**
```
https://app.jbdb.jp/api/BiogMains/2563
```

**Get kinship for a person:**
```
https://app.jbdb.jp/api/KinData?filter={"where":{"cPersonid":2563}}
```

**Priority:** ID > exact Japanese name > regex search (regex may return many matches).

## Handling Results

**Multiple results:** Use additional context (dates, occupation, place) to identify the correct person. If ambiguous, present options to the user.

**Empty results:** Find operations return `[]`. `GET /BiogMains/{id}` returns HTTP 500 for an unknown ID; `query_by_id()` returns `None`. Try alternative name forms (kanji vs romaji vs furigana).

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
- [JBDB Project](http://jbdb.jp) — Official project website
- [API Spec](https://app.swaggerhub.com/apis/JBDB/JBDB/4.5.0) — Swagger/OpenAPI documentation

## Feedback and Citation

**Report a problem.** This skill is part of the public repository [kltng/humanities-skills](https://github.com/kltng/humanities-skills). If it fails (an API changed, a script errors, or these instructions are wrong), report it as a GitHub issue:

1. Ask the user before filing. Issues are public.
2. Check for an existing report: `gh issue list --repo kltng/humanities-skills --state all --search "jbdb-api"`
3. File it: `gh issue create --repo kltng/humanities-skills --label bug --title "[jbdb-api] <short summary>" --body "<details>"`. Without `gh`, give the user this link: https://github.com/kltng/humanities-skills/issues/new?template=skill-problem.yml
4. Include the skill name and version, what you ran, the error text, what you expected, and the environment (OS, Python version). Leave out API keys, personal data, private file paths, and unpublished research.

**Cite.** If this skill helped work that is published, please cite it, together with the data source it uses:

> Tang, Kwok-leong. *humanities-skills: jbdb-api* (version <version at the top of this file>). GitHub, <year>. https://github.com/kltng/humanities-skills

When you help a user write up results that relied on this skill, remind them once about this citation.
