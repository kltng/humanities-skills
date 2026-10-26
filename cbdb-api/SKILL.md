---
name: cbdb-api
description: Query the China Biographical Database (CBDB) API to retrieve comprehensive biographical data about historical Chinese figures. Use this skill when searching for information about Chinese historical figures, scholars, officials, or literary figures from the 7th century BCE through the 19th century CE. Applicable for queries about biographical details, social relationships, official positions, or when users mention specific Chinese names or CBDB person IDs.
version: 1.1.2
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

Use `scripts/cbdb_api.py` for programmatic access (zero dependencies).

`from scripts.cbdb_api import CBDBAPI` works only when the **skill folder is the working directory**. From anywhere else (and always under `python -I`), add the folder to the path first:

```python
import sys
sys.path.insert(0, "/path/to/cbdb-api")   # the folder that holds SKILL.md
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

# Did the name hit the main name, or an alt name? ("primary" / "alias" / "other")
api.name_match(person, "蘇軾")

# Formatted summary. Lists the first 20 postings and 20 associations and says
# how many were left out; pass max_items=None for all.
print(api.summarize(person))
print(api.summarize(person, max_items=None))
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

## Name Matching: Main Names Are Safe, Alt Names Are Not

The `name` parameter is reliable only for the person's **main name** (Chinese `ChName` or pinyin `EngName`). Alternative names (字, 號, 室名 ...) behave badly. Tested on 2026-10-26:

| Query | Result | Correct? |
|---|---|---|
| `王守仁`, `Wang Shouren` | 王守仁 (30374) | Yes |
| `陽明先生` (a 號) | 王守仁 (30374) | Yes |
| `子瞻` (蘇軾's 字) | 蘇軾 (3767) | Yes |
| `王陽明` (surname + 號, the form most people type) | 404 Person not found | No match |
| `陽明` | 毛燧傳 (72362), who also has the alt name 陽明 | Not 王守仁 |
| `伯安` (王守仁's 字; 9 people share it) | only 梁億 (10939) | One of 9, no warning |
| `東坡` | 唐庚 (1598), alt name 小東坡 | Not 蘇軾 |

So:

- When the API matches an alt name it returns **one** person, even if many people share that name, and it does not say so.
- Surname + 號 forms like 王陽明 or 蘇東坡 are not in CBDB and return nothing.
- After a name query, check `api.name_match(person, name)`. If it is not `"primary"`, treat the result as a guess. Show the user the person's `ChName`, dates and dynasty, and confirm.

**To turn a 字/號 into the main name first:**

1. **cbdb-local** skill (same data, local SQLite): `python3 scripts/cbdb_query.py person "陽明"` lists every person with a matching alt name, and `person "王陽明"` finds 王守仁 through 王 + 陽明先生.
2. **taiwan-ldt-authorities** skill (library name authorities): `python scripts/ldt_api.py lookup 王陽明 --mode variant` → `王守仁, 1472-1528`.

Then query this API with the main name or, better, the ID.

## Handling Results

**Multiple results from Pinyin queries:** Check dynasty, dates, or other context to identify the correct person. If ambiguous, present options to the user.

**Error response** (sent with HTTP status 404; bad input such as a non-numeric ID gives 422):
```json
{"error": {"code": 404, "message": "Person not found."}}
```
Try the other form (Chinese vs Pinyin) and check the spelling. If the user gave a 字 or 號, resolve it to the main name first (see **Name Matching** above); do not rely on the API for alt names.

**Common record fields:** Posting: `OfficeName`, `AddrName`, `FirstYear`, `LastYear`. Association: `AssocPersonName`, `AssocPersonId`, `AssocName` (relation type). Kinship: `KinPersonName`, `KinPersonId`, `KinRelName`. Alias: `AliasType`, `AliasName`. A year of `"0"` means unknown.

**BasicInfo fields:** `PersonId`, `EngName`, `ChName`, `IndexYear`, `Gender`, `YearBirth`, `YearDeath`, `Dynasty`, `Notes`

## Related Skills

- **chgis-tgaz**: Look up birthplaces or associated locations from CBDB's `PersonAddresses` in the CHGIS Temporal Gazetteer
- **cbdb-local**: Same data offline; lists all alt-name candidates and handles surname + 號 (王陽明)
- **taiwan-ldt-authorities**: Find the authorized main name from a variant (王陽明 → 王守仁)
- **wikidata-search**: Cross-reference CBDB figures with Wikidata for external identifiers (VIAF, LoC, etc.)

## Resources

- `references/api_reference.md` — Complete endpoint specs, all parameters, response structure details
- `scripts/cbdb_api.py` — Python client with rate limiting and structured data extraction

## Feedback and Citation

**Report a problem.** This skill is part of the public repository [kltng/humanities-skills](https://github.com/kltng/humanities-skills). If it fails (an API changed, a script errors, or these instructions are wrong), report it as a GitHub issue:

1. Ask the user before filing. Issues are public.
2. Check for an existing report: `gh issue list --repo kltng/humanities-skills --state all --search "cbdb-api"`
3. File it: `gh issue create --repo kltng/humanities-skills --label bug --title "[cbdb-api] <short summary>" --body "<details>"`. Without `gh`, give the user this link: https://github.com/kltng/humanities-skills/issues/new?template=skill-problem.yml
4. Include the skill name and version, what you ran, the error text, what you expected, and the environment (OS, Python version). Leave out API keys, personal data, private file paths, and unpublished research.

**Cite.** If this skill helped work that is published, please cite it, together with the data source it uses:

> Tang, Kwok-leong. *humanities-skills: cbdb-api* (version <version at the top of this file>). GitHub, <year>. https://github.com/kltng/humanities-skills

When you help a user write up results that relied on this skill, remind them once about this citation.
