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
The Person object contains: `BasicInfo`, `PersonAliases.Alias`, `PersonAddresses.Address`, `PersonEntryInfo.Entry`, `PersonPostings.Posting`, `PersonSocialStatus.SocialStatus`, `PersonKinshipInfo.Kinship`, `PersonSocialAssociation.Association`, `PersonTexts.Text`, `PersonSources.Source`.

Each section is a dict when it has records, but an **empty string `""`** when it has none. Inside a section, one record may come back as a dict and several as a list. `Person` itself may also be a list if the name matches more than one person.

**Encoding:** Pass Chinese characters as UTF-8 directly — do not URL-encode into hex.

## Python Script

Use `scripts/cbdb_api.py` for programmatic access (zero dependencies):

```python
from scripts.cbdb_api import CBDBAPI
api = CBDBAPI()

# By name (Chinese or Pinyin)
person = api.query_by_name("蘇軾")
person = api.query_by_name("Wang Anshi")
people = api.query_by_name_all("Wang Anshi")  # every match, as a list

# By ID (most precise)
person = api.query_by_id(1762)

# Extract structured data
basic = api.get_basic_info(person)      # name, dates, dynasty
postings = api.get_postings(person)     # official positions
assocs = api.get_social_associations(person)  # social network
kinship = api.get_kinship(person)       # family relations
alt_names = api.get_alt_names(person)   # courtesy name, pen name, etc.
entries = api.get_entries(person)       # exam / entry records
addresses = api.get_addresses(person)   # places

# Formatted summary
print(api.summarize(person))
```

The script handles rate limiting, retries (including HTTP 429 `Retry-After`), a `User-Agent` header, and the nested JSON navigation automatically. A person that is not found returns `None` (the API answers with HTTP 404 and a JSON error body).

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

**Error response** (sent with HTTP status 404; bad input such as a non-numeric ID gives 422):
```json
{"error": {"code": 404, "message": "Person not found."}}
```
Try alternative name forms (Chinese vs Pinyin), check spelling, or try courtesy names (字, 號).

**Common record fields:** Posting: `OfficeName`, `AddrName`, `FirstYear`, `LastYear`. Association: `AssocPersonName`, `AssocPersonId`, `AssocName` (relation type). Kinship: `KinPersonName`, `KinPersonId`, `KinRelName`. Alias: `AliasType`, `AliasName`. A year of `"0"` means unknown.

**BasicInfo fields:** `PersonId`, `EngName`, `ChName`, `IndexYear`, `Gender`, `YearBirth`, `YearDeath`, `Dynasty`, `Notes`

## Related Skills

- **chgis-tgaz**: Look up birthplaces or associated locations from CBDB's `PersonAddresses` in the CHGIS Temporal Gazetteer
- **wikidata-search**: Cross-reference CBDB figures with Wikidata for external identifiers (VIAF, LoC, etc.)

## Resources

- `references/api_reference.md` — Complete endpoint specs, all parameters, response structure details
- `scripts/cbdb_api.py` — Python client with rate limiting and structured data extraction
